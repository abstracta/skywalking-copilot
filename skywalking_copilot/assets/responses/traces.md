Current session generated the following traces:

| span | duration (ms) |
|------|---------------|
{% for span in spans -%}
| {{span.prefix}} <pre> {{ span.name }} </pre> | {{ span.duration }} |
{% endfor %}

Check [Skywakling UI]({{ sw_url }}) for more details.