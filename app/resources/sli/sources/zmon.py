import datetime
import fnmatch
import itertools
import math
from typing import Dict, List, Optional, Set, Tuple

import opentracing
import requests
import zign.api
from datetime_truncate import truncate as truncate_datetime
from opentracing_utils import extract_span_from_kwargs, trace
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import KAIROS_QUERY_LIMIT, KAIROSDB_URL, MAX_QUERY_TIME_SLICE
from app.extensions import db

from .base import (IndicatorValueAggregate, IndicatorValueLike, Pagination,
                   Resolution, Source, SourceError, TimeRange)

_MIN_VAL = math.expm1(1e-10)
_AGGREGATION_TYPES = ("average", "weighted", "sum", "min", "max", "minimum", "maximum")


def _key_matches(key, key_patterns):
    for pat in key_patterns:
        if fnmatch.fnmatch(key, pat):
            return True
    return False


class IndicatorValue(db.Model, IndicatorValueLike):
    __tablename__ = 'indicatorvalue'

    timestamp = db.Column(db.DateTime(), nullable=False)
    value = db.Column(db.Numeric(), nullable=False)

    indicator_id = db.Column(
        db.Integer(),
        db.ForeignKey('indicator.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        db.PrimaryKeyConstraint(
            'timestamp',
            'indicator_id',
            name='indicatorvalue_timestamp_indicator_id_pkey',
        ),
    )

    def as_dict(self):
        return {
            'timestamp': self.timestamp,
            'value': self.value,
            'indicator_id': self.indicator_id,
        }

    def update_dict(self):
        return {"value": self.value}

    def __repr__(self):
        return "<SLI value {} | {}: {}>".format(
            self.indicator.name, self.timestamp, self.value
        )


# Source: http://stackoverflow.com/questions/41636169/how-to-use-postgresqls-insert-on-conflict-upsert-feature-with-flask-sqlal  # noqa
def insert_indicator_value(session: db.Session, sli_value: IndicatorValue) -> None:
    """
    Upsert indicator value.

    Note: Does not perform ``session.commit()``.
    """
    statement = (
        pg_insert(IndicatorValue)
        .values(**sli_value.as_dict())
        .on_conflict_do_update(
            constraint='indicatorvalue_timestamp_indicator_id_pkey',
            set_=sli_value.update_dict(),
        )
    )

    session.execute(statement)


class ZMON(Source):
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
        if not agg_type or agg_type not in _AGGREGATION_TYPES:
            raise SourceError(
                "SLI 'source' aggregation type is invalid. Valid values are: {}".format(
                    _AGGREGATION_TYPES
                ),
            )

        if agg_type == "weighted" and not aggregation.get("weight_keys"):
            raise SourceError(
                "SLI 'source' aggregation type *weighted* must have *weight_keys*",
            )

    @classmethod
    def delete_all_indicator_values(self, timerange: TimeRange) -> int:
        from_dt, to_dt = timerange.to_datetimes()
        count = IndicatorValue.query.filter(
            IndicatorValue.timestamp >= from_dt, IndicatorValue.timestamp <= to_dt
        ).delete()
        db.session.commit()

        return count

    def __init__(
        self,
        indicator: "Indicator",
        check_id,
        keys,
        aggregation,
        tags=None,
        exclude_keys=(),
    ):
        self.indicator = indicator

        self.check_id = check_id
        self.keys = keys
        self.aggregation = aggregation

        self.exclude_keys = exclude_keys
        self.tags = tags or {}

    def get_indicator_values(
        self,
        timerange: TimeRange = TimeRange.DEFAULT,
        resolution: Optional[int] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Tuple[List[IndicatorValueLike], Optional[Pagination]]:
        start_dt, end_dt = timerange.to_datetimes()
        query = IndicatorValue.query.filter(
            IndicatorValue.indicator_id == self.indicator.id,
            IndicatorValue.timestamp >= start_dt,
            IndicatorValue.timestamp < end_dt,
        ).order_by(IndicatorValue.timestamp)
        if page and per_page:
            query = query.paginate(page=page, per_page=per_page, error_out=False)

            return (
                list(query.items),
                query,
            )
        else:
            return list(query.all()), None

    def get_indicator_value_aggregates(
        self, timerange: TimeRange, resolutions: Set[Resolution]
    ) -> Dict:
        values, _ = self.get_indicator_values(timerange)

        return {
            resolution: [
                IndicatorValueAggregate.from_indicator_values(
                    timestamp, list(grouped_values), self.indicator.aggregation,
                )
                for timestamp, grouped_values in itertools.groupby(
                    values,
                    lambda value: truncate_datetime(value.timestamp, resolution.unit),
                )
            ]
            for resolution in resolutions
        }

    def _get_start_relative_for_update(self) -> int:
        now = datetime.datetime.utcnow()
        newest_dt = now - datetime.timedelta(minutes=MAX_QUERY_TIME_SLICE)

        newest_iv = (
            IndicatorValue.query.with_entities(
                db.func.max(IndicatorValue.timestamp).label("timestamp")
            )
            .filter(
                IndicatorValue.timestamp >= newest_dt,
                IndicatorValue.timestamp < now,
                IndicatorValue.indicator_id == self.indicator.id,
            )
            .first()
        )
        if not getattr(newest_iv, "timestamp", None):
            return MAX_QUERY_TIME_SLICE

        return (now - newest_iv.timestamp).seconds // 60 + 5  # add some overlapping

    def _query_kairosdb(self, start, end=None):
        aggregation_type = self.aggregation["type"]
        weight_keys = self.aggregation.get("weight_keys", [])

        kairosdb_metric_name = "zmon.check.{}".format(self.check_id)

        token = zign.api.get_token("zmon", ["uid"])
        headers = {"Authorization": "Bearer {}".format(token)}

        session = requests.Session()
        session.headers.update(headers)

        tags = {"key": self.keys + weight_keys}
        if self.tags:
            tags.update(self.tags)

        q = {
            "start_relative": {"value": start, "unit": "minutes"},
            "metrics": [
                {
                    "name": kairosdb_metric_name,
                    "tags": tags,
                    "limit": KAIROS_QUERY_LIMIT,
                    "group_by": [{"name": "tag", "tags": ["entity", "key"]}],
                }
            ],
        }

        if end:
            q["end_relative"] = {"value": end, "unit": "minutes"}

        # TODO: make this part smarter.
        # If we fail with 500 then may be consider graceful retries with smaller intervals!
        response = session.post(
            KAIROSDB_URL + "/api/v1/datapoints/query", json=q, timeout=55
        )
        response.raise_for_status()

        data = response.json()

        res = {}
        for result in data["queries"][0]["results"]:
            if not result.get("values"):
                continue

            group = result["group_by"][0]["group"]
            key = group["key"]

            exclude = _key_matches(key, self.exclude_keys)

            if not exclude:
                for ts, value in result["values"]:
                    # truncate to full minutes
                    minute = datetime.datetime.utcfromtimestamp((ts // 60000) * 60)
                    if minute not in res:
                        res[minute] = {}

                    g = group["entity"], ".".join(key.split(".")[:-1])
                    if g not in res[minute]:
                        res[minute][g] = {}

                    if aggregation_type == "weighted" and _key_matches(
                        key, weight_keys
                    ):
                        res[minute][g]["weight"] = value
                    else:
                        res[minute][g]["value"] = value

        result = {}
        for minute, values in res.items():
            if aggregation_type == "weighted":
                total_weight = 0
                total_value = 0
                for g, entry in values.items():
                    if "value" in entry:
                        val = entry["value"]
                        weight = entry.get(
                            "weight", 1
                        )  # In case weight was not available!

                        total_weight += weight
                        total_value += val * weight
                if total_weight != 0:
                    result[minute] = total_value / total_weight
                else:
                    result[minute] = 0
            # TODO: aggregate in Kairosdb query?!
            elif aggregation_type == "average":
                total_value = 0
                for g, entry in values.items():
                    total_value += entry["value"]
                result[minute] = total_value / len(values)
            # TODO: aggregate in Kairosdb query?!
            elif aggregation_type == "sum":
                total_value = 0
                for g, entry in values.items():
                    total_value += entry["value"]
                result[minute] = total_value
            elif aggregation_type in ("minimum", "min"):
                result[minute] = min([entry["value"] for g, entry in values.items()])
            elif aggregation_type in ("maximum", "max"):
                result[minute] = max([entry["value"] for g, entry in values.items()])

        return result

    @trace(pass_span=True)
    def update_indicator_values(
        self, timerange: TimeRange = TimeRange.DEFAULT, **kwargs,
    ):
        start, end = timerange.to_relative_minutes()
        start = start or self._get_start_relative_for_update()
        result = self._query_kairosdb(start, end)
        if not result:
            return 0

        session = db.session
        current_span = extract_span_from_kwargs(**kwargs)
        insert_span = opentracing.tracer.start_span(
            operation_name="insert_indicator_values", child_of=current_span
        )
        (
            insert_span.set_tag("indicator", self.indicator.name).set_tag(
                "indicator_id", self.indicator.id
            )
        )
        insert_span.log_kv({"result_count": len(result)})

        with insert_span:
            for minute, val in result.items():
                if val > 0:
                    val = max(val, _MIN_VAL)
                elif val < 0:
                    val = min(val, _MIN_VAL * -1)

                iv = IndicatorValue(
                    timestamp=minute, value=val, indicator_id=self.indicator.id
                )
                insert_indicator_value(session, iv)

        session.commit()  # pylint: disable=no-member

        return len(result)
