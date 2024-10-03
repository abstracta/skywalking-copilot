import datetime
import logging
import uuid
from enum import Enum
from typing import List, Optional, Dict, Any

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from pydantic import BaseModel

from skywalking_copilot.templates import solve_template

logger = logging.getLogger(__name__)


class Service(BaseModel):
    id: str
    name: str
    normal: bool
    # This field does not follow python naming convention to simplify object creation from graphql response
    shortName: str
    layers: List[str]

    def to_gql(self) -> str:
        return _val_to_gql({"serviceName": self.name, "normal": self.normal})


def _val_to_gql(data: any) -> str:
    if isinstance(data, str):
        return f'"{data.replace("\\", "\\\\").replace("\n", "\\n").replace("\"", "\\\"")}"'
    elif isinstance(data, bool):
        return "true" if data else "false"
    elif isinstance(data, dict):
        return f"{{{', '.join([f'{key}: {_val_to_gql(val)}' for key, val in data.items()])}}}"
    elif isinstance(data, list):
        return f"[{', '.join([_val_to_gql(val) for val in data])}]"
    elif isinstance(data, Enum):
        return data.value
    else:
        return str(data)


class DurationStep(Enum):
    MINUTE = "MINUTE"


class TimeRange(BaseModel):
    start: datetime.datetime
    end: datetime.datetime
    step: DurationStep

    @staticmethod
    def from_last_minutes(minutes: int) -> 'TimeRange':
        now = datetime.datetime.now(datetime.UTC)
        return TimeRange(start=now - datetime.timedelta(minutes=minutes), end=now, step=DurationStep.MINUTE)

    def to_gql(self) -> str:
        duration = {
            "start": self.start.strftime("%Y-%m-%d %H%M"),
            "end": self.end.strftime("%Y-%m-%d %H%M"),
            "step": self.step
        }
        return _val_to_gql(duration)


class ServiceSummaryMetrics(BaseModel):
    cpm: Optional[float] = None
    sla: Optional[float] = None
    resp_time: Optional[float] = None
    apdex: Optional[float] = None

    def __setitem__(self, key, value):
        setattr(self, key, value)


class TopologyNode(BaseModel):
    id: str
    name: str
    type: Optional[str]

    @staticmethod
    def from_graphql(data: dict) -> 'TopologyNode':
        return TopologyNode(**data)


class TopologyEdge(BaseModel):
    source: str
    target: str

    @staticmethod
    def from_graphql(data: dict) -> 'TopologyEdge':
        return TopologyEdge(**data)


class Topology(BaseModel):
    nodes: List[TopologyNode]
    edges: List[TopologyEdge]

    @staticmethod
    def from_graphql(data: dict) -> 'Topology':
        return Topology(nodes=[TopologyNode.from_graphql(node) for node in data['nodes']],
                        edges=[TopologyEdge.from_graphql(edge) for edge in data['calls']])


class ServiceMetricValue(BaseModel):
    id: Optional[str]
    value: Optional[str]


class ServiceMetric(BaseModel):
    labels: List[str]
    values: List[ServiceMetricValue]

    @staticmethod
    def from_gql(data: dict) -> 'ServiceMetric':
        return ServiceMetric(
            labels=[f"{label['key']}{label['value']}" for label in data['metric']['labels']],
            values=[ServiceMetricValue(**val) for val in data['values']])


def _parse_epoch(epoch: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(epoch / 1000)


class AlarmType(Enum):
    ERROR = "Error"


class AlarmSource(BaseModel):
    service: str


class AlarmEvent(BaseModel):
    uuid: uuid.UUID
    start_time: datetime.datetime
    end_time: datetime.datetime
    type: AlarmType
    source: AlarmSource
    message: str

    @staticmethod
    def from_gql(data: dict) -> 'AlarmEvent':
        return AlarmEvent(uuid=uuid.UUID(data['uuid']), start_time=_parse_epoch(data['startTime']),
                          end_time=_parse_epoch(data['endTime']), type=AlarmType(data['type']),
                          source=AlarmSource(**data['source']), message=data['message'])


class Alarm(BaseModel):
    id: str
    events: List[AlarmEvent]

    @staticmethod
    def from_gql(data: dict) -> 'Alarm':
        return Alarm(id=data['id'], events=[AlarmEvent.from_gql(event) for event in data['events']])


class TraceSpanType(Enum):
    ENTRY = "Entry"
    EXIT = "Exit"
    LOCAL = "Local"


class TraceSpan(BaseModel):
    trace_id: str
    segment_id: str
    span_id: int
    parent_segment_id: Optional[str]
    parent_span_id: Optional[int]
    ref_trace_id: Optional[str]
    service: str
    start_time: int
    end_time: int
    endpoint: str
    type: TraceSpanType
    peer: str
    component: str
    is_error: bool
    layer: str
    tags: Dict[str, str]
    children: List['TraceSpan']

    @staticmethod
    def from_gql(data: dict) -> 'TraceSpan':
        refs = data['refs']
        ref = refs[0] if refs else None
        return TraceSpan(
            trace_id=data['traceId'],
            segment_id=data['segmentId'], span_id=data['spanId'],
            parent_segment_id=ref['parentSegmentId'] if ref else None,
            parent_span_id=ref['parentSpanId'] if ref else None,
            ref_trace_id=ref['traceId'] if ref else None,
            service=data['serviceCode'], start_time=int(data['startTime']), end_time=int(data['endTime']),
            endpoint=data['endpointName'], type=TraceSpanType(data['type']), peer=data['peer'],
            component=data['component'], is_error=data['isError'], layer=data['layer'],
            tags={t['key']: t['value'] for t in data['tags']}, children=[])


class SkywalkingApi:

    def __init__(self, url: str):
        self._base_url = url
        self.services_url = f"{url}/General-Service/Services"
        transport = AIOHTTPTransport(url=url + "/graphql")
        self._client = Client(transport=transport, fetch_schema_from_transport=True)

    async def connect(self):
        await self._client.connect_async(reconnecting=True)

    async def close(self):
        await self._client.close_async()

    async def find_services(self) -> List[Service]:
        result = await self._query_by_name("list-services", {})
        return [Service(**service) for service in result['services']]

    async def _query_by_name(self, query_name: str, context: Dict[str, Any]) -> dict:
        return await self._query(self._solve_query(query_name, context))

    @staticmethod
    def _solve_query(query_name: str, context: Dict[str, Any]) -> str:
        return solve_template(f"graphql/{query_name}.gql", context)

    async def _query(self, query: str) -> dict:
        return await self._client.session.execute(gql(query))

    async def find_services_summary_metrics(self, services: List[Service], time_range: TimeRange) \
            -> Dict[str, ServiceSummaryMetrics]:
        metrics = {
            "cpm": "avg(service_cpm)",
            "sla": "avg(service_sla)/100",
            "resp_time": "avg(service_resp_time)",
            "apdex": "avg(service_apdex)/10000",
        }
        result = await self.find_services_metrics(services, metrics, time_range)
        ret = {}
        for service_name, service_metrics in result.items():
            for metric_name, metric_value in service_metrics.items():
                service_metrics = ret.get(service_name, ServiceSummaryMetrics())
                service_metrics[metric_name] = metric_value[0].values[0].value
                ret[service_name] = service_metrics
        return ret

    async def find_services_metrics(self, services: List[Service], metrics: Dict[str, str], time_range: TimeRange) -> \
            Dict[str, Dict[str, List[ServiceMetric]]]:
        query = self._build_services_metrics_query(services, metrics, time_range)
        result = await self._query(query)
        return self._parse_service_metrics(result)

    def _build_services_metrics_query(
            self, services: List[Service], metrics: Dict[str, str], time_range: TimeRange) -> str:
        queries = []
        for service in services:
            for metric_name, expression in metrics.items():
                query = self._solve_query("service-metric",
                                          {"service": service, "metric_name": metric_name, "expression": expression,
                                           "duration": time_range})
                queries.append(query)
        return f"""
            query queryMetrics {{
              {'\n'.join(queries)}
            }}
        """

    def _parse_service_metrics(self, result: dict) -> Dict[str, Dict[str, List[ServiceMetric]]]:
        ret = {}
        for expression_name, expression_result in result.items():
            error = expression_result['error']
            if error:
                logger.error(f"Error retrieving {expression_name}: {error}")
                continue
            name_parts = expression_name.split('_', 1)
            service_metrics = ret.setdefault(name_parts[0], {})
            metric_results = service_metrics.setdefault(name_parts[1], [])
            for metric_result in expression_result['results']:
                metric_results.append(ServiceMetric.from_gql(metric_result))
        return ret

    async def find_services_topology(self, services: List[Service], time_range: TimeRange) -> Topology:
        service_ids = _val_to_gql([service.id for service in services])
        result = await self._query_by_name("services-topology", {"duration": time_range, "service_ids": service_ids})
        return Topology.from_graphql(result['topology'])

    def get_service_url(self, service: Service) -> str:
        layer = service.layers[0]
        return f"{self._base_url}/dashboard/{layer}/Service/{service.id}/{'Browser-App' if layer == 'BROWSER' else 'General-Service'}"

    async def find_alarms(self, time_range: TimeRange, limit: int) -> List[Alarm]:
        result = await self._query_by_name("alarms", {"duration": time_range, "limit": limit})
        return [Alarm.from_gql(alarm) for alarm in result['getAlarm']['msgs']]

    async def find_trace_spans(self, trace_id: str) -> List[TraceSpan]:
        result = await self._query_by_name("trace", {"trace_id": _val_to_gql(trace_id)})
        spans_by_id = {}
        segments_parents = {}
        root_spans = []
        for span in result['trace']['spans']:
            span = TraceSpan.from_gql(span)
            spans_by_id[self._build_unique_span_id(span.segment_id, span.span_id)] = span
            segment_parent = segments_parents.get(span.segment_id)
            if not segment_parent and span.parent_segment_id:
                segment_parent = spans_by_id.get(self._build_unique_span_id(span.parent_segment_id, span.parent_span_id))
                if segment_parent:
                    segments_parents[span.segment_id] = segment_parent
            if segment_parent:
                segment_parent.children.append(span)
            else:
                root_spans.append(span)
        for span in root_spans:
            self._simplify_span(span)
        return root_spans

    @staticmethod
    def _build_unique_span_id(segment_id: str, span_id: int) -> str:
        return f"{segment_id}-{span_id}"

    def _simplify_span(self, span: TraceSpan):
        final_children = []
        for child in span.children:
            self._simplify_span(child)
            if child.type in [TraceSpanType.LOCAL, TraceSpanType.ENTRY]:
                final_children += child.children
            else:
                final_children.append(child)
        span.children = final_children

    async def find_service_by_name(self, service_name: str) -> Service:
        result = await self._query_by_name("service-by-name", {"service_name": service_name})
        return Service(**result['service']) if result else None
