import dataclasses
import datetime
from typing import Dict, List, Optional, Tuple, cast

from ..models import Indicator, IndicatorValueLike


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


class Pagination(object):
    per_page: int
    page: int
    next_num: int


class Source:
    @classmethod
    def validate_config(cls, config: Dict):
        raise NotImplementedError

    def __init__(self, indicator: Indicator, **kwargs):
        self.indicator = indicator

    def get_indicator_values(
        self,
        timerange: TimeRange = TimeRange.DEFAULT,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Tuple[List[IndicatorValueLike], Optional[Pagination]]:
        raise NotImplementedError

    def update_indicator_values(self, timerange: TimeRange = TimeRange.DEFAULT) -> int:
        raise NotImplementedError
