import requests
import os
import dateutil.parser


# ops-count, error-count, p99, p90, p75, p50


def get_individual_metric_from_stream(stream_data, position, metric):
    if metric == "ops-count":
        return stream_data["data"]["attributes"]["ops-counts"][position]
    elif metric == "error-count":
        return stream_data["data"]["attributes"]["error-counts"][position]
    return stream_data["data"]["attributes"]["latencies"][position]


def extract_metric_from_stream(stream_data, metric):
    result = []
    data_points = stream_data['data']['attributes']['points-count']
    for i in range(0, data_points):
        result.append({
            "timestamp": dateutil.parser.parse(stream_data["data"]["attributes"]["time-windows"][i]["youngest-time"]),
            "value": get_individual_metric_from_stream(stream_data, i, metric)
        })
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


def get_stream_data(stream_id, timestampStart, timestampEnd, metric):
    params = {**{
            "oldest-time": timestampStart,
            "youngest-time": timestampEnd,
            "resolution-ms": "60000",
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
    return extract_metric_from_stream(response_json, metric)


if __name__ == '__main__':
    try:
        result = get_stream_data("yNzld3jn", "2019-11-01T00:00:00Z", "2019-11-03T00:00:00Z", "ops-count")
        print(result)
    except KeyboardInterrupt:
        pass
