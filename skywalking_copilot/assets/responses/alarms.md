{% if alarms|length > 1 %}Some alarms have{% else %}An alarm has{% endif %} been triggered:

| Time Period                       | Type           | Source       | Message |
|-----------------------------------|----------------|--------------| --- |
{% for alarm in alarms -%}
| {{ alarm.start }} - {{ alarm.end }} | {{ alarm.type }} | [{{ alarm.service_name }}]({{ alarm.service_url }}) | {{ alarm.message }} |
{%- endfor %}