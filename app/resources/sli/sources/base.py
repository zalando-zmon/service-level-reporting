import dataclasses
import datetime
from typing import Dict, List, Optional, Tuple, Union

from ..models import IndicatorValueLike


class SourceError(Exception):
    pass


class TimeRange:
    NOW = 0

    def to_relative_minutes(self) -> Tuple[int, int]:
        return NotImplementedError

    def to_datetimes(self) -> Tuple[datetime.datetime, datetime.datetime]:
        return NotImplementedError


@dataclasses.dataclass
class RelativeMinutesRange(TimeRange):
    start: Optional[int] = None
    end: int = TimeRange.NOW

    def to_relative_minutes(self) -> Tuple[int, int]:
        return self.start, self.end

    def to_datetimes(self) -> Tuple[datetime.datetime, datetime.datetime]:
        now = datetime.datetime.utcnow()
        from_dt = now - datetime.timedelta(minutes=self.start)
        to_dt = now if not self.end else now - datetime.timedelta(minutes=self.end)

        return from_dt, to_dt


@dataclasses.dataclass
class DatetimeRange(TimeRange):
    start: Optional[datetime.datetime] = None
    end: datetime.datetime = TimeRange.NOW

    def to_relative_minutes(self) -> Tuple[int, int]:
        now = datetime.datetime.utcnow()
        if self.end:
            end = (now - self.end).total_seconds() // 60
        else:
            end = self.end

        if self.start:
            start = (now - self.start).total_seconds() // 60
        else:
            start = self.start

        return start, end

    def to_datetimes(self) -> Tuple[datetime.datetime, datetime.datetime]:
        return self.start, self.end if self.end else datetime.datetime.utcnow()


TimeRange.DEFAULT = DatetimeRange()


class Source:
    @classmethod
    def validate_config(cls, config: Dict):
        raise NotImplementedError

    def get_indicator_values(
        self,
        timerange: TimeRange = TimeRange.DEFAULT,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Tuple[List[IndicatorValueLike], Optional[object]]:
        raise NotImplementedError

    def update_indicator_values(self, timerange: TimeRange = TimeRange.DEFAULT) -> int:
        raise NotImplementedError


@dataclasses.dataclass
class Pagination:
    page: int
    per_page: int
