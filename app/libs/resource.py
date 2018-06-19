from typing import List, Union, Tuple, Optional
from urllib.parse import urljoin, urlencode

from sqlalchemy.exc import IntegrityError
from flask_sqlalchemy import BaseQuery, Model, Pagination

from connexion import NoContent, request, problem, ProblemException

from opentracing.ext import tags as ot_tags
from opentracing_utils import trace, extract_span_from_flask_request

from app.config import API_DEFAULT_PAGE_SIZE
from app.utils import slugger

from .authorization import get_authorization


READ_ONLY_FIELDS = ('created', 'updated', 'username')


########################################################################################################################
# DEFAULT HANDLER
########################################################################################################################
class ResourceHandler:

    model_fields = ()

    @property
    def authorization(self):
        return get_authorization()

    ####################################################################################################################
    # HANDLERS
    ####################################################################################################################
    @classmethod
    @trace(span_extractor=extract_span_from_flask_request, operation_name='resource_handler',
           tags={ot_tags.COMPONENT: 'flask'})
    def list(cls, **kwargs) -> Union[dict, Tuple]:
        resource = cls()

        # Get query
        query = resource.get_query(**kwargs)

        # Filter query
        filter_kwargs = resource.get_filter_kwargs(**kwargs)
        if filter_kwargs:
            query = resource.get_filtered_query(query, **filter_kwargs)

        # Limit query
        paginated = resource.get_limited_query(query, **kwargs)

        # Get objects from DB
        objs = resource.get_objects(paginated)

        # Transform objects to resources
        resources = [resource.build_resource(obj, **kwargs) for obj in objs]

        total_count = query.count()

        # Return list response (mainly add _meta & data)
        return resource.build_list_response(resources, paginated, total_count, **kwargs)

    @classmethod
    @trace(span_extractor=extract_span_from_flask_request, operation_name='resource_handler',
           tags={ot_tags.COMPONENT: 'flask'})
    def get(cls, **kwargs) -> Union[dict, Tuple]:
        resource = cls()

        obj_id = int(kwargs.get('id'))

        # Get objects from DB
        obj = resource.get_object(obj_id, **kwargs)

        # Transform object to resource
        return resource.build_resource(obj, **kwargs)

    @classmethod
    @trace(span_extractor=extract_span_from_flask_request, operation_name='resource_handler',
           tags={ot_tags.COMPONENT: 'flask'})
    def create(cls, **kwargs) -> Union[dict, Tuple]:
        resource = cls()

        resource.validate(**kwargs)

        # Build object from resource payload
        obj = resource.new_object(**kwargs)

        obj = resource.set_username(obj)

        # Should raise Authorization error if needed!
        resource.authorization.create(obj, **kwargs)

        # Persist
        try:
            obj = resource.save_object(obj)
        except IntegrityError:
            return problem(status=400, title='Duplication error', detail='Resource already exist')

        # Transform object to resource
        return resource.build_resource(obj, **kwargs), 201

    @classmethod
    @trace(span_extractor=extract_span_from_flask_request, operation_name='resource_handler',
           tags={ot_tags.COMPONENT: 'flask'})
    def update(cls, **kwargs) -> Union[dict, Tuple]:
        resource = cls()

        obj_id = int(kwargs.get('id'))

        # Get objects from DB
        obj = resource.get_object(obj_id, **kwargs)

        resource.validate(**kwargs)

        resource.authorization.update(obj, **kwargs)

        # Persist
        try:
            obj = resource.update_object(obj, **kwargs)
        except IntegrityError as e:
            return problem(status=400, title='Duplication error', detail='Resource already exist')

        return resource.build_resource(obj, **kwargs)

    @classmethod
    @trace(span_extractor=extract_span_from_flask_request, operation_name='resource_handler',
           tags={ot_tags.COMPONENT: 'flask'})
    def delete(cls, **kwargs) -> Union[dict, Tuple]:
        resource = cls()

        obj_id = int(kwargs.get('id'))

        # Get objects from DB
        obj = resource.get_object(obj_id, **kwargs)

        resource.authorization.delete(obj, **kwargs)

        resource.delete_object(obj, **kwargs)

        return NoContent, 204

    ####################################################################################################################
    # URI
    ####################################################################################################################
    @staticmethod
    def get_uri_from_id(obj_id: Union[str, int], **kwargs) -> str:
        raise NotImplemented

    ####################################################################################################################
    # DEFAULT IMPL
    ####################################################################################################################
    def build_list_response(self, resources: List[dict], paginated: Pagination, total_count, **kwargs) -> dict:
        next_query = request.args.copy()
        prev_query = request.args.copy()

        next_query['page'] = paginated.next_num if hasattr(paginated, 'next_num') else None
        prev_query['page'] = paginated.page - 1 if hasattr(paginated, 'page') else None
        next_query['page_size'] = prev_query['page_size'] = (
            paginated.per_page if hasattr(paginated, 'per_page') else None)

        return {
            'data': resources,
            '_meta': {
                'count': total_count,
                'next_uri': urljoin(request.url, '?' + urlencode(next_query)) if next_query['page'] else None,
                'previous_uri': urljoin(request.url, '?' + urlencode(prev_query)) if prev_query['page'] else None,
            }
        }

    def get_limited_query(self, query: BaseQuery, **kwargs) -> Union[Pagination, BaseQuery]:
        """Apply pagination limits on query"""
        per_page = int(kwargs.get('page_size', API_DEFAULT_PAGE_SIZE))
        page = int(kwargs.get('page', 1))

        if page < 0 or per_page < 1:
            raise ProblemException(
                title='Invalid paging parameters', detail='page and page_size should be greater than 0')

        return query.paginate(page=page or 1, per_page=per_page, error_out=False)

    def get_filtered_query(self, query: BaseQuery, **kwargs) -> BaseQuery:
        """Filter query using query parameters"""
        return query.filter_by(**kwargs)

    def get_filter_kwargs(self, **kwargs) -> dict:
        return {}

    def build_resource(self, obj: Model, **kwargs) -> dict:
        resource = {}

        for field in self.model_fields:
            resource[field] = getattr(obj, field)

        request_path = request.path.replace('/api/', '')

        if not hasattr(obj, 'id'):
            return resource

        uri_path = '{}/{}'.format(request_path, str(obj.id))

        # Adjust path components (list v.s. detail)
        path_components = request_path.lstrip('/').rsplit('/', 1)
        if str(obj.id) == path_components[-1]:
            uri_path = request_path

        resource['uri'] = urljoin(request.api_url, uri_path)

        return resource

    def get_id_from_uri(self, uri: str) -> Optional[int]:
        end = uri.strip('/').rsplit('/', 1)[-1]

        if end.isdigit():
            return int(end)

        return None

    def get_object_fields(self, body: dict, **kwargs) -> dict:
        fields = {}

        for field in self.model_fields:
            if field in READ_ONLY_FIELDS:
                continue

            if field == 'slug' and 'name' in body:
                fields['slug'] = slugger(body['name'])
                if fields['slug'] == '':
                    raise ProblemException(
                        title='Invalid resource name',
                        detail='Resource name is invalid. Should include at least one character!')
            else:
                fields[field] = body.get(field)

        return fields

    def set_username(self, obj: Model) -> Model:
        if hasattr(obj, 'username') and hasattr(request, 'user'):
            obj.username = request.user

        return obj

    ####################################################################################################################
    # NOT IMPL
    ####################################################################################################################
    def validate(self, **kwargs) -> None:
        pass

    def get_query(self, **kwargs) -> BaseQuery:
        raise NotImplemented

    def new_object(self, **kwargs) -> Model:
        raise NotImplemented

    def get_objects(self, query: Pagination, **kwargs) -> List[Model]:
        raise NotImplemented

    def get_object(self, obj_id: int, **kwargs) -> Model:
        raise NotImplemented

    def save_object(self, obj: Model, **kwargs) -> Model:
        raise NotImplemented

    def update_object(self, obj: Model, **kwargs) -> Model:
        raise NotImplemented

    def delete_object(self, obj: Model, **kwargs) -> Model:
        raise NotImplemented
