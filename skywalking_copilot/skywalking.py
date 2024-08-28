import logging
import datetime
from enum import Enum
from typing import List, Optional, Dict

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from pydantic import BaseModel

from skywalking_copilot.templates import solve_template


class Service(BaseModel):
    id: str
    name: str
    normal: bool
    shortName: str

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
    id: str
    value: Optional[str]


class ServiceMetric(BaseModel):
    labels: List[str]
    values: List[ServiceMetricValue]

    @staticmethod
    def from_gql(data: dict) -> 'ServiceMetric':
        return ServiceMetric(
            labels=[f"{label['key']}{label['value']}" for label in data['metric']['labels']],
            values=[ServiceMetricValue(**val) for val in data['values']])


class SkywalkingApi:

    def __init__(self, url: str):
        transport = AIOHTTPTransport(url=url + "/graphql")
        self._client = Client(transport=transport, fetch_schema_from_transport=True)
        self._logger = logging.getLogger("skywalking_api")

    async def connect(self):
        await self._client.connect_async(reconnecting=True)

    async def close(self):
        await self._client.close_async()

    async def find_services(self) -> List[Service]:
        result = await self._query(solve_template("list-services-query-template.gql", {}))
        return [Service(**service) for service in result['services']]

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
                service_metrics[metric_name] = metric_value[0].value
                ret[service_name] = service_metrics
        return ret

    async def find_services_metrics(self, services: List[Service], metrics: Dict[str, str], time_range: TimeRange) -> \
            Dict[str, Dict[str, List[ServiceMetric]]]:
        query = self._build_services_metrics_query(services, metrics, time_range)
        result = await self._query(query)
        return self._parse_service_metrics(result)

    @staticmethod
    def _build_services_metrics_query(services: List[Service], metrics: Dict[str, str], time_range: TimeRange) -> str:
        queries = []
        for service in services:
            for metric_name, expression in metrics.items():
                query = solve_template("service-metric-query-template.gql",
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
                self._logger.error(f"Error retrieving {expression_name}: {error}")
                continue
            name_parts = expression_name.split('_', 1)
            service_metrics = ret.setdefault(name_parts[0], {})
            metric_results = service_metrics.setdefault(name_parts[1], [])
            for metric_result in expression_result['results']:
                metric_results.append(ServiceMetric.from_gql(metric_result))
        return ret

    async def find_services_topology(self, services: List[Service], time_range: TimeRange) -> Topology:
        service_ids = _val_to_gql([service.id for service in services])
        result = await self._query(
            solve_template("services-topology-query-template.gql",
                           {"duration": time_range, "service_ids": service_ids}))
        return Topology.from_graphql(result['topology'])
