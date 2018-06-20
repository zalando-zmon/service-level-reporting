from typing import List, Union
from urllib.parse import urljoin

from flask_sqlalchemy import BaseQuery, Pagination

from connexion import ProblemException, request

from opentracing_utils import trace, extract_span_from_kwargs

from app.extensions import db
from app.libs.resource import ResourceHandler
from app.libs.authorization import Authorization

from app.resources.slo.models import Objective
from app.resources.sli.models import Indicator
from app.resources.sli.api import SLIResource

from .models import Target


class TargetResource(ResourceHandler):
    model_fields = ('username', 'created', 'updated')

    @property
    def authorization(self):
        return Authorization()

    @staticmethod
    def get_uri_from_id(obj_id: Union[str, int], **kwargs) -> str:
        product_id = kwargs.get('product_id')
        slo_id = kwargs.get('slo_id')
        return urljoin(request.api_url, 'products/{}/slo/{}/targets/{}'.format(product_id, slo_id, obj_id))

    def get_query(self, slo_id: int, **kwargs) -> BaseQuery:
        return Target.query.filter_by(objective_id=slo_id)

    def validate(self, target: dict, **kwargs) -> None:
        if not target or not target.get('sli_uri'):
            raise ProblemException(title='Invalid target', detail="Target 'sli_uri' must have a value!")

    def new_object(self, target: dict, **kwargs) -> Target:
        fields = self.get_object_fields(target, **kwargs)

        fields['target_from'] = target.get('from')
        fields['target_to'] = target.get('to')

        product_id = kwargs.get('product_id')
        objective_id = kwargs.get('slo_id')

        target_objective = Objective.query.filter_by(product_id=product_id, id=objective_id).first_or_404()
        fields['objective_id'] = target_objective.id

        indicator_id = self.get_id_from_uri(target['sli_uri'])
        indicator = Indicator.query.filter_by(product_id=product_id, id=indicator_id, is_deleted=False).first_or_404()
        fields['indicator_id'] = indicator.id

        return Target(**fields)

    def get_objects(self, query: Pagination, **kwargs) -> List[Target]:
        return [obj for obj in query.items]

    def get_object(self, obj_id: int, **kwargs) -> Target:
        return self.get_query(**kwargs).filter_by(id=obj_id).first_or_404()

    @trace(operation_name='save_target', pass_span=True)
    def save_object(self, obj: Target, **kwargs) -> Target:
        current_span = extract_span_from_kwargs(**kwargs)
        current_span.log_kv({'objective_id': obj.objective_id})
        current_span.log_kv({'indicator_id': obj.indicator_id})

        db.session.add(obj)
        db.session.commit()

        return obj

    def update_object(self, obj: Target, target: dict, **kwargs) -> Target:
        fields = self.get_object_fields(target)

        for field, val in fields.items():
            setattr(obj, field, val)

        obj.target_from = target.get('from')
        obj.target_to = target.get('to')

        product_id = kwargs.get('product_id')
        objective_id = kwargs.get('slo_id')

        # No need to make extra DB call!
        if obj.objective_id != objective_id:
            target_objective = (
                Objective.query.filter_by(product_id=product_id, id=objective_id).first_or_404()
            )
            obj.objective_id = target_objective.id

        indicator_id = self.get_id_from_uri(target['sli_uri'])
        if obj.indicator_id != indicator_id:
            target_sli = (
                Indicator.query.filter_by(product_id=product_id, id=indicator_id, is_deleted=False).first_or_404()
            )
            obj.indicator_id = target_sli.id

        db.session.commit()

        return obj

    def delete_object(self, obj: Target, **kwargs) -> None:
        db.session.delete(obj)
        db.session.commit()

    def build_resource(self, obj: Target, **kwargs) -> dict:
        resource = super().build_resource(obj)

        # extra fields
        resource['sli_name'] = obj.indicator.name
        resource['from'] = obj.target_from
        resource['to'] = obj.target_to
        resource['product_name'] = obj.objective.product.name

        resource['sli_uri'] = SLIResource.get_uri_from_id(obj.indicator_id, **kwargs)

        return resource
