import requests
import os
import dateutil.parser
from datetime import datetime
from datetime_truncate import truncate

# ops-count, error-count, p99, p90, p75, p50
from app.resources import IndicatorValue


def get_individual_metric_from_stream(stream_data, position, metric):
    if metric == "ops-count":
        return stream_data["data"]["attributes"]["ops-counts"][position]
    elif metric == "error-count":
        return stream_data["data"]["attributes"]["error-counts"][position]
    return stream_data["data"]["attributes"]["latencies"][0]["latency-ms"][position]


class StreamDataPoint:
    def __init__(self, timestamp, value):
        self.timestamp = timestamp
        self.value = value


def extract_metric_from_stream(stream_data, metric):
    result = []
    data_points = stream_data['data']['attributes']['points-count']
    for i in range(0, data_points):

        timestamp = truncate(dateutil.parser.parse(stream_data["data"]["attributes"]["time-windows"][i]["youngest-time"]), 'second').replace(tzinfo=None)
        value = get_individual_metric_from_stream(stream_data, i, metric)
        result.append(IndicatorValue(timestamp=timestamp, value=value))
    return result


def get_api_params_for_metric(metric):
    if metric == "ops-count":
        return {
            "include-ops-counts": "1"
        }
    elif metric == "error-count":
        return {
            "include-error-counts": "1"
        }
    elif metric == "p50":
        return {
            "percentile": "50"
        }
    elif metric == "p75":
        return {
            "percentile": "75"
        }
    elif metric == "p90":
        return {
            "percentile": "90"
        }
    elif metric == "p99":
        return {
            "percentile": "99"
        }


def get_stream_data(stream_id, timestamp_start: datetime, timestamp_end: datetime, metric):
    timestamp_start_iso = timestamp_start.replace(microsecond=0).isoformat() + "Z"
    timestamp_end_iso = timestamp_end.replace(microsecond=0).isoformat() + "Z"

    params = {**{
        "oldest-time": timestamp_start_iso,
        "youngest-time": timestamp_end_iso,
        "resolution-ms": "600000",
    # Lightstep has an internal server error at a resolution of 60000, for more than 2 days
        "include-ops-counts": "1" if metric == "ops-count" else "0",
        "percentile": "90",
        "include-error-counts": "1"
    }, **get_api_params_for_metric(metric)}

    response = requests.request(
        "GET",
        url=f"https://api.lightstep.com/public/v0.1/Zalando/projects/Production/searches/{stream_id}/timeseries",
        headers={
            "Authorization": f'Bearer {os.getenv("LIGHTSTEP_API_KEY")}'
        },
        params=params
    )
    response_json = response.json()
    errors = response_json.get('errors', None)
    if errors:
        raise Exception('Lightstep returned errors', errors)

    return extract_metric_from_stream(response_json, metric)


if __name__ == '__main__':
    try:
        result = get_stream_data("yNzld3jn", "2019-11-01T00:00:00Z", "2019-11-03T00:00:00Z", "ops-count")
        print(result)
    except KeyboardInterrupt:
        pass
