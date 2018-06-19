import collections

import opentracing

from datetime import datetime
from dateutil.relativedelta import relativedelta

from connexion import ProblemException

from sqlalchemy.sql import text

from opentracing.ext import tags as ot_tags
from opentracing_utils import extract_span_from_flask_request, trace, extract_span_from_kwargs

from app.extensions import db
from app.libs.resource import ResourceHandler

from app.resources.product.models import Product
from app.resources.sli.models import Indicator


REPORT_TYPES = ('weekly', 'monthly', 'quarterly')


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
        current_span.set_tag('product_group', product.product_group.name)

        slo = []
        for objective in objectives:
            days = collections.defaultdict(dict)

            if not len(objective.targets):
                current_span.log_kv({'objective_skipped': True, 'objective': objective.id})
                continue

            q = text('''
                SELECT
                    date_trunc(:unit, indicatorvalue.timestamp) AS day,
                    indicator.name AS name,
                    indicator.aggregation AS aggregation,
                    MIN(indicatorvalue.value) AS min,
                    AVG(indicatorvalue.value) AS avg,
                    MAX(indicatorvalue.value) AS max,
                    COUNT(indicatorvalue.value) AS count,
                    SUM(indicatorvalue.value) AS sum,
                    (SELECT SUM(CASE b WHEN TRUE THEN 0 ELSE 1 END) FROM UNNEST(array_agg(indicatorvalue.value BETWEEN
                        COALESCE(target.target_from, :lower) AND COALESCE(target.target_to, :upper))) AS dt(b)
                    ) AS breaches
                FROM indicatorvalue
                JOIN target ON target.indicator_id = indicatorvalue.indicator_id AND target.objective_id = :objective_id
                JOIN indicator ON indicator.id = indicatorvalue.indicator_id
                WHERE indicatorvalue.timestamp >= :start AND indicatorvalue.timestamp < :now
                GROUP BY day, name, aggregation
                ''')  # noqa

            params = {
                'unit': unit, 'objective_id': objective.id, 'start': start, 'now': now, 'lower': float('-inf'),
                'upper': float('inf')
            }

            # Instrument DB query to generate a product report!
            db_query_span = opentracing.tracer.start_span(operation_name='report_db_query', child_of=current_span)
            db_query_span.set_tag('objective', objective.id)
            with db_query_span:

                for obj in db.session.execute(q, params):
                    days[obj.day.isoformat()][obj.name] = {
                        'max': obj.max, 'min': obj.min, 'avg': obj.avg, 'count': obj.count, 'breaches': obj.breaches,
                        'sum': obj.sum, 'aggregation': obj.aggregation
                    }

                slo.append(
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
