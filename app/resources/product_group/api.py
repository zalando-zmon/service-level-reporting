from typing import List, Union

from urllib.parse import urljoin

from flask_sqlalchemy import BaseQuery, Pagination

from connexion import ProblemException, request

from app.extensions import db
from app.libs.resource import ResourceHandler
from app.utils import slugger

from .models import ProductGroup


class ProductGroupResource(ResourceHandler):
    model_fields = ('name', 'department', 'slug', 'username', 'created', 'updated')

    @staticmethod
    def get_uri_from_id(obj_id: Union[str, int], **kwargs) -> str:
        return urljoin(request.api_url, 'product-groups/{}'.format(obj_id))

    def get_filter_kwargs(self, **kwargs) -> dict:
        """Return relevant filters"""
        filters = {}

        if 'name' in kwargs:
            filters['slug'] = slugger(kwargs['name'])

        return filters

    def get_query(self, **kwargs) -> BaseQuery:
        return ProductGroup.query

    def validate(self, product_group: dict, **kwargs) -> None:
        if not product_group or not product_group.get('name'):
            raise ProblemException(title='Invalid product group', detail='Product group name must have a value!')

    def new_object(self, product_group: dict, **kwargs) -> ProductGroup:
        fields = self.get_object_fields(product_group)

        return ProductGroup(**fields)

    def get_objects(self, query: Pagination, **kwargs) -> List[ProductGroup]:
        return [obj for obj in query.items]

    def get_object(self, obj_id: int, **kwargs) -> ProductGroup:
        return ProductGroup.query.get_or_404(obj_id)

    def save_object(self, obj: ProductGroup, **kwargs) -> ProductGroup:
        db.session.add(obj)
        db.session.commit()

        return obj

    def update_object(self, obj: ProductGroup, product_group: dict, **kwargs) -> ProductGroup:
        fields = self.get_object_fields(product_group)

        for field, val in fields.items():
            setattr(obj, field, val)

        db.session.commit()

        return obj

    def delete_object(self, obj: ProductGroup, **kwargs) -> None:
        if obj.products.count():
            raise ProblemException(
                status=403, title='Deleting Product group forbidden',
                detail='Some products still belong to this product group.')

        db.session.delete(obj)
        db.session.commit()
