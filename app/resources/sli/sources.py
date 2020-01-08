import dataclasses
import datetime
import enum
import os
from typing import Dict, Generator, List, Tuple

import dateutil.parser
import requests

from app.config import LIGHTSTEP_API_KEY

from .models import Indicator, IndicatorValue, IndicatorValueLike, PureIndicatorValue


class SourceError(Exception):
    pass


@dataclasses.dataclass(frozen=True)
class GetIndicatorValuesHints:
    page: Optional[int] = None
    per_page: Optional[int] = None


_GET_INDICATOR_VALUES_HINTS_DEFAULT = GetIndicatorValuesHints()


@dataclasses.dataclass(frozen=True)
class GetIndicatorValuesMetadata:
    page: Optional[int] = None
    per_page: Optional[int] = None
    next_num: Optional[int] = None


_GET_INDICATOR_VALUES_METADATA_DEFAULT = GetIndicatorValuesMetadata()


class Source:
    @classmethod
    def validate_config(cls, config: Dict):
        raise NotImplementedError

    def get_indicator_values(
        self,
        from_: datetime.datetime,
        to: datetime.datetime,
        hints: GetIndicatorValuesHints = _GET_INDICATOR_VALUES_HINTS_DEFAULT,
    ) -> Tuple[List[IndicatorValueLike], GetIndicatorValuesMetadata]:
        raise NotImplementedError

    def update_indicator_values(self):
        raise NotImplementedError


class ZMON(Source):
    AGG_TYPES = ("average", "weighted", "sum", "min", "max", "minimum", "maximum")

    @classmethod
    def validate_config(cls, config: Dict):
        required = {"aggregation", "check_id", "keys"}
        missing = set(required) - set(config.keys())
        if missing:
            raise SourceError("SLI 'source' has missing keys: {}!".format(missing),)

        if not config["keys"]:
            raise SourceError("SLI 'source' *keys* must have a value")

        aggregation = config.get("aggregation", {})
        if not aggregation:
            raise SourceError("SLI 'source' *aggregation* must have a value",)

        agg_type = aggregation.get("type")
        if not agg_type or agg_type not in cls.AGG_TYPES:
            raise SourceError(
                "SLI 'source' aggregation type is invalid. Valid values are: {}".format(
                    cls.AGG_TYPES
                ),
            )

        if agg_type == "weighted" and not aggregation.get("weight_keys"):
            raise SourceError(
                "SLI 'source' aggregation type *weighted* must have *weight_keys*",
            )

    def __init__(self, indicator_id, check_id, keys, aggregation, weight_keys=()):
        self.indicator_id = indicator_id
        self.check_id = check_id
        self.keys = keys
        self.aggregation = aggregation
        self.weight_keys = weight_keys

    def get_indicator_values(
        self,
        from_: datetime.datetime,
        to: datetime.datetime,
        hints: GetIndicatorValuesHints = _GET_INDICATOR_VALUES_HINTS_DEFAULT,
    ) -> Tuple[List[IndicatorValue], GetIndicatorValuesMetadata]:
        query = IndicatorValue.query.filter(
            IndicatorValue.indicator_id == self.indicator_id,
            IndicatorValue.timestamp >= from_,
            IndicatorValue.timestamp < to,
        ).order_by(IndicatorValue.timestamp)
        if hints.page and hints.per_page:
            query = query.paginate(
                page=hints.page, per_page=hints.per_page, error_out=False
            )

            return (
                list(query.items),
                GetIndicatorValuesMetadata(
                    page=query.page, per_page=query.per_page, next_num=query.next_num,
                ),
            )
        else:
            return list(query.all()), _GET_INDICATOR_VALUES_METADATA_DEFAULT

    def update_indicator_values(self):
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

    def __init__(self, indicator_id: int, stream_id: str, metric: str):
        self.indicator_id = indicator_id
        self.stream_id = stream_id
        self.metric = self.Metric.from_str(metric)

    def get_indicator_values(
        self,
        from_: datetime.datetime,
        to: datetime.datetime,
        hints: GetIndicatorValuesHints = _GET_INDICATOR_VALUES_HINTS_DEFAULT,
    ) -> Tuple[List[IndicatorValueLike], GetIndicatorValuesMetadata]:
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

        return (
            [
                PureIndicatorValue(dateutil.parser.parse(timestamp_str), value)
                for timestamp_str, value in self.metric.get_datapoints(response)
            ],
            _GET_INDICATOR_VALUES_METADATA_DEFAULT,
        )

    def update_indicator_values(self):
        pass


_DEFAULT_SOURCE = "zmon"
_SOURCES = {"zmon": ZMON, "lightstep": Lightstep}


def from_indicator(indicator: Indicator) -> Source:
    config = indicator.source.copy()
    type_ = config.pop("type", _DEFAULT_SOURCE)

    try:
        cls = _SOURCES[type_]
        cls.validate_config(config)

        return cls(indicator_id=indicator.id, **config)
    except KeyError:
        raise SourceError(
            f"Given source type '{type_}' is not valid. Choose one from: {_SOURCES.keys()}"
        )
