import collections

import opentracing

from typing import Iterator, List, Dict

from datetime import datetime
from dateutil.relativedelta import relativedelta
from datetime_truncate import truncate

from connexion import ProblemException

from opentracing.ext import tags as ot_tags
from opentracing_utils import extract_span_from_flask_request, trace, extract_span_from_kwargs

from app.libs.resource import ResourceHandler

from app.resources.product.models import Product
from app.resources.sli.models import Indicator, IndicatorValue
from app.resources.slo.models import Objective

from app.libs.lightstep import get_stream_data


REPORT_TYPES = ('weekly', 'monthly', 'quarterly')


@trace()
def truncate_values(values: Iterator[IndicatorValue], unit='day') -> Dict[str, List[IndicatorValue]]:
    truncated = collections.defaultdict(list)

    for v in values:
        truncated[truncate(v.timestamp, unit)].append(v.value)

    return truncated


def get_report_summary(objectives: Iterator[Objective], unit: str, start: datetime, end: datetime,
                       current_span: opentracing.Span) -> List[dict]:
    summary = []

    start = truncate(start)

    for objective in objectives:
        days = collections.defaultdict(dict)

        if not len(objective.targets):
            current_span.log_kv({'objective_skipped': True, 'objective': objective.id})
            continue

        current_span.log_kv({'objective_target_count': len(objective.targets), 'objective_id': objective.id})

        # Instrument objective summary!
        objective_summary_span = opentracing.tracer.start_span(
            operation_name='report_objective_summary', child_of=current_span)
        objective_summary_span.set_tag('objective_id', objective.id)

        with objective_summary_span:
            for target in objective.targets:

                objective_summary_span.log_kv({'target_id': target.id, 'indicator_id': target.indicator_id})

                target_source_type = target.indicator.source.get('type', 'zmon')

                if target_source_type == 'lightstep':
                    stream_id = target.indicator.source.get('stream-id')
                    metric = target.indicator.source.get('metric')

                    ivs = get_stream_data(stream_id, start, end, metric)

                else:
                    ivs = (
                        IndicatorValue.query
                            .filter(IndicatorValue.indicator_id == target.indicator_id,
                                    IndicatorValue.timestamp >= start,
                                    IndicatorValue.timestamp < end)
                            .order_by(IndicatorValue.timestamp))

                try:
                    target_values_truncated = truncate_values(ivs, parent_span=objective_summary_span)
                except Exception as e:
                    print(e)

                for truncated_date, target_values in target_values_truncated.items():
                    target_form = target.target_from or float('-inf')
                    target_to = target.target_to or float('inf')

                    target_count = len(target_values)
                    target_sum = sum(target_values)
                    breaches = target_count - len([v for v in target_values if v >= target_form and v <= target_to])

                    days[truncated_date.isoformat()][target.indicator.name] = {
                        'aggregation': target.indicator.aggregation,
                        'avg': target_sum / target_count,
                        'breaches': breaches,
                        'count': target_count,
                        'max': max(target_values),
                        'min': min(target_values),
                        'sum': target_sum,
                    }

            summary.append(
                {
                    'title': objective.title,
                    'description': objective.description,
                    'id': objective.id,
                    'targets': [
                        {
                            'from': t.target_from, 'to': t.target_to, 'sli_name': t.indicator.name,
                            'unit': t.indicator.unit, 'aggregation': t.indicator.aggregation
                        }
                        for t in objective.targets
                    ],
                    'days': days
                }
            )

    return summary


class ReportResource(ResourceHandler):
    @classmethod
    @trace(span_extractor=extract_span_from_flask_request, operation_name='resource_handler', pass_span=True,
           tags={ot_tags.COMPONENT: 'flask', 'is_report': True})
    def get(cls, **kwargs) -> dict:
        current_span = extract_span_from_kwargs(**kwargs)

        report_type = kwargs.get('report_type')
        if report_type not in REPORT_TYPES:
            raise ProblemException(
                status=404, title='Resource not found',
                detail='Report type ({}) is invalid. Supported types are: {}'.format(report_type, REPORT_TYPES))

        product_id = kwargs.get('product_id')
        product = Product.query.get_or_404(product_id)

        objectives = product.objectives.all()

        now = datetime.utcnow()
        start = now - relativedelta(days=7)

        if report_type != 'weekly':
            months = 1 if report_type == 'monthly' else 3
            start = now - relativedelta(months=months)

        unit = 'day' if report_type == 'weekly' else 'week'

        current_span.set_tag('report_type', report_type)
        current_span.set_tag('product_id', product_id)
        current_span.set_tag('product', product.name)
        current_span.set_tag('product_slug', product.slug)
        current_span.set_tag('product_group', product.product_group.name)
        current_span.log_kv({'report_duration_start': start, 'report_duration_end': now})

        slo = get_report_summary(objectives, unit, start, now, current_span)

        current_span.log_kv({'report_objective_count': len(slo), 'objective_count': len(objectives)})

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
