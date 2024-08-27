import os
import re

from jinja2 import Environment, FileSystemLoader
from langchain.tools import BaseTool
from pydantic import BaseModel

from skywalking_copilot.skywalking import SkywalkingApi, TimeRange, Topology

assets_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'assets')
templates_repo = Environment(loader=FileSystemLoader(assets_path))


class NoArgsSchema(BaseModel):
    pass


class AgentTool(BaseTool):
    sw_api: SkywalkingApi
    return_direct = True

    def _run(self, *args, **kwargs):
        raise NotImplementedError()


class ServicesMetricsTool(AgentTool):
    name = "get_services_metrics"
    description = "gets the metrics of all services in the last 10 minutes"

    async def _arun(self) -> str:
        services = await self.sw_api.find_services()
        service_metrics = await self.sw_api.find_services_metrics(services, TimeRange.from_last_minutes(10))
        return templates_repo.get_template("services-metrics-template.md").render(service_metrics=service_metrics)


class ServicesTopologyTool(AgentTool):
    name = "get_services_topology"
    description = """gets a diagram with the topology of services showing how are they connected.
    This information is based on the calls made between services in the last 10 minutes"""

    async def _arun(self) -> str:
        services = await self.sw_api.find_services()
        topology = await self.sw_api.find_services_topology(services, TimeRange.from_last_minutes(10))
        return self._topology_to_markdown(topology)

    @staticmethod
    def _topology_to_markdown(topology: Topology) -> str:
        node_ids = {}
        nodes = {}
        edges = []
        for index, node in enumerate(topology.nodes):
            if node.type == "USER":
                continue
            node_id = node.name
            if re.search(r"\W", node_id):
                node_id = f"{node.type.lower() if node.type else 'node'}{index}"
            node_ids[node.id] = node_id
            nodes[node_id] = node
        for edge in topology.edges:
            if node_ids.get(edge.source):
                edges.append((node_ids[edge.source], node_ids[edge.target]))
        return templates_repo.get_template("topology-diagram-template.puml").render(nodes=nodes, edges=edges, re=re)
