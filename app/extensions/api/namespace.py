# -*- coding: utf-8 -*-
"""
Extended Api Namespace implementation with an application-specific helpers
--------------------------------------------------------------------------
"""
import logging
from contextlib import contextmanager
from functools import wraps
from http import HTTPStatus

import flask_marshmallow
import flask_sqlalchemy
import sqlalchemy
from marshmallow import ValidationError
from sqlalchemy.inspection import inspect

from flask_restx_patched.namespace import Namespace as BaseNamespace

from . import http_exceptions
from .webargs_parser import CustomWebargsParser

log = logging.getLogger(__name__)


class Namespace(BaseNamespace):
    """
    Having app-specific handlers here.
    """

    WEBARGS_PARSER = CustomWebargsParser()

    def resolve_object_by_model(
        self, model, object_arg_name, identity_arg_names=None, return_not_found=False
    ):
        """
        A helper decorator to resolve DB record instance by id.

        Arguments:
            model (type) - a Flask-SQLAlchemy model class with
                ``query.get_or_404`` method
            object_arg_name (str) - argument name for a resolved object
            identity_arg_names (tuple) - a list of argument names holding an
                object identity, by default it will be auto-generated as
                ``%(object_arg_name)s_guid``.

        Example:
        >>> @namespace.resolve_object_by_model(User, 'user')
        ... def get_user_by_guid(user):
        ...     return user
        >>> get_user_by_guid(user_guid=3)
        <User(id=3, ...)>

        >>> @namespace.resolve_object_by_model(MyModel, 'my_model', ('user_guid', 'model_name'))
        ... def get_object_by_two_primary_keys(my_model):
        ...     return my_model
        >>> get_object_by_two_primary_keys(user_guid=3, model_name="test")
        <MyModel(user_guid=3, name="test", ...)>
        """
        if identity_arg_names is None:
            identity_arg_names = ('%s_guid' % object_arg_name,)
        elif not isinstance(identity_arg_names, (list, tuple)):
            identity_arg_names = (identity_arg_names,)

        def _resolver(kwargs):
            query_func = model.query.get if return_not_found else model.query.get_or_404
            identity_args = [
                kwargs.pop(identity_arg_name) for identity_arg_name in identity_arg_names
            ]
            response = query_func(identity_args)
            return (
                (
                    response,
                    identity_args,
                )
                if return_not_found
                else response
            )

        return self.resolve_object(
            object_arg_name,
            resolver=_resolver,
        )

    def model(self, name=None, model=None, **kwargs):
        # pylint: disable=arguments-differ
        """
        A decorator which registers a model (aka schema / definition).

        This extended implementation auto-generates a name for
        ``Flask-Marshmallow.Schema``-based instances by using a class name
        with stripped off `Schema` prefix.
        """
        if isinstance(model, flask_marshmallow.Schema) and not name:
            name = model.__class__.__name__
            if name.endswith('Schema'):
                name = name[: -len('Schema')]
        return super(Namespace, self).model(name=name, model=model, **kwargs)

    def paginate(
        self,
        parameters=None,
        locations=None,
    ):
        """
        Endpoint parameters registration decorator special for pagination.
        If ``parameters`` is not provided default PaginationParameters will be
        used.

        Also, any custom Parameters can be used, but it needs to have ``limit`` and ``offset``
        fields.
        """
        if not parameters:
            # Use default parameters if None specified
            from app.extensions.api.parameters import PaginationParameters

            parameters = PaginationParameters()

        if not all(
            mandatory in parameters.declared_fields for mandatory in ('limit', 'offset')
        ):
            raise AttributeError(
                '`limit` and `offset` fields must be in Parameter passed to `paginate()`'
            )

        def decorator(func):
            @wraps(func)
            def wrapper(self_, parameters_args, *args, **kwargs):
                from app.extensions.elasticsearch import ELASTICSEARCH_SORTING_PREFIX

                offset = parameters_args['offset']
                limit = parameters_args['limit']
                sort = parameters_args['sort']
                reverse = parameters_args['reverse']
                reverse_after = parameters_args.pop('reverse_after', False)

                query = func(self_, parameters_args, *args, **kwargs)

                exportable_count = -1
                if not isinstance(query, flask_sqlalchemy.BaseQuery):
                    if query is None or len(query) == 0:
                        total_count, response = 0, []
                    elif len(query) == 2:
                        total_count, response = query
                        assert isinstance(total_count, int)
                    elif len(query) == 3:
                        total_count, response, exportable_count = query
                        assert isinstance(total_count, int)
                        assert isinstance(exportable_count, int)
                    else:
                        raise ValueError(
                            'This may happen when @api.paginate is above @api.response'
                        )
                else:
                    total_count = query.count()
                    cls = query.column_descriptions[0].get('entity')

                    prmiary_columns = list(cls.__table__.primary_key.columns)
                    if len(prmiary_columns) == 1:
                        default_column = prmiary_columns[0]
                    else:
                        log.warning(
                            'Multiple columns specified as the primary key, defaulting to GUID'
                        )
                        default_column = cls.guid

                    if sort.startswith(ELASTICSEARCH_SORTING_PREFIX):
                        log.error(
                            'Unable to sort listing APIs with Elasticsearch property {!r}'.format(
                                sort
                            )
                        )

                        # Remove ES-specific prefix from sort
                        # This will also try to use local columns as a backup, if found
                        sort = sort.replace(ELASTICSEARCH_SORTING_PREFIX, '')

                    sort = sort.lower()

                    outerjoin_cls = None

                    if sort in ['default', 'primary']:
                        sort_column = default_column
                    else:
                        # First, check for columns in the table
                        sort_column = None
                        column_names = list(cls.__table__.columns)
                        for column in column_names:
                            if column.name.lower() == sort:
                                sort_column = column

                        # Next, check for columns in relationship tables
                        if '.' in sort:
                            for attribute, relationship in inspect(
                                cls
                            ).relationships.items():
                                rel_cls = relationship.mapper.class_
                                column_names = list(rel_cls.__table__.columns)
                                for column in column_names:
                                    column_name = '{}.{}'.format(
                                        attribute,
                                        column.name.lower(),
                                    )
                                    if column_name == sort:
                                        outerjoin_cls = rel_cls
                                        sort_column = column

                        if sort_column is None:
                            log.warning(
                                'The sort field %r is unrecognized, defaulting to GUID'
                                % (sort,)
                            )
                            sort_column = default_column

                    sort_func_1 = sort_column.desc if reverse else sort_column.asc
                    sort_func_2 = default_column.desc if reverse else default_column.asc

                    if outerjoin_cls is not None:
                        query = query.outerjoin(outerjoin_cls)

                    query = (
                        query.order_by(sort_func_1(), sort_func_2())
                        .offset(offset)
                        .limit(limit)
                    )

                    if reverse_after:
                        after_sort_func_1 = (
                            sort_column.asc if reverse else sort_column.desc
                        )
                        after_sort_func_2 = (
                            default_column.asc if reverse else default_column.desc
                        )
                        query = query.from_self().order_by(
                            after_sort_func_1(), after_sort_func_2()
                        )

                    response = query

                return (
                    response,
                    HTTPStatus.OK,
                    {
                        'X-Total-Count': total_count,
                        'X-Exportable-Count': exportable_count,
                    },
                )

            return self.parameters(parameters, locations)(wrapper)

        return decorator

    @contextmanager
    def commit_or_abort(
        self,
        session,
        default_error_message='The operation failed to complete',
        code=HTTPStatus.CONFLICT,
        **kwargs
    ):
        """
        Context manager to simplify a workflow in resources

        Args:
            session: db.session instance
            default_error_message: Custom error message
            kwargs: extra fields for the abort message
            code: change the abort code used

        Exampple:
        >>> with api.commit_or_abort(db.session):
        ...     family = Family(**args)
        ...     db.session.add(family)
        ...     return family
        """
        from app.extensions import elasticsearch_context

        try:
            with elasticsearch_context(forced=True):
                with session.begin():
                    yield
        except (ValueError, ValidationError) as exception:
            log.info('Database transaction was rolled back due to: %r', exception)
            http_exceptions.abort(code=code, message=str(exception), **kwargs)
        except sqlalchemy.exc.IntegrityError as exception:
            log.info('Database transaction was rolled back due to: %r', exception)
            http_exceptions.abort(code=code, message=default_error_message, **kwargs)
