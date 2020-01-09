import datetime
import enum
from typing import Dict, Generator, List, Optional, Tuple

import dateutil.parser
import requests

from app.config import LIGHTSTEP_API_KEY, LIGHTSTEP_RESOLUTION_SECONDS

from ..models import Indicator, IndicatorValueLike, PureIndicatorValue
from .base import DatetimeRange, Pagination, Source, SourceError, TimeRange


class _Metric(enum.Enum):
    OPS_COUNT = "ops-counts"
    ERRORS_COUNT = "error-counts"
    LATENCY_P50 = "50"
    LATENCY_P75 = "75"
    LATENCY_P90 = "90"
    LATENCY_P99 = "99"

    @classmethod
    def names(cls):
        return [metric.name.lower() for metric in cls]

    @classmethod
    def from_str(cls, metric_str: str) -> "_Metric":
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


def _paginate_timerange(
    timerange: TimeRange, page: Optional[int] = None, per_page: Optional[int] = None,
) -> Tuple[DatetimeRange, Optional[Pagination]]:
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
        metric = config.get("metric")

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

    def __init__(
        self, indicator: Indicator, stream_id: str, metric: str, aggregation: Dict
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
        response = response.json()
        errors = response.get("errors")
        if errors:
            raise SourceError(
                f"Something went wrong with a request to the Lightstep API: {errors}."
            )

        return (
            [
                PureIndicatorValue(
                    dateutil.parser.parse(timestamp_str, ignoretz=True), value
                )
                for timestamp_str, value in self.metric.get_datapoints(response)
            ],
            pagination,
        )

    def update_indicator_values(self, *_, **__) -> int:
        return 0
