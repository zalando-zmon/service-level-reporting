<html>
<head>
    <title>Service Level Report - {{period}}</title>
    <style>
    body { font: 13px Arial, Helvetica, sans-serif; text-align: center; }
    td.value { text-align: center; }
    .sli-large { font-size: 48px; text-align: center; }
    .sli-caption { text-align: center; }
    </style>
</head>
<body>
<h1>Service Levels Report</h1>
<h2>Product Group - {{ product }}</h2>
<h2>{{period}}</h2>

{% for slo in slos %}
<h1>Service Level Objective</h1>
{{slo.title}}
<h2>Reliability Index</h2>
<table style="width:100%">
    <tr>
        {% for sli in slo.slis.values() %}
        <th class="sli-large">{{sli}}</th>
        {% endfor %}
    </tr>
    <tr>
        {% for sli in slo.slis.keys() %}
        <td class="sli-caption">{{sli}}</td>
        {% endfor %}
    </tr>
</table>

<table style="width:100%">
    <tr>
        <th>SLI</th>
        {% for sli in slo.data %}
        <th>{{sli.caption}}</th>
        {% endfor %}
    </tr>

    {% for sli in slo.slis.keys() %}
    <tr>
        <th>{{sli}}</th>
        {% for data in slo.data %}
        {% if data.slis.get(sli) %}
        <td class="value" {{ 'bgcolor="' + data.slis.get(sli).get('flag') + '"' if data.slis.get(sli).get('flag') }}>{{'%.2f'|format(data.slis.get(sli).get('value'))}}</td>
        {% endif %}
        {% endfor %}
    </tr>
    {% endfor %}
</table>

<table style="width:100%">
    <tr>
        <td bgcolor="orange">&nbsp;</td>
        <td>At least one data point failed to meet the SLO</td>
        <td bgcolor="red">&nbsp;</td>
        <td>The weighted average for the period failed to meet the SLO</td>
    </tr>
</table>
<p>
<img src="{{slo.chart}}" alt="Service Level Objective Chart" />
</p>
<p>During this period, the service failed to meet this SLO for {{slo.breaches}} minute(s)</p>

{% endfor %}
</body>
</html>
