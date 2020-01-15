import datetime
import enum
from decimal import Decimal
from typing import Dict, Generator, List, Optional, Tuple

import dateutil.parser
import requests

from app.config import LIGHTSTEP_API_KEY, LIGHTSTEP_RESOLUTION_SECONDS

from ..models import Indicator, IndicatorValueLike, PureIndicatorValue
from .base import DatetimeRange, Pagination, Source, SourceError, TimeRange

_AGGREGATION_TYPES = ("average", "sum", "min", "max", "minimum", "maximum")


class _MetricImpl:
    def to_request(self) -> Dict:
        raise NotImplementedError

    def from_response(self, attributes: Dict) -> List[Decimal]:
        raise NotImplementedError


class _Latency(_MetricImpl):
    def __init__(self, percentile: str):
        self.percentile = percentile

    def to_request(self) -> Dict:
        return {"percentile": self.percentile}

    def from_response(self, attributes: Dict) -> List[Decimal]:
        for latency_dict in attributes["latencies"]:
            if latency_dict["percentile"] == self.percentile:
                return [Decimal(latency) for latency in latency_dict["latency-ms"]]

        return []


class _OperationRate(_MetricImpl):
    def to_request(self) -> Dict:
        return {"include-ops-counts": 1}

    def from_response(self, attributes: Dict) -> List[Decimal]:
        return [
            Decimal(ops_count) / int(LIGHTSTEP_RESOLUTION_SECONDS)
            for ops_count in attributes["ops-counts"]
        ]


class _ErrorPercentage(_MetricImpl):
    def to_request(self) -> Dict:
        return {"include-ops-counts": 1, "include-error-counts": 1}

    def from_response(self, attributes: Dict) -> List[Decimal]:
        return [
            Decimal(error_count) / Decimal(ops_count)
            for ops_count, error_count in zip(
                attributes["ops-counts"], attributes["error-counts"]
            )
        ]


class _RawCount(_MetricImpl):
    def __init__(self, name: str):
        self.name = name

    def to_request(self) -> Dict:
        return {f"include-{self.name}": 1}

    def from_response(self, attributes: Dict) -> List[Decimal]:
        return [Decimal(count) for count in attributes[self.name]]


class _Metric(enum.Enum):
    OPERATION_COUNT = _RawCount("ops-counts")
    OPERATION_RATE = _OperationRate()
    ERROR_COUNT = _RawCount("error-counts")
    ERROR_PERCENTAGE = _ErrorPercentage()
    LATENCY_P50 = _Latency("50")
    LATENCY_P75 = _Latency("75")
    LATENCY_P90 = _Latency("90")
    LATENCY_P99 = _Latency("99")

    @classmethod
    def names(cls):
        return [metric.name.lower() for metric in cls]

    @classmethod
    def from_str(cls, metric_str: str) -> "_Metric":
        return cls[metric_str.upper().replace("-", "_")]

    def to_request(self) -> Dict:
        return self.value.to_request()

    def get_datapoints(self, response) -> List[Tuple[str, Decimal]]:
        attributes = response["data"]["attributes"]
        values = self.value.from_response(attributes)

        return [
            (window["youngest-time"], value)
            for window, value in zip(attributes["time-windows"], values)
        ]


def _paginate_timerange(
    timerange: TimeRange, page: Optional[int] = None, per_page: Optional[int] = None,
) -> Tuple[TimeRange, Optional[Pagination]]:
    if not page or not per_page:
        return timerange, None

    start_dt, end_dt = timerange.to_datetimes()
    delta_seconds = (end_dt - start_dt).total_seconds()
    start_dt = start_dt + datetime.timedelta(
        seconds=(page - 1) * per_page * LIGHTSTEP_RESOLUTION_SECONDS
    )
    end_dt = start_dt + datetime.timedelta(
        seconds=LIGHTSTEP_RESOLUTION_SECONDS * per_page
    )

    total_count = delta_seconds / LIGHTSTEP_RESOLUTION_SECONDS
    current_count = page * per_page
    pagination = Pagination()
    pagination.per_page = per_page
    if page > 1:
        pagination.page = page
    if current_count < total_count:
        pagination.next_num = page + 1

    return DatetimeRange(start_dt, end_dt), pagination


class Lightstep(Source):
    @classmethod
    def validate_config(cls, config: Dict):
        stream_id = config.get("stream_id")
        metric = str(config.get("metric"))
        aggregation_type = config.get("aggregation", {}).get("type")

        if not stream_id:
            raise SourceError(
                "LightStep stream ID is required, but was not provided or is empty. "
                "Please provide a valid LightStep stream ID in the 'stream_id' property of the source configuration."
            )
        try:
            _Metric.from_str(metric)
        except:  # noqa
            raise SourceError(
                "Metric name for the LightStep source is not correct. "
                "Please provide a valid metric name in the 'metric' property of the source configuration. "
                f"Current value is {metric!r} whereas the valid choices are: {', '.join(_Metric.names())}. "
            )

        if aggregation_type and (aggregation_type not in _AGGREGATION_TYPES):
            raise SourceError(
                "Provided aggregation type is not supported for LightStep. "
                f"Current value is {aggregation_type!r} whereas the valid choices are: {', '.join(_AGGREGATION_TYPES)}."
            )

    def __init__(
        self,
        indicator: Indicator,
        stream_id: str,
        metric: str,
        aggregation: Optional[Dict] = None,
    ):
        self.indicator = indicator
        self.stream_id = stream_id
        self.metric = _Metric.from_str(metric)
        self.aggregation = aggregation

    def get_indicator_values(
        self,
        timerange: TimeRange = TimeRange.DEFAULT,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Tuple[List[IndicatorValueLike], Optional[Pagination]]:
        timerange, pagination = _paginate_timerange(timerange, page, per_page)
        start_dt, end_dt = timerange.to_datetimes()

        params = {
            "oldest-time": start_dt.replace(tzinfo=datetime.timezone.utc).isoformat(),
            "youngest-time": end_dt.replace(tzinfo=datetime.timezone.utc).isoformat(),
            "resolution-ms": str(LIGHTSTEP_RESOLUTION_SECONDS * 1000),
            **self.metric.to_request(),
        }
        url = f"https://api.lightstep.com/public/v0.1/Zalando/projects/Production/searches/{self.stream_id}/timeseries"
        response = requests.get(
            url=url,
            headers={"Authorization": f"Bearer {LIGHTSTEP_API_KEY}"},
            params=params,
        )
        if response.status_code == 401:
            raise SourceError(
                "Given Lightstep API key is probably wrong. "
                "Please verify if the LIGHTSTEP_API_KEY environment variable contains a valid key."
            )
        response_dict = response.json()
        errors = response_dict.get("errors")
        if errors:
            raise SourceError(
                f"Something went wrong with a request to the Lightstep API: {errors}."
            )

        return (
            [
                PureIndicatorValue(
                    dateutil.parser.parse(timestamp_str, ignoretz=True), value
                )
                for timestamp_str, value in self.metric.get_datapoints(response_dict)
            ],
            pagination,
        )

    def update_indicator_values(self, *_, **__) -> int:
        return 0
