from typing import Dict, Tuple, Type

from .base import Source  # noqa
from .base import (
    DatetimeRange,
    IndicatorValueAggregate,
    IndicatorValueLike,
    RelativeMinutesRange,
    Resolution,
    SourceError,
    TimeRange,
)
from .lightstep import Lightstep
from .zmon import ZMON

__all__ = [
    "validate_config",
    "from_indicator",
    "DatetimeRange",
    "RelativeMinutesRange",
    "IndicatorValueLike",
    "IndicatorValueAggregate",
    "TimeRange",
    "Resolution",
]

_DEFAULT_SOURCE = "zmon"
_SOURCES = {"zmon": ZMON, "lightstep": Lightstep}


def from_type(type_: str) -> Type[Source]:
    try:
        return _SOURCES[type_]
    except KeyError:
        raise SourceError(
            f"Given source type '{type_}' is not valid. Choose one from: {_SOURCES.keys()}"
        )


def from_config(config: Dict) -> Tuple[Type[Source], Dict]:
    config = config.copy()
    type_ = config.pop("type", _DEFAULT_SOURCE)

    return from_type(type_), config


def from_indicator(indicator: "Indicator") -> Source:
    cls, config = from_config(indicator.source)

    return cls(indicator=indicator, **config)


def validate_config(config: Dict):
    cls, final_config = from_config(config)

    return cls.validate_config(final_config)
