import dataclasses
import datetime
from typing import Dict, List, Optional, Tuple

from ..models import IndicatorValueLike


class SourceError(Exception):
    pass


class Source:
    @classmethod
    def validate_config(cls, config: Dict):
        raise NotImplementedError

    def get_indicator_values(
        self,
        from_: datetime.datetime,
        to: datetime.datetime,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Tuple[List[IndicatorValueLike], Optional[object]]:
        raise NotImplementedError

    def update_indicator_values(self) -> int:
        raise NotImplementedError


@dataclasses.dataclass
class Pagination:
    page: int
    per_page: int
