```echarts
{
  "title": {
    "text": {{ title|json }},
    "textStyle": {
      "fontSize": 12
    }
  },
  "legend": {
    "top": 15
  },
  "grid": {
    "top": {% if legends %}60{% else %}40{% endif %},
    "left": 20,
    "right": 20,
    "bottom": 20
  },
  "tooltip": {
    "trigger": "axis"
  },
  "xAxis": {
    "data": {{ x_vals|json }},
    "axisLabel": {
      "formatter": "formatTime"
    },
    "axisPointer": {
      "label": {
        "formatter": "formatTime"
      }
    }
  },
  "yAxis": {
    "type": "value"
  },
  "series": [
    {% for serie in series -%}
    {
      "type": "line",
      {% if serie.name %}"name": {{ serie.name|json }},
      {% endif %}"data": {{ serie.data|json }}
    }{{ ", " if not loop.last else "" }}
    {% endfor -%}
  ]
}
```