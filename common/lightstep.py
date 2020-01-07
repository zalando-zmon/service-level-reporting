import enum
import os
from typing import Dict, List, Tuple, Union

import dateutil.parser
import requests


class Metric(enum.Enum):
    OPS = "ops-counts"
    ERRORS = "error-counts"
    LATENCY_P50 = "50"
    LATENCY_P75 = "75"
    LATENCY_P90 = "90"
    LATENCY_P99 = "99"

    def to_request(self) -> Dict:
        if self.name.startswith("LATENCY_"):
            return {"percentile": self.value}

        return {f"include-{self.value}": 1}

    def datapoints(self, timeseries: dict):
        attributes = timeseries["attributes"]

        if self is self.OPS or self is self.ERRORS:
            values = attributes[self.value]
        else:
            for latency in attributes["latencies"]:
                if latency["percentile"] == self.value:
                    values = latency["latency-ms"]
                    break
            else:
                raise ValueError(
                    f"No latencies for {self.value}th percentile in timeseries."
                )

        timestamps = [
            pendulum.parse(time_window["youngest-time"])
            for time_window in attributes["time-windows"]
        ]

        return timestamps


# class StreamDataPoint:
#     def __init__(self, timestamp, value):
#         self.timestamp = timestamp
#         self.value = value¬


# def extract_metric_from_stream(stream_data, metric):
#     result = []
#     data_points = stream_data["data"]["attributes"]["points-count"]
#     for i in range(data_points):
#         timestamp = truncate(
#             dateutil.parser.parse(
#                 stream_data["data"]["attributes"]["time-windows"][i]["youngest-time"]
#             ),
#             "second",
#         ).replace(tzinfo=None)
#         value = get_individual_metric_from_stream(stream_data, i, metric)
#         result.append(StreamDataPoint(timestamp=timestamp, value=value))
#     return result
