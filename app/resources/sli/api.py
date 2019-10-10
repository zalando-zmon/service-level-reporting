from typing import List, Tuple, Union
from urllib.parse import urljoin

from datetime import datetime, timedelta

from flask_sqlalchemy import BaseQuery, Pagination

from connexion import ProblemException, request

from opentracing.ext import tags as ot_tags
from opentracing_utils import extract_span_from_flask_request, trace, extract_span_from_kwargs

from app.extensions import db
from app.libs.zmon import AGG_TYPES
from app.libs.resource import ResourceHandler
from app.libs.authorization import Authorization
from app.utils import slugger

from app.resources.product.models import Product
from app.resources.product.api import ProductResource

from .models import Indicator, IndicatorValue
from .updater import update_indicator_values

from app.libs.lightstep import get_stream_data

from dateutil.relativedelta import relativedelta


class SLIResource(ResourceHandler):
    model_fields = ('name', 'slug', 'source', 'unit', 'aggregation', 'created', 'updated', 'username')

    @property
    def authorization(self):
        return Authorization()

    @staticmethod
    def get_uri_from_id(obj_id: Union[str, int], **kwargs) -> str:
        product_id = kwargs.get('product_id')
        return urljoin(request.api_url, 'products/{}/sli/{}'.format(product_id, obj_id))

    def get_query(self, product_id: int, **kwargs) -> BaseQuery:
        return Indicator.query.filter_by(product_id=product_id, is_deleted=False)

    def get_filter_kwargs(self, **kwargs) -> dict:
        """Return relevant filters"""
        filters = {}

        if 'name' in kwargs:
            filters['slug'] = slugger(kwargs['name'])

        return filters

    def validate(self, sli: dict, **kwargs) -> None:
        if not sli or not sli.get('name'):
            raise ProblemException(title='Invalid SLI', detail="SLI 'name' must have a value!")

        source = sli.get('source')
        if not source:
            raise ProblemException(title='Invalid SLI', detail="SLI 'source' must have a value!")
        source_type = source.get('type') or 'zmon'

        if source_type == 'lightstep':
            self.validate_lightstep_source(source)
        else:
            self.validate_zmon_source(source)

    @staticmethod
    def validate_zmon_source(source: dict):
        required = {'aggregation', 'check_id', 'keys'}
        missing = set(required) - set(source.keys())
        if missing:
            raise ProblemException(title='Invalid SLI', detail="SLI 'source' has missing keys: {}!".format(missing))

        if not source['keys']:
            raise ProblemException(title='Invalid SLI', detail="SLI 'source' *keys* must have a value")

        aggregation = source.get('aggregation', {})
        if not aggregation:
            raise ProblemException(title='Invalid SLI', detail="SLI 'source' *aggregation* must have a value")

        agg_type = aggregation.get('type')
        if not agg_type or agg_type not in AGG_TYPES:
            raise ProblemException(
                title='Invalid SLI',
                detail="SLI 'source' aggregation type is invalid. Valid values are: {}".format(AGG_TYPES))

        if agg_type == 'weighted' and not aggregation.get('weight_keys'):
            raise ProblemException(
                title='Invalid SLI', detail="SLI 'source' aggregation type *weighted* must have *weight_keys*")

    @staticmethod
    def validate_lightstep_source(sli: dict):
        pass

    @staticmethod
    def update_indicator_from_source(obj: Indicator):
        _type = obj.source.get('type', 'zmon')
        if _type == 'lightstep':
            SLIResource.update_lightstep_from_source(obj)
        else:
            SLIResource.update_zmon_indicator_from_source(obj)

    @staticmethod
    def update_zmon_indicator_from_source(obj: Indicator):
        obj.aggregation = obj.source['aggregation']['type']
        pass

    @staticmethod
    def update_lightstep_from_source(source: dict):
        pass

    def new_object(self, sli: dict, **kwargs) -> Indicator:
        fields = self.get_object_fields(sli)

        product_id = kwargs.get('product_id')

        sli_product = Product.query.get_or_404(product_id)

        fields['product_id'] = sli_product.id

        return Indicator(**fields)

    def get_objects(self, query: Pagination, **kwargs) -> List[Indicator]:
        return [obj for obj in query.items]

    def get_object(self, obj_id: int, **kwargs) -> Indicator:
        return self.get_query(**kwargs).filter_by(id=obj_id).first_or_404()

    def save_object(self, obj: Indicator, **kwargs) -> Indicator:
        obj.slug = slugger(obj.name)
        SLIResource.update_indicator_from_source(obj)
        db.session.add(obj)
        db.session.commit()

        return obj

    def update_object(self, obj: Indicator, sli: dict, **kwargs) -> Indicator:
        fields = self.get_object_fields(sli)

        for field, val in fields.items():
            setattr(obj, field, val)

        SLIResource.update_indicator_from_source(obj)

        product_id = kwargs.get('product_id')

        # No need to make extra DB call!
        if obj.product_id != product_id:
            sli_product = Product.query.get_or_404(product_id)
            obj.product_id = sli_product.id

        db.session.commit()

        return obj

    def delete_object(self, obj: Indicator, **kwargs) -> None:
        if obj.targets.count():
            raise ProblemException(
                status=403, title='Deleting SLI forbidden', detail='Some SLO targets reference this SLI.')
        obj.name = '{}-{}'.format(obj.name, datetime.utcnow())
        obj.is_deleted = True
        db.session.commit()

    def build_resource(self, obj: Indicator, **kwargs) -> dict:
        resource = super().build_resource(obj)

        # extra fields
        resource['product_name'] = obj.product.name

        # Links
        base_uri = resource['uri'] + '/'

        resource['product_uri'] = ProductResource.get_uri_from_id(obj.product_id, **kwargs)
        resource['sli_values_uri'] = urljoin(base_uri, 'values')
        resource['sli_query_uri'] = urljoin(base_uri, 'query')

        return resource


class SLIValueResource(ResourceHandler):
    model_fields = ('timestamp', 'value',)
    skip_count = True

    @classmethod
    def list(cls, **kwargs) -> Union[dict, Tuple]:
        indicator = Indicator.query.filter_by(id=kwargs.get('id'), is_deleted=False).first_or_404()
        type = indicator.source.get('type')
        if type != 'lightstep':
            return super().list(**kwargs)

        metric = indicator.source.get('metric')

        now = datetime.utcnow()
        start = now - relativedelta(days=7)
        stream_data = get_stream_data("yNzld3jn", start, now, metric)
        resources = [{
            "timestamp": stream_object.timestamp,
            "value": stream_object.value} for stream_object in stream_data
        ]

        return {
            'data': resources,
            '_meta': {
                'count': len(resources),
                'next_uri': None,
                'previous_uri': None,
            }
        }

    def get_query(self, id: int, **kwargs) -> BaseQuery:
        Indicator.query.filter_by(id=id, is_deleted=False).first_or_404()
        return IndicatorValue.query.filter_by(indicator_id=id).order_by(IndicatorValue.timestamp)

    def get_filter_kwargs(self, **kwargs) -> dict:
        min_from = kwargs.get('from', 10080)
        min_to = kwargs.get('to')

        now = datetime.utcnow()
        start = now - timedelta(minutes=min_from)
        end = now if not min_to else now - timedelta(minutes=min_to)

        if end < start:
            raise ProblemException(
                status=400, title='Invalid time range', detail="Query filters 'from' should be greater than 'to'")

        return {
            'start': start,
            'end': end
        }

    def get_filtered_query(self, query: BaseQuery, **kwargs) -> BaseQuery:
        """Filter query using query parameters"""
        end = kwargs.get('end')
        start = kwargs.get('start')
        return query.filter(IndicatorValue.timestamp >= start, IndicatorValue.timestamp < end)

    def get_limited_query(self, query: BaseQuery, **kwargs) -> Union[Pagination, BaseQuery]:
        """Apply pagination limits on query"""
        if 'from' in kwargs:
            return query

        return super().get_limited_query(query, **kwargs)

    def get_objects(self, query: Union[Pagination, BaseQuery], **kwargs) -> List[IndicatorValue]:
        if isinstance(query, Pagination):
            return [obj for obj in query.items]

        return [obj for obj in query.all()]

    def build_resource(self, obj: IndicatorValue, **kwargs) -> dict:
        resource = super().build_resource(obj, **kwargs)
        resource.pop('uri', None)
        return resource


class SLIQueryResource(ResourceHandler):
    @classmethod
    @trace(span_extractor=extract_span_from_flask_request, operation_name='indicator_query', pass_span=True,
           tags={ot_tags.COMPONENT: 'flask'})
    def create(cls, **kwargs) -> Tuple:
        resource = cls()

        resource.current_span = extract_span_from_kwargs(**kwargs)

        obj_id = int(kwargs.get('id'))

        # Get objects from DB
        obj = resource.get_object(obj_id, **kwargs)

        resource.validate(**kwargs)

        resource.authorization.update(obj, **kwargs)

        # Query and persist
        # TODO: what about returning ACCEPTED and run in background?!
        count = resource.query(obj, **kwargs)

        # Transform object to resource
        return resource.build_resource(obj, count=count, **kwargs), 200

    def get_query(self, product_id: int, **kwargs) -> BaseQuery:
        return Indicator.query.filter_by(product_id=product_id, is_deleted=False)

    def validate(self, duration: dict, **kwargs) -> None:
        start = duration.get('start')
        end = duration.get('end', 0)

        if not duration or not start:
            raise ProblemException(title='Invalid query duration', detail="Query 'start' must have a value!")

        if start < end:
            raise ProblemException(title='Invalid query duration', detail="Query 'start' must be greater than 'end'")

    def get_object(self, obj_id: int, **kwargs) -> Indicator:
        return self.get_query(**kwargs).filter_by(id=obj_id).first_or_404()

    def query(self, obj: Indicator, duration: dict, **kwargs) -> int:
        start = duration.get('start')
        end = duration.get('end', 0)

        self.current_span.set_tag('indicator', obj.name)
        self.current_span.set_tag('product', obj.product.name)
        self.current_span.log_kv({'query_start': start, 'query_end': end})

        # Query and insert IndicatorValue
        return update_indicator_values(obj, start, end)

    def build_resource(self, obj: IndicatorValue, count=0, **kwargs) -> dict:
        resource = super().build_resource(obj, **kwargs)
        resource.pop('uri', None)

        resource['count'] = count

        return resource
