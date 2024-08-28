| Service | Load (calls/min) | Success Rate (%) | Latency (ms) | Apdex |
|---|---|---|---|---|
{% for service, metrics in service_metrics.items() -%}
|{{ service }}|{{ metrics.cpm }}|{{ metrics.sla }}|{{ metrics.resp_time }}|{{ metrics.apdex }}|
{% endfor %}

Check [Skywakling UI]({{ sw_url }}) for more details.
