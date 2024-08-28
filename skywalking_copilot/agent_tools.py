import re
from enum import Enum
from typing import Optional, List, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from skywalking_copilot.skywalking import SkywalkingApi, TimeRange, Topology, ServiceMetric, Service
from skywalking_copilot.templates import solve_template


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
        service_metrics = await self.sw_api.find_services_summary_metrics(services, TimeRange.from_last_minutes(10))
        return solve_template("services-metrics-template.md",
                              {"service_metrics": service_metrics, "sw_url": self.sw_api.services_url})


class ServicesTopologyTool(AgentTool):
    name = "get_services_topology"
    description = """gets a diagram with the topology of services showing how are they connected.
    This information is based on the calls made between services in the last 10 minutes"""

    async def _arun(self) -> str:
        services = await self.sw_api.find_services()
        topology = await self.sw_api.find_services_topology(services, TimeRange.from_last_minutes(10))
        return self._topology_to_markdown(topology)

    def _topology_to_markdown(self, topology: Topology) -> str:
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
        return solve_template("services-topology-template.md", {"nodes": nodes, "edges": edges, "sw_url": self.sw_api.services_url})


class ServiceMetricId(Enum):
    RESPONSE_TIME_AVERAGE = "response_time_average"
    RESPONSE_TIME_PERCENTILES = "response_time_percentiles"
    APDEX = "apdex"
    LOAD = "load"
    SUCCESS_RATE = "success_rate"
    QUEUE_CONSUME_COUNT = "queue_consume_count"
    QUEUE_AVERAGE_CONSUME_LATENCY = "queue_avg_consume_latency"


class ServiceMetricArgs(BaseModel):
    service_name: str = Field(description="The name of the service to get the metrics from")
    metric: ServiceMetricId = Field(description="The metric to show in the chart")


class MetricChart:

    def __init__(self, title: str, unit: Optional[str], expression: str):
        self.title = title
        self.unit = unit
        self.expression = expression

    def to_markdown(self, data: List[ServiceMetric], service_url: str) -> str:
        x_vals = sorted(set([int(value.id) for metric in data for value in metric.values]))
        series = []
        legends = []
        for metric in data:
            vals_idx = 0
            y_vals = []
            for x_val in x_vals:
                point = metric.values[vals_idx] if vals_idx < len(metric.values) else None
                if point and x_val == int(point.id):
                    y_vals.append(float(point.value) if point.value else None)
                    vals_idx += 1
                else:
                    y_vals.append(None)
            serie = {"data": y_vals}
            if metric.labels:
                serie["name"] = metric.labels[0]
                legends.append(metric.labels[0])
            series.append(serie)
        return solve_template("service-metric-chart-template.md",
                              {"title": self.title + (f" ({self.unit})" if self.unit else ""), "unit": self.unit,
                               "x_vals": x_vals, "legends": legends, "series": series, "sw_url": service_url})


metrics_charts = {
    ServiceMetricId.RESPONSE_TIME_AVERAGE: MetricChart("Avg Response Time", "ms", "service_resp_time"),
    ServiceMetricId.RESPONSE_TIME_PERCENTILES: MetricChart("Response Time Percentiles", "ms",
                                                           "service_percentile{p='50,75,90,95,99'}"),
    ServiceMetricId.APDEX: MetricChart("Apdex", None, "service_apdex/10000"),
    ServiceMetricId.LOAD: MetricChart("Load", "calls/min", "service_cpm"),
    ServiceMetricId.SUCCESS_RATE: MetricChart("Success Rate", "%", "service_sla/100"),
    ServiceMetricId.QUEUE_CONSUME_COUNT: MetricChart("Message Queue Consuming Count", None, "service_mq_consume_count"),
    ServiceMetricId.QUEUE_AVERAGE_CONSUME_LATENCY: MetricChart("Message Queue Consuming Latency", None,
                                                               "service_mq_consume_latency"),
}


class ServiceMetricChartTool(AgentTool):
    name = "get_service_metric_chart"
    description = "gets a chart showing the values of a particular metric and service in the last 10 minutes."
    args_schema: Type[BaseModel] = ServiceMetricArgs

    async def _arun(self, service_name: str, metric: ServiceMetricId) -> str:
        services = await self.sw_api.find_services()
        candidates = [service for service in services if service_name == service.name]
        services = candidates if candidates else [service for service in services if service_name in service.name]
        if not services:
            return f"Service {service_name} not found. Check the list of services and try again"
        if len(services) > 1:
            return (f"The following services where found containing '{service_name}': "
                    f"{','.join(service.shortName for service in services)}. "
                    f"Please specify which one do you want to get the metrics from.")
        metric_chart = metrics_charts.get(metric)
        if not metric_chart:
            return (f"Metric `{metric}` not known. The list of available metrics is: "
                    f"{', '.join([metric.value for metric in metrics_charts.keys()])}.")
        result = await self.sw_api.find_services_metrics(services, {metric.value: metric_chart.expression},
                                                         TimeRange.from_last_minutes(10))
        service_metrics = next(iter(result.values()))
        data = next(iter(service_metrics.values()))
        return metric_chart.to_markdown(data, self.sw_api.get_service_url(services[0]))
