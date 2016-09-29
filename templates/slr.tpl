<!DOCTYPE html>
<html lang="en">
<head>
    <title>Service Level Report - {{ period }}</title>
    <!-- Latest compiled and minified CSS -->
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css"
          integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u" crossorigin="anonymous">

    <!-- Optional theme -->
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap-theme.min.css"
          integrity="sha384-rHyoN1iRsVXV4nD0JutlnGaslCJuC7uwjduW9SVrLvRYooPp2bWYgmgJQIXwl/Sp" crossorigin="anonymous">

    <!-- Latest compiled and minified JavaScript -->
    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js"
            integrity="sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa"
            crossorigin="anonymous"></script>
    <link href="https://fonts.googleapis.com/css?family=Merriweather|Roboto" rel="stylesheet">
    <style>
        body {
            font-family: 'Roboto', sans-serif;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Merriweather', serif;
        }

        table.report td, th.day { text-align: center;}
        td.ok { }
        td.orange { background-color: #ffffc8; }
        td.red { background-color: #ffcece; }
        td.not-enough-samples { opacity: 0.7; }

        .sli-large { font-size: 48px; }

        .chart { text-align: center; }

    </style>
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
</head>
<body>
<div class="container-fluid">
    <div class="container">
        <div class="page-header">
            <h1>Service Levels Report</h1>
            <h3>{{ product.product_group_name }} - {{ product.name }}</h3>
            <h4>{{ period }}</h4>
        </div>
        {% for slo in slos %}
            <div class="panel panel-default">
                <div class="panel-heading">{{ slo.title }}</div>
                <div class="panel-body">
                    <h4>Reliability Index</h4>
                    <table class="table">
                        <tr>
                            {% for sli in slo.slis.keys() | sort %}
                                {% if sli != 'requests' %}
                                    <th class="sli-caption">{{ sli|sli_title }}</th>
                                {% endif %}
                            {% endfor %}
                        </tr>
                        <tr>
                            {% for sli in slo.slis.keys() | sort %}
                                {% if sli != 'requests' %}
                                    <td class="sli-large {{ 'red' if not slo.slis[sli].ok }}">{{ slo.slis[sli].avg }}</td>
                                {% endif %}
                            {% endfor %}
                        </tr>
                    </table>

                    <table class="table table-bordered report">
                        <tr>
                            <th>SLI</th>
                            {% for data in slo.data %}
                                <th class="day">{{ data.caption|sli_title }}</th>
                            {% endfor %}
                        </tr>

                        {% for sli in slo.slis.keys()|sort %}
                            <tr>
                                <th>{{ sli|sli_title }}</th>
                                {% for data in slo.data %}
                                    {% if data.slis.get(sli) %}
                                        <td class="value {{ ' '.join(data.slis.get(sli).classes) }}"
                                            title="min: {{ data.slis.get(sli).min }}, max: {{ data.slis.get(sli).max }}, breaches: {{ data.slis.get(sli).breaches }}, count: {{ data.slis.get(sli).count }}">{{ '%.2f'|format(data.slis.get(sli).avg) }} {{ data.slis.get(sli).unit }}</td>
                                    {% else %}
                                        <td></td>
                                    {% endif %}
                                {% endfor %}
                            </tr>
                        {% endfor %}
                    </table>

                    <table class="table">
                        <tr>
                            <td class="orange">&nbsp;</td>
                            <td>At least one data point failed to meet the SLO</td>
                            <td class="red">&nbsp;</td>
                            <td>The weighted average for the period failed to meet the SLO</td>
                        </tr>
                    </table>
                    <p class="chart">
                        <img src="{{ slo.chart }}" alt="Service Level Objective Chart"/>
                    </p>
                    {% if slo.breaches %}
                    <div class="alert alert-danger"><p>During this period, the service failed to meet this SLO for <strong>{{ slo.breaches }}</strong> minute(s)</p></div>
                    {% endif %}
                </div>
            </div>
        {% endfor %}
    </div>
</div>
</body>
</html>
