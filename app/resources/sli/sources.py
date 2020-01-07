import dataclasses
import datetime
import enum
import os
from typing import Dict, Generator, List, Tuple

import dateutil.parser
import requests

LIGHTSTEP_API_KEY = os.getenv("LIGHTSTEP_API_KEY")


class SourceError(Exception):
    pass


@dataclasses.dataclass
class IndicatorValueLike:
    timestamp: datetime.datetime
    value: str


class Source:
    def get_indicator_values(
        self, from_: datetime.datetime, to: datetime.datetime
    ) -> List[IndicatorValueLike]:
        raise NotImplementedError


class ZMON(Source):
    pass


class Lightstep(Source):
    class Metric(enum.Enum):
        OPS_COUNT = "ops-counts"
        ERRORS_COUNT = "error-counts"
        LATENCY_P50 = "50"
        LATENCY_P75 = "75"
        LATENCY_P90 = "90"
        LATENCY_P99 = "99"

        @classmethod
        def from_str(cls, metric_str: str) -> "Metric":
            return cls[metric_str.upper().replace("-", "_")]

        def to_request(self) -> Dict:
            if self.name.startswith("LATENCY_"):
                return {"percentile": self.value}

            return {f"include-{self.value}": 1}

        def get_datapoints(self, response) -> Generator[Tuple[str, str], None, None]:
            attributes = response["data"]["attributes"]

            if self.name.startswith("LATENCY_"):
                for latency in attributes["latencies"]:
                    if latency["percentile"] == self.value:
                        values = latency["latency-ms"]
                        break
                else:
                    raise SourceError(
                        f"No latencies found for {self.value}th percentile in timeseries."
                    )
            else:
                values = attributes[self.value]

            return (
                (window["youngest-time"], value)
                for window, value in zip(attributes["time-windows"], values)
            )

    def __init__(self, stream_id: str, metric: str):
        self.stream_id = stream_id
        self.metric = self.Metric.from_str(metric)

    def get_indicator_values(
        self, from_: datetime.datetime, to: datetime.datetime
    ) -> List[IndicatorValueLike]:
        params = {
            "oldest-time": from_.replace(tzinfo=datetime.timezone.utc).isoformat(),
            "youngest-time": to.replace(tzinfo=datetime.timezone.utc).isoformat(),
            "resolution-ms": "600000",
            **self.metric.to_request(),
        }
        response = requests.get(
            url=f"https://api.lightstep.com/public/v0.1/Zalando/projects/Production/searches/{self.stream_id}/timeseries",
            headers={"Authorization": f"Bearer {LIGHTSTEP_API_KEY}"},
            params=params,
        )
        if response.status_code == 401:
            raise SourceError(
                "Given Lightstep API key is probably wrong. Please verify if the LIGHTSTEP_API_KEY environment variable contains a valid key."
            )
        response = response.json()
        errors = response.get("errors")
        if errors:
            raise SourceError(
                f"Something went wrong with a request to the Lightstep API: {errors}."
            )

        return [
            IndicatorValueLike(dateutil.parser.parse(timestamp_str), value)
            for timestamp_str, value in self.metric.get_datapoints(response)
        ]


_DEFAULT_SOURCE = "zmon"
_SOURCES = {"zmon": ZMON, "lightstep": Lightstep}


def from_config(config: Dict) -> Source:
    config = config.copy()
    type_ = config.pop("type", _DEFAULT_SOURCE)

    return _SOURCES[type_](**config)
