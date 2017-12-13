from typing import List, Union
from urllib.parse import urljoin

from flask_sqlalchemy import BaseQuery, Pagination

from connexion import ProblemException, request

from app.extensions import db
from app.libs.resource import ResourceHandler
from app.utils import slugger

from app.resources.product_group.models import ProductGroup
from app.resources.product_group.api import ProductGroupResource

from .models import Product


class ProductResource(ResourceHandler):
    model_fields = ('name', 'slug', 'email', 'username', 'created', 'updated')

    @staticmethod
    def get_uri_from_id(obj_id: Union[str, int], **kwargs) -> str:
        return urljoin(request.api_url, 'products/{}'.format(obj_id))

    def get_filter_kwargs(self, **kwargs) -> dict:
        """Return relevant filters"""
        filters = {}

        if 'name' in kwargs:
            filters['slug'] = slugger(kwargs['name'])

        if 'q' in kwargs:
            filters['q'] = slugger(kwargs['q'])

        return filters

    def get_filtered_query(self, query: BaseQuery, **kwargs) -> BaseQuery:
        """Filter query using query parameters"""
        if 'q' in kwargs:
            return query.filter(Product.slug.ilike('%{}%'.format(kwargs['q'])))

        return super().get_filtered_query(query, **kwargs)

    def get_query(self, **kwargs) -> BaseQuery:
        q = Product.query
        if 'product_group' in kwargs:
            return q.filter(ProductGroup.name == kwargs['product_group'])

        return q

    def validate(self, product: dict, **kwargs) -> None:
        if not product or not product.get('name'):
            raise ProblemException(title='Invalid product', detail="Product 'name' must have a value!")

        if not product.get('product_group_uri'):
            raise ProblemException(title='Invalid product', detail="Product 'product_group_uri' must have a value!")

    def new_object(self, product: dict, **kwargs) -> Product:
        fields = self.get_object_fields(product)

        product_group_id = self.get_id_from_uri(product['product_group_uri'])

        product_group = ProductGroup.query.get_or_404(product_group_id)

        fields['product_group_id'] = product_group.id

        return Product(**fields)

    def get_objects(self, query: Pagination, **kwargs) -> List[Product]:
        return [obj for obj in query.items]

    def get_object(self, obj_id: int, **kwargs) -> Product:
        return Product.query.get_or_404(obj_id)

    def save_object(self, obj: Product, **kwargs) -> Product:
        db.session.add(obj)
        db.session.commit()

        return obj

    def update_object(self, obj: Product, product: dict, **kwargs) -> Product:
        fields = self.get_object_fields(product)

        for field, val in fields.items():
            setattr(obj, field, val)

        product_group_id = self.get_id_from_uri(product['product_group_uri'])

        # No need to make extra DB call!
        if obj.product_group_id != product_group_id:
            product_group = ProductGroup.query.get_or_404(product_group_id)
            obj.product_group_id = product_group.id

        db.session.commit()

        return obj

    def delete_object(self, obj: Product, **kwargs) -> None:
        if obj.indicators.count():
            raise ProblemException(
                status=403, title='Deleting product forbidden', detail='Some SLIs reference this product.')

        db.session.delete(obj)
        db.session.commit()

    def build_resource(self, obj: Product, **kwargs) -> dict:
        resource = super().build_resource(obj)

        # extra fields
        resource['product_group_name'] = obj.product_group.name

        # Links
        base_uri = resource['uri'] + '/'

        resource['product_group_uri'] = ProductGroupResource.get_uri_from_id(obj.product_group_id, **kwargs)

        resource['product_sli_uri'] = urljoin(base_uri, 'sli')
        resource['product_slo_uri'] = urljoin(base_uri, 'slo')
        resource['product_reports_uri'] = urljoin(base_uri, 'reports')
        resource['product_reports_weekly_uri'] = urljoin(base_uri, 'reports/weekly')

        return resource
