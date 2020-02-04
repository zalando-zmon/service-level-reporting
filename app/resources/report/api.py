import collections
from datetime import datetime
from typing import Iterator, List, Tuple

import dateutil.parser
import opentracing
from connexion import ProblemException
from datetime_truncate import truncate as truncate_datetime
from dateutil.relativedelta import relativedelta
from opentracing.ext import tags as ot_tags
from opentracing_utils import (extract_span_from_flask_request,
                               extract_span_from_kwargs, trace)
from sqlalchemy.orm import joinedload

from app.libs.resource import ResourceHandler
from app.resources.product.models import Product
from app.resources.sli import sources
from app.resources.sli.models import Indicator
from app.resources.slo.models import Objective

REPORT_TYPES = ('weekly', 'monthly', 'quarterly')


def get_report_params(
    report_type, to_dt=None,
) -> Tuple[sources.DatetimeRange, sources.Resolution]:
    if report_type == "weekly":
        from_dt = to_dt - relativedelta(days=7)
        resolution = sources.Resolution.DAILY
    elif report_type == "monthly":
        from_dt = to_dt - relativedelta(months=1)
        resolution = sources.Resolution.WEEKLY
    elif report_type == "quarterly":
        from_dt = to_dt - relativedelta(months=3)
        resolution = sources.Resolution.WEEKLY

    return sources.DatetimeRange(truncate_datetime(from_dt), to_dt), resolution


def get_target_healthiness(target, aggregate, metric):
    target_data = {"breaches": None}
    target_from = target.target_from or float('-inf')
    target_to = target.target_to or float('inf')

    metric_value = getattr(aggregate, metric, None) or aggregate.aggregate
    target_data["healthy"] = target_from <= metric_value <= target_to

    if aggregate.indicator_values:
        target_data["breaches"] = sum(
            1
            for iv in aggregate.indicator_values
            if iv.value > target_to or iv.value < target_from
        )

    target_data["unit"] = target.indicator.unit

    return target_data


def get_report_summary(
    objectives: Iterator[Objective],
    timerange: sources.TimeRange,
    resolution: sources.Resolution,
    current_span: opentracing.Span,
) -> List[dict]:
    summary = []
    aggregates = {}

    for objective in objectives:
        if not len(objective.targets):
            current_span.log_kv({'objective_skipped': True, 'objective': objective.id})
            continue

        current_span.log_kv(
            {
                'objective_target_count': len(objective.targets),
                'objective_id': objective.id,
            }
        )

        # Instrument objective summary!
        objective_summary_span = opentracing.tracer.start_span(
            operation_name='report_objective_summary', child_of=current_span
        )
        objective_summary_span.set_tag('objective_id', objective.id)

        with objective_summary_span:
            days = collections.defaultdict(dict)
            total = {}
            targets = []

            for target in objective.targets:
                objective_summary_span.log_kv(
                    {'target_id': target.id, 'indicator_id': target.indicator_id}
                )

                if target.indicator not in aggregates:
                    aggregates[target.indicator] = sources.from_indicator(
                        target.indicator
                    ).get_indicator_value_aggregates(timerange, resolution)
                target_aggregates = aggregates[target.indicator]
                for aggregate in target_aggregates[resolution]:
                    timestamp_str = aggregate.timestamp.isoformat()
                    aggregate_dict = aggregate.as_dict()
                    aggregate_dict.update(
                        get_target_healthiness(target, aggregate, "avg")
                    )

                    days[timestamp_str][target.indicator.name] = aggregate_dict

                total_aggregate = target_aggregates[sources.Resolution.TOTAL]
                if total_aggregate:
                    total_aggregate_dict = total_aggregate.as_dict()
                    total_aggregate_dict.update(
                        get_target_healthiness(target, total_aggregate, "aggregate")
                    )
                    total[target.indicator.name] = total_aggregate_dict

                targets.append(
                    {
                        'from': target.target_from,
                        'to': target.target_to,
                        'sli_name': target.indicator.name,
                        'unit': target.indicator.unit,
                        'aggregation': target.indicator.aggregation,
                    }
                )

            summary.append(
                {
                    'title': objective.title,
                    'description': objective.description,
                    'id': objective.id,
                    'targets': targets,
                    'days': days,
                    'total': total,
                }
            )

    return summary


class ReportResource(ResourceHandler):
    @classmethod
    @trace(
        span_extractor=extract_span_from_flask_request,
        operation_name='resource_handler',
        pass_span=True,
        tags={ot_tags.COMPONENT: 'flask', 'is_report': True},
    )
    def get(cls, **kwargs) -> dict:
        current_span = extract_span_from_kwargs(**kwargs)

        report_type = kwargs.get('report_type')
        if report_type not in REPORT_TYPES:
            raise ProblemException(
                status=404,
                title='Resource not found',
                detail='Report type ({}) is invalid. Supported types are: {}'.format(
                    report_type, REPORT_TYPES
                ),
            )

        product_id = kwargs.get('product_id')
        product = Product.query.get_or_404(product_id)

        to_str = kwargs.get('period_to')
        if to_str:
            try:
                to_dt = dateutil.parser.parse(to_str, ignoretz=True)
            except:  # noqa
                raise ProblemException(
                    status=400,
                    title='Invalid time range.',
                    detail='Invalid format of "period_to" datetime.',
                )
        else:
            to_dt = datetime.utcnow()
        timerange, resolution = get_report_params(report_type, to_dt)

        current_span.set_tag('report_type', report_type)
        current_span.set_tag('product_id', product_id)
        current_span.set_tag('product', product.name)
        current_span.set_tag('product_slug', product.slug)
        current_span.set_tag('product_group', product.product_group.name)
        current_span.log_kv(
            {
                'report_duration_start': timerange.start,
                'report_duration_end': timerange.end,
            }
        )

        objectives = product.objectives.options(joinedload(Objective.targets)).all()

        slo = get_report_summary(objectives, timerange, resolution, current_span)

        current_span.log_kv(
            {'report_objective_count': len(slo), 'objective_count': len(objectives)}
        )

        return {
            'product_name': product.name,
            'product_slug': product.slug,
            'product_group_name': product.product_group.name,
            'product_group_slug': product.product_group.slug,
            'department': product.product_group.department,
            'timerange': {
                'start': timerange.start,
                'end': timerange.end,
                'delta_seconds': timerange.delta_seconds(),
            },
            'slo': slo,
        }

    def build_resource(self, obj: Indicator, **kwargs) -> dict:
        resource = super().build_resource(obj)

        return resource
