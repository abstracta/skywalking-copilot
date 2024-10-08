import asyncio
import logging
import os
from typing import Annotated, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status, Depends, Request, Body
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import ServerSentEvent

from skywalking_copilot.agent import Agent
from skywalking_copilot.alarms import find_new_alarms
from skywalking_copilot.database import get_db, SessionsRepository, QuestionsRepository, get_raw_connection
from skywalking_copilot.domain import SessionBase, Session, Question
from skywalking_copilot.skywalking import SkywalkingApi, TimeRange, AlarmEvent, TraceSpan
from skywalking_copilot.templates import solve_response

app = FastAPI()
assets_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'assets')
templates = Jinja2Templates(directory=assets_path)
sw_api = SkywalkingApi(os.getenv("SKYWALKING_URL"))
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup_event():
    await sw_api.connect()


@app.on_event("shutdown")
async def shutdown_event():
    await sw_api.close()


@app.get('/manifest.json')
async def get_manifest(request: Request) -> Response:
    return templates.TemplateResponse("manifest.json", {"request": request, "app_url": os.getenv("APP_URL"),
                                                        "support_email": os.getenv("SUPPORT_EMAIL")},
                                      media_type='application/json')


@app.get('/logo.png')
async def get_logo() -> FileResponse:
    return FileResponse(os.path.join(assets_path, 'logo.png'))


@app.post('/sessions', status_code=status.HTTP_201_CREATED)
async def create_session(
        req: SessionBase,
        db: Annotated[AsyncSession, Depends(get_db)]) -> Session:
    ret = Session(**req.model_dump())
    await SessionsRepository(db).save(ret)
    conn = await get_raw_connection(db)
    await Agent(ret, conn, sw_api).start_session()
    return ret


class QuestionRequest(BaseModel):
    question: str


async def _find_session(session_id: str, db: AsyncSession) -> Session:
    ret = await SessionsRepository(db).find_by_id(session_id)
    if not ret:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return ret


@app.post('/sessions/{session_id}/questions')
async def answer_question(
        session_id: str, req: QuestionRequest,
        db: Annotated[AsyncSession, Depends(get_db)]) -> Response:
    session = await _find_session(session_id, db)
    return StreamingResponse(agent_response_stream(req, session, db), media_type="text/event-stream")


async def agent_response_stream(
        req: QuestionRequest,
        session: Session,
        db: AsyncSession) -> AsyncIterator[str]:
    try:
        conn = await get_raw_connection(db)
        answer_stream = Agent(session, conn, sw_api).ask(req.question)
        complete_answer = ""
        async for token in answer_stream:
            complete_answer = complete_answer + token
            yield ServerSentEvent(data=token).encode()
        ret = Question(question=req.question, answer=complete_answer, session=session)
        await QuestionsRepository(db).save(ret)
    except Exception:
        logger.exception("Problem answering question")
        yield ServerSentEvent(event="error").encode()


class InteractionResponse(BaseModel):
    summary: str


class CapturedTrace(BaseModel):
    traceId: str


@app.post('/sessions/{session_id}/interactions')
async def record_interaction(
        session_id: str, db: Annotated[AsyncSession, Depends(get_db)],
        traces: Optional[List[CapturedTrace]] = Body(None)) -> InteractionResponse:
    await _find_session(session_id, db)
    if traces:
        # sometimes the trace is not available immediately, so we do some retries
        spans = await _await_found_trace([trace.traceId for trace in traces])
        service = await sw_api.find_service_by_name(spans[0].service) if spans else None
        return InteractionResponse(
            summary=solve_response("traces", {"spans": _build_spans_context(spans),
                                              "sw_url": sw_api.get_service_url(service)}) if spans else "")
    else:
        alarms = await find_new_alarms(TimeRange.from_last_minutes(30), 10, sw_api, session_id, db)
        return InteractionResponse(
            summary=solve_response("alarms", {"alarms": await _build_alarms_context(alarms)}) if alarms else "")


async def _await_found_trace(trace_ids: List[str]) -> List[TraceSpan]:
    spans = []
    for trace_id in trace_ids:
        spans += await sw_api.find_trace_spans(trace_id)
    max_retries = 4
    retries = 0
    while not spans and retries < max_retries:
        await asyncio.sleep(5)
        for trace_id in trace_ids:
            spans += await sw_api.find_trace_spans(trace_id)
        retries += 1
    return spans


def _build_spans_context(spans: List[TraceSpan], prefix: str = "") -> List[Dict]:
    ret = []
    for idx, span in enumerate(spans):
        ret.append({
            'prefix': prefix + ("└─ " if idx == len(spans) - 1 else "├─ "),
            'name': _build_span_name(span),
            'duration': span.end_time - span.start_time
        })
        ret += _build_spans_context(span.children, prefix + ("    " if idx == len(spans) - 1 else "│   "))
    return ret


def _build_span_name(span: TraceSpan) -> str:
    if span.layer == 'Http':
        return f"{span.tags.get('http.method', 'GET')} {span.tags.get('url') or span.tags.get('http.url')
                                                        or span.endpoint}"
    elif span.layer == 'Database':
        return f"@{span.peer} {span.tags.get('db.statement') or span.endpoint}"
    elif span.layer == 'MQ':
        return f"@{span.peer} {span.endpoint}"
    return span.endpoint


async def _build_alarms_context(alarms: List[AlarmEvent]) -> List[Dict]:
    services = await sw_api.find_services()
    services_map = {service.name: service for service in services}
    return [{
        'start': alarm.start_time.strftime('%H:%M'),
        'end': alarm.end_time.strftime('%H:%M'),
        'type': alarm.type.value,
        'service_name': alarm.source.service,
        'service_url': sw_api.get_service_url(services_map[alarm.source.service]),
        'message': alarm.message
    } for alarm in alarms]
