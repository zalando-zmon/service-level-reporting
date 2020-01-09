from typing import Dict, Tuple, Type

from ..models import Indicator
from .base import Source, SourceError
from .lightstep import Lightstep
from .zmon import ZMON

_DEFAULT_SOURCE = "zmon"
_SOURCES = {"zmon": ZMON, "lightstep": Lightstep}


def _get_source_cls_from_config(config: Dict) -> Tuple[Type[Source], Dict]:
    config = config.copy()
    type_ = config.pop("type", _DEFAULT_SOURCE)

    try:
        return _SOURCES[type_], config
    except KeyError:
        raise SourceError(
            f"Given source type '{type_}' is not valid. Choose one from: {_SOURCES.keys()}"
        )


def validate_config(config: Dict):
    cls, config = _get_source_cls_from_config(config)

    return cls.validate_config(config)


def from_indicator(indicator: Indicator) -> Source:
    cls, config = _get_source_cls_from_config(indicator.source)

    return cls(indicator=indicator, **config)
