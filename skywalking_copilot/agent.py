import asyncio
import datetime
import os
from typing import List, AsyncIterator, Dict, Optional, Any
from uuid import UUID

from langchain.agents import Tool, AgentExecutor, create_openai_functions_agent
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder, ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI
from langchain_openai.chat_models.base import BaseChatOpenAI
from langchain_postgres import PostgresChatMessageHistory
from psycopg import AsyncConnection

from skywalking_copilot.database import CHAT_HISTORY_TABLE
from skywalking_copilot.domain import Session
from skywalking_copilot.skywalking import SkywalkingApi, ServiceMetrics


def _metrics_to_markdown(service_metrics: Dict[str, ServiceMetrics]) -> str:
    return ("""| Service | Load (calls/min) | Success Rate (%) | Latency (ms) | Apdex |
|---|---|---|---|---|
""" + "\n".join(
                [f"|{service}|{metrics.cpm}|{metrics.sla}|{metrics.resp_time}|{metrics.apdex}|" for service, metrics in
                 service_metrics.items()]))


class Agent:

    def __init__(self, session: Session, db: AsyncConnection, sw_api: SkywalkingApi):
        self._session = session
        self._llm = self._build_llm()
        self._memory = self._build_memory(session.id, db)
        self._sw_api = sw_api
        tools = [
            Tool.from_function(
                name="services_metrics",
                description="gets the service metrics collected in Skywalking for the last 10 minutes",
                coroutine=self._find_services_metrics,
                func=None,
                return_direct=True)
        ]
        self._agent = self._build_agent(self._llm, self._memory, tools)

    async def _find_services_metrics(self, _) -> str:
        services = await self._sw_api.find_services()
        now = datetime.datetime.now(datetime.UTC)
        service_metrics = await self._sw_api.find_general_services_metrics(services,
                                                                           now - datetime.timedelta(minutes=10), now)
        return _metrics_to_markdown(service_metrics)

    @staticmethod
    def _build_llm():
        return AzureChatOpenAI(azure_endpoint=os.getenv("AZURE_ENDPOINT"),
                               deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME"),
                               model_name=os.getenv("MODEL_NAME"), temperature=0, verbose=True, streaming=True)

    @staticmethod
    def _build_memory(session_id: UUID, db: AsyncConnection) -> ConversationBufferMemory:
        message_history = PostgresChatMessageHistory(CHAT_HISTORY_TABLE, str(session_id), async_connection=db)
        return ConversationBufferMemory(memory_key="chat_history", chat_memory=message_history, return_messages=True)

    def _build_agent(self, llm: BaseChatOpenAI, memory: ConversationBufferMemory, tools: List[Tool]) -> AgentExecutor:
        prompt = ChatPromptTemplate(messages=[
            SystemMessage(content=self._read_file("system-prompt.md")),
            MessagesPlaceholder(variable_name=memory.memory_key),
            HumanMessagePromptTemplate.from_template("{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        agent = create_openai_functions_agent(llm=llm, tools=tools, prompt=prompt)
        return AgentExecutor(
            agent=agent,
            tools=tools,
            memory=memory,
            verbose=True,
            return_intermediate_steps=False,
            max_iterations=os.getenv("AGENT_MAX_ITERATIONS", 3)
        )

    @staticmethod
    def _read_file(path: str) -> str:
        with open(os.path.join('skywalking_copilot', 'assets', path), encoding="utf-8") as f:
            return f.read()

    async def start_session(self):
        await self._memory.chat_memory.aadd_messages(
            [HumanMessage(content="this is my locale: " + self._session.locales[0])])

    async def ask(self, question: str) -> AsyncIterator[str]:
        callback = FullAsyncIteratorCallbackHandler()
        task = asyncio.create_task(
            self._agent.ainvoke({"input": question},
                                RunnableConfig(callbacks=[callback])))
        resp = ""
        async for token in callback.aiter():
            resp += token
            yield token
        ret = await task
        answer = ret['output']
        # when using tools, tokens are not passed to the callback handler, so we need to get the
        # response directly from agent run call
        if answer != resp:
            yield answer


# avoid warning due to unimplemented methods
class FullAsyncIteratorCallbackHandler(AsyncIteratorCallbackHandler):

    async def on_chat_model_start(
            self, serialized: Dict[str, Any], messages: List[List[BaseMessage]], *, run_id: UUID,
            parent_run_id: Optional[UUID] = None, tags: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        pass
