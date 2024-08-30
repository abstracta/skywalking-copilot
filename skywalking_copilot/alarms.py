from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession

import skywalking_copilot.database as database
from skywalking_copilot import skywalking
from skywalking_copilot.skywalking import AlarmEvent


async def find_new_alarms(
        time_range: skywalking.TimeRange, limit: int, sw_api: skywalking.SkywalkingApi,
        session_id: str, db: AsyncSession) -> List[AlarmEvent]:
    alarms = await sw_api.find_alarms(time_range, limit)
    events = _group_events_by_alarm_id_and_service(alarms)
    events_repo = database.AlarmEventsRepository(db)
    known_events_list = await events_repo.find_by_session_id(session_id)
    known_events = _group_known_events_by_alarm_id_and_service(known_events_list)
    return await _find_new_events(events, known_events, session_id, events_repo)


def _group_events_by_alarm_id_and_service(alarms: List[skywalking.Alarm]) \
        -> Dict[str, Dict[str, skywalking.AlarmEvent]]:
    ret = {}
    for alarm in alarms:
        alarm_id = alarm.id
        last_source_event = {}
        for event in alarm.events:
            service = event.source.service
            if service not in last_source_event or last_source_event[service].startTime < event.startTime:
                last_source_event[service] = event
        ret[alarm_id] = last_source_event
    return ret


def _group_known_events_by_alarm_id_and_service(known_events: List[database.AlarmEvent]) \
        -> Dict[str, Dict[str, database.AlarmEvent]]:
    ret = {}
    for event in known_events:
        if event.alarm_id not in ret:
            ret[event.alarm_id] = {}
        ret[event.alarm_id][event.service] = event
    return ret


async def _find_new_events(
        events: Dict[str, Dict[str, skywalking.AlarmEvent]], known_events: Dict[str, Dict[str, database.AlarmEvent]],
        session_id: str, events_repo: database.AlarmEventsRepository) -> List[skywalking.AlarmEvent]:
    ret = []
    for alarm_id, events_by_service in events.items():
        for service_name, event in events_by_service.items():
            if alarm_id not in known_events or service_name not in known_events[alarm_id]:
                ret.append(event)
                await events_repo.save(_build_database_event(session_id, alarm_id, event))
            else:
                known_event = known_events[alarm_id][service_name]
                if known_event.id != event.uuid:
                    ret.append(event)
                    await events_repo.delete(known_event)
                    await events_repo.save(_build_database_event(session_id, alarm_id, event))
    return ret


def _build_database_event(session_id: str, alarm_id: str, event: skywalking.AlarmEvent) -> database.AlarmEvent:
    return database.AlarmEvent(
        session_id=session_id, alarm_id=alarm_id, id=event.uuid, event_type=event.type, start_time=event.startTime,
        end_time=event.endTime, service=event.source.service, message=event.message)
