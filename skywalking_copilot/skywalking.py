import logging
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from pydantic import BaseModel


class Service(BaseModel):
    id: str
    name: str
    normal: bool
    shortName: str


class DurationStep(Enum):
    MINUTE = "MINUTE"


class ServiceMetrics(BaseModel):
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
        result = await self._query("""
            query listServices {
              services: listServices(layer: "GENERAL") {
                id
                name
                normal
                shortName
              }
            }
        """)
        return [Service(**service) for service in result['services']]

    async def _query(self, query: str) -> dict:
        return await self._client.session.execute(gql(query))

    async def find_services_metrics(self,
            services: List[Service], start_time: datetime, end_time: datetime) -> Dict[str, ServiceMetrics]:
        expressions = {
            "cpm": "avg(service_cpm)",
            "sla": "avg(service_sla)/100",
            "resp_time": "avg(service_resp_time)",
            "apdex": "avg(service_apdex)/10000",
        }
        duration = self._duration_from_limits(start_time, end_time)
        queries = []
        for service in services:
            entity_val = f"{{serviceName: \"{service.name}\", normal: {'true' if service.normal else 'false'}}}"
            for metric_name, expression in expressions.items():
                queries.append(f"""
                    {service.shortName}_{metric_name}: execExpression(expression: \"{expression}\", 
                    entity: {entity_val}, duration: {duration}) {{
                        results {{
                            values {{
                                value
                            }}
                        }}
                        error
                    }}
                """)
        result = await self._query(f"""
            query queryMetrics {{
              {'\n'.join(queries)}
            }}
        """)
        ret = {}
        for metric_name, metric_val in result.items():
            if metric_val['error']:
                self._logger.error(f"Error retrieving {metric_name}: {metric_val['error']}")
                continue
            value = metric_val['results'][0]['values'][0]['value']
            name_parts = metric_name.split('_', 1)
            service_metrics = ret.get(name_parts[0], ServiceMetrics())
            service_metrics[name_parts[1]] = value
            ret[name_parts[0]] = service_metrics
        return ret

    def _duration_from_limits(self, start_time: datetime, end_time: datetime) -> str:
        duration = {
            "start": start_time.strftime("%Y-%m-%d %H%M"),
            "end": end_time.strftime("%Y-%m-%d %H%M"),
            "step": DurationStep.MINUTE
        }
        return self._val_to_gql(duration)

    def _val_to_gql(self, data: any) -> str:
        if isinstance(data, str):
            return f'"{data.replace("\\", "\\\\").replace("\n", "\\n").replace("\"", "\\\"")}"'
        elif isinstance(data, bool):
            return "true" if data else "false"
        elif isinstance(data, dict):
            return f"{{{', '.join([f'{key}: {self._val_to_gql(val)}' for key, val in data.items()])}}}"
        elif isinstance(data, list):
            return f"[{', '.join([self._val_to_gql(val) for val in data])}]"
        elif isinstance(data, Enum):
            return data.value
        else:
            return str(data)

    async def find_services_topology(
            self, services: List[Service], start_time: datetime, end_time: datetime) -> Topology:
        duration = self._duration_from_limits(start_time, end_time)
        service_ids = self._val_to_gql([service.id for service in services])
        result = await self._query(f"""
            query queryTopology {{
              topology: getServicesTopology(duration: {duration}, serviceIds: {service_ids}) {{
                nodes {{
                  id
                  name
                  type
                }}
                calls {{
                  source
                  target
                }}
              }}
            }}""")
        return Topology.from_graphql(result['topology'])
