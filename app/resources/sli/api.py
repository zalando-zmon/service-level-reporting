from datetime import datetime
from typing import List, Tuple, Union, cast
from urllib.parse import urljoin

from connexion import ProblemException, request
from flask_sqlalchemy import BaseQuery, Pagination
from opentracing.ext import tags as ot_tags
from opentracing_utils import (
    extract_span_from_flask_request,
    extract_span_from_kwargs,
    trace,
)

from app.config import API_DEFAULT_PAGE_SIZE
from app.extensions import db
from app.libs.authorization import Authorization
from app.libs.resource import ResourceHandler
from app.resources.product.api import ProductResource
from app.resources.product.models import Product
from app.resources.sli import sources
from app.resources.sli.sources import IndicatorValueLike
from app.utils import slugger

from .models import Indicator


class SLIResource(ResourceHandler):
    model_fields = (
        'name',
        'slug',
        'source',
        'unit',
        'aggregation',
        'created',
        'updated',
        'username',
    )

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
        if not sli or not sli.get("name"):
            raise ProblemException(
                title="Invalid SLI", detail="SLI 'name' must have a value!"
            )

        source_config = sli.get("source")
        if not source_config:
            raise ProblemException(
                title="Invalid SLI", detail="SLI 'source' must have a value!"
            )

        try:
            sources.validate_config(source_config)
        except sources.SourceError as e:
            raise ProblemException(title="Invalid SLI source", detail=str(e))

    def before_object_update(self, obj: Indicator):
        aggregation = obj.source.get("aggregation", {}).get("type")
        obj.aggregation = aggregation

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
        self.before_object_update(obj)
        db.session.add(obj)
        db.session.commit()

        return obj

    def update_object(self, obj: Indicator, sli: dict, **kwargs) -> Indicator:
        fields = self.get_object_fields(sli)

        for field, val in fields.items():
            setattr(obj, field, val)

        self.before_object_update(obj)

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
                status=403,
                title='Deleting SLI forbidden',
                detail='Some SLO targets reference this SLI.',
            )
        obj.name = '{}-{}'.format(obj.name, datetime.utcnow())
        obj.is_deleted = True
        db.session.commit()

    def build_resource(self, obj: Indicator, **kwargs) -> dict:
        resource = super().build_resource(obj)

        # extra fields
        resource['product_name'] = obj.product.name

        # Links
        base_uri = resource['uri'] + '/'

        resource['product_uri'] = ProductResource.get_uri_from_id(
            obj.product_id, **kwargs
        )
        resource['sli_values_uri'] = urljoin(base_uri, 'values')
        resource['sli_query_uri'] = urljoin(base_uri, 'query')

        return resource


class SLIValueResource(ResourceHandler):
    model_fields = ('timestamp', 'value')

    @classmethod
    def list(cls, **kwargs) -> dict:
        indicator = Indicator.query.filter_by(
            id=kwargs.get("id"), is_deleted=False
        ).first_or_404()

        timerange = sources.RelativeMinutesRange(
            kwargs.get("from", 10080), kwargs.get("to")
        )
        start_dt, end_dt = timerange.to_datetimes()
        if start_dt > end_dt:
            raise ProblemException(
                status=400,
                title="Invalid time range",
                detail="Query filters 'from' should be greater than 'to'",
            )

        if "from" in kwargs:
            page, per_page = None, None
        else:
            per_page = int(kwargs.get("page_size", API_DEFAULT_PAGE_SIZE))
            page = int(kwargs.get("page") or 1)

        source = sources.from_indicator(indicator)
        indicator_values, metadata = source.get_indicator_values(
            timerange, page=page, per_page=per_page,
        )
        resources = [
            {k: v for k, v in iv.as_dict().items() if k in cls.model_fields}
            for iv in indicator_values
        ]

        return cls().build_list_response(
            resources, cast(Pagination, metadata), len(resources)
        )


class SLIQueryResource(ResourceHandler):
    @classmethod
    @trace(
        span_extractor=extract_span_from_flask_request,
        operation_name='indicator_query',
        pass_span=True,
        tags={ot_tags.COMPONENT: 'flask'},
    )
    def create(cls, **kwargs) -> Tuple:
        resource = cls()

        resource.current_span = extract_span_from_kwargs(**kwargs)

        obj_id = int(cast(str, kwargs.get('id')))

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
            raise ProblemException(
                title='Invalid query duration',
                detail="Query 'start' must have a value!",
            )

        if start < end:
            raise ProblemException(
                title='Invalid query duration',
                detail="Query 'start' must be greater than 'end'",
            )

    def get_object(self, obj_id: int, **kwargs) -> Indicator:
        return self.get_query(**kwargs).filter_by(id=obj_id).first_or_404()

    def query(self, obj: Indicator, duration: dict, **kwargs) -> int:
        start = duration.get('start')
        end = duration.get('end', 0)

        self.current_span.set_tag('indicator', obj.name)
        self.current_span.set_tag('product', obj.product.name)
        self.current_span.log_kv({'query_start': start, 'query_end': end})

        # Query and insert IndicatorValue
        return sources.from_indicator(obj).update_indicator_values(
            sources.RelativeMinutesRange(start=start, end=end)
        )

    def build_resource(self, obj: IndicatorValueLike, count=0, **kwargs) -> dict:
        resource = super().build_resource(obj, **kwargs)
        resource.pop('uri', None)

        resource['count'] = count

        return resource
