import dataclasses
import datetime
import enum
from decimal import Decimal
from typing import Dict, List, NamedTuple, Optional, Set, Tuple, Union, cast


class SourceError(Exception):
    pass


class TimeRange:
    DEFAULT: "TimeRange"

    def to_relative_minutes(self) -> Tuple[Optional[int], int]:
        return NotImplementedError  # type: ignore

    def to_datetimes(self) -> Tuple[datetime.datetime, datetime.datetime]:
        return NotImplementedError  # type: ignore


@dataclasses.dataclass
class RelativeMinutesRange(TimeRange):
    start: Optional[int] = None
    end: Optional[int] = None

    def to_relative_minutes(self) -> Tuple[Optional[int], int]:
        return self.start, self.end or 0

    def to_datetimes(self) -> Tuple[datetime.datetime, datetime.datetime]:
        now = datetime.datetime.utcnow()
        from_dt = now
        if self.start:
            from_dt -= datetime.timedelta(minutes=float(self.start))
        to_dt = now if not self.end else now - datetime.timedelta(minutes=self.end)

        return from_dt, to_dt


@dataclasses.dataclass
class DatetimeRange(TimeRange):
    start: Optional[datetime.datetime] = None
    end: Optional[datetime.datetime] = None

    def to_relative_minutes(self) -> Tuple[Optional[int], int]:
        now = datetime.datetime.utcnow()
        start: Optional[int]

        if self.end:
            end = int((now - self.end).total_seconds() / 60)
        else:
            end = 0

        if self.start:
            start = int((now - self.start).total_seconds() / 60)
        else:
            start = None

        return start, end

    def to_datetimes(self) -> Tuple[datetime.datetime, datetime.datetime]:
        from_dt = self.start if self.start else datetime.datetime.min
        to_dt = self.end if self.end else datetime.datetime.utcnow()

        return from_dt, to_dt


TimeRange.DEFAULT = DatetimeRange()


class Resolution(enum.Enum):
    DAILY = (86400, 'day')
    WEEKLY = (604800, 'week')
    TOTAL = None

    @property
    def seconds(self):
        return self.value[0]

    @property
    def unit(self):
        return self.value[1]


class Aggregation(enum.Enum):
    AVERAGE = 'average'
    COUNT = 'count'
    MIN = MINIMUM = 'min'
    MAX = MAXIMUM = 'max'
    SUM = 'sum'


class IndicatorValueLike:
    timestamp: datetime.datetime
    value: Decimal

    def __init__(self, timestamp: datetime.datetime, value: Decimal, **kwargs):
        self.timestamp = timestamp
        self.value = value

    def as_dict(self):
        raise NotImplementedError


@dataclasses.dataclass
class PureIndicatorValue(IndicatorValueLike):
    timestamp: datetime
    value: Decimal

    def as_dict(self):
        return dataclasses.asdict(self)


@dataclasses.dataclass
class IndicatorValueAggregate:
    timestamp: datetime.datetime
    aggregate: Union[Decimal, float]
    aggregation: Optional[Aggregation] = None
    average: Optional[Decimal] = None
    count: Optional[Decimal] = None
    max: Optional[Decimal] = None
    min: Optional[Decimal] = None
    sum: Optional[Decimal] = None
    indicator_values: Optional[List[IndicatorValueLike]] = None

    @classmethod
    def from_indicator_value(cls, indicator_value):
        return cls(timestamp=indicator_value.timestamp, aggregate=indicator_value.value)

    @classmethod
    def from_indicator_values(
        cls, timestamp: datetime.datetime, aggregation, indicator_values
    ):
        values: List[Decimal] = [
            indicator_value.value for indicator_value in indicator_values
        ]
        sum_ = sum(values)
        count = len(values)
        summary = {
            "sum": sum_,
            "count": count,
            "average": sum_ / count,
            "max": max(values),
            "min": min(values),
        }

        return cls(
            timestamp=timestamp,
            aggregation=aggregation,
            aggregate=summary[aggregation],
            indicator_values=indicator_values,
            **summary,  # type: ignore
        )

    def as_dict(self):
        return dataclasses.asdict(self)


class Pagination(object):
    per_page: int
    page: int
    next_num: int


class Source:
    @classmethod
    def validate_config(cls, config: Dict):
        raise NotImplementedError

    @classmethod
    def delete_all_indicator_values(cls, timerange: TimeRange) -> int:
        raise NotImplementedError

    def __init__(self, indicator: "Indicator", **kwargs):
        self.indicator = indicator

    def get_indicator_value_aggregates(
        self, timerange: TimeRange, resolutions: Set[Resolution]
    ) -> Dict:
        raise NotImplementedError

    def get_indicator_values(
        self,
        timerange: TimeRange = TimeRange.DEFAULT,
        resolution: Optional[int] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Tuple[List[IndicatorValueLike], Optional[Pagination]]:
        raise NotImplementedError

    def update_indicator_values(self, timerange: TimeRange = TimeRange.DEFAULT) -> int:
        raise NotImplementedError
