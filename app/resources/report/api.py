import collections
from datetime import datetime
from typing import Dict, Iterator, List, Set, Tuple

import opentracing
from connexion import ProblemException
from datetime_truncate import truncate as truncate_datetime
from dateutil.relativedelta import relativedelta
from opentracing.ext import tags as ot_tags
from opentracing_utils import (
    extract_span_from_flask_request,
    extract_span_from_kwargs,
    trace,
)

from app.libs.resource import ResourceHandler
from app.resources.product.models import Product
from app.resources.sli import sources
from app.resources.sli.models import Indicator
from app.resources.slo.models import Objective

REPORT_TYPES = ('weekly', 'monthly', 'quarterly')


def get_report_params(report_type,) -> Tuple[sources.DatetimeRange, sources.Resolution]:
    to_dt = datetime.utcnow()
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


def get_report_summary(
    objectives: Iterator[Objective],
    aggregates: Dict[
        Indicator, Dict[sources.Resolution, List[sources.IndicatorValueAggregate]]
    ],
    resolution: sources.Resolution,
    current_span: opentracing.Span,
) -> List[dict]:
    summary = []

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

            for target in objective.targets:
                objective_summary_span.log_kv(
                    {'target_id': target.id, 'indicator_id': target.indicator_id}
                )

                target_from = target.target_from or float('-inf')
                target_to = target.target_to or float('inf')
                target_aggregates = aggregates[target.indicator]
                for aggregate in target_aggregates[resolution]:
                    timestamp_str = aggregate.timestamp.isoformat()
                    aggregate_dict = aggregate.as_dict()
                    aggregate_dict['breaches'] = sum(
                        1
                        for iv in aggregate.indicator_values
                        if target_from > iv.value > target_to
                    )
                    days[timestamp_str][target.indicator.name] = aggregate_dict

                total.setdefault(
                    target.indicator.name,
                    target_aggregates[sources.Resolution.TOTAL].as_dict(),
                )

            summary.append(
                {
                    'title': objective.title,
                    'description': objective.description,
                    'id': objective.id,
                    'targets': [
                        {
                            'from': t.target_from,
                            'to': t.target_to,
                            'sli_name': t.indicator.name,
                            'unit': t.indicator.unit,
                            'aggregation': t.indicator.aggregation,
                        }
                        for t in objective.targets
                    ],
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

        timerange, resolution = get_report_params(report_type)

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

        aggregates = {
            indicator: sources.from_indicator(indicator).get_indicator_value_aggregates(
                timerange, resolution
            )
            for indicator in product.indicators.all()
        }
        objectives = product.objectives.all()

        slo = get_report_summary(objectives, aggregates, resolution, current_span)

        current_span.log_kv(
            {'report_objective_count': len(slo), 'objective_count': len(objectives)}
        )

        return {
            'product_name': product.name,
            'product_slug': product.slug,
            'product_group_name': product.product_group.name,
            'product_group_slug': product.product_group.slug,
            'department': product.product_group.department,
            'slo': slo,
        }

    def build_resource(self, obj: Indicator, **kwargs) -> dict:
        resource = super().build_resource(obj)

        return resource
