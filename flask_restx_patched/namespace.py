# -*- coding: utf-8 -*-
import os
from functools import wraps

import elasticsearch
import flask
import flask_marshmallow
from flask_restx import Namespace as OriginalNamespace
from flask_restx._http import HTTPStatus
from flask_restx.utils import merge, unpack
from webargs.flaskparser import parser as webargs_parser
from werkzeug import cached_property  # NOQA
from werkzeug import exceptions as http_exceptions

from config import get_preliminary_config

from .model import Model  # DefaultHTTPErrorSchema


def is_x_enabled(names, name_args, enabled_names):
    force_enable = os.environ.get('FORCE_ENABLE', None)
    if force_enable is not None:
        return True

    if isinstance(names, str):
        names = (names,)
    names = names + name_args
    for name in names:
        if name not in enabled_names:
            return False

    return True


def is_extension_enabled(extension_names, *args):
    config = get_preliminary_config()
    return is_x_enabled(extension_names, args, config.ENABLED_EXTENSIONS)


def is_module_enabled(module_names, *args):
    config = get_preliminary_config()
    return is_x_enabled(module_names, args, config.ENABLED_MODULES)


def x_required(
    names, name_args, resolve, default, is_x_enabled_func, tag, func, args, kwargs
):
    import logging

    if isinstance(names, str):
        names = (names,)
    names = names + name_args

    missing_names = []
    for name in names:
        if not is_x_enabled_func(name):
            missing_names.append(name)

    if len(missing_names) > 0:
        if resolve in ['error']:
            logging.error(
                'Function %r has missing %s %r'
                % (
                    func,
                    tag,
                    missing_names,
                )
            )
            raise NotImplementedError(
                'Missing %s: %r'
                % (
                    tag,
                    missing_names,
                )
            )
        else:
            if resolve not in ['quiet']:
                logging.warning(
                    'Function %r has missing %s %r, returning default value %r'
                    % (func, tag, missing_names, default)
                )
            if callable(default):
                retval = default(*args, **kwargs)
            else:
                retval = default
            return retval
    else:
        return func(*args, **kwargs)


def extension_required(extensions, *extension_args, resolve='error', default=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return x_required(
                extensions,
                extension_args,
                resolve,
                default,
                is_extension_enabled,
                'extensions',
                func,
                args,
                kwargs,
            )

        return wrapper

    return decorator


def module_required(modules, *module_args, resolve='error', default=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return x_required(
                modules,
                module_args,
                resolve,
                default,
                is_module_enabled,
                'modules',
                func,
                args,
                kwargs,
            )

        return wrapper

    return decorator


class Namespace(OriginalNamespace):

    WEBARGS_PARSER = webargs_parser

    def _handle_api_doc(self, cls, doc):
        if doc is False:
            cls.__apidoc__ = False
            return
        # unshortcut_params_description(doc)
        # handle_deprecations(doc)
        # for key in 'get', 'post', 'put', 'delete', 'options', 'head', 'patch':
        #     if key in doc:
        #         if doc[key] is False:
        #             continue
        #         unshortcut_params_description(doc[key])
        #         handle_deprecations(doc[key])
        #         if 'expect' in doc[key] and not isinstance(doc[key]['expect'], (list, tuple)):
        #             doc[key]['expect'] = [doc[key]['expect']]
        cls.__apidoc__ = merge(getattr(cls, '__apidoc__', {}), doc)

    def resolve_object(self, object_arg_name, resolver):
        """
        A helper decorator to resolve object instance from arguments (e.g. identity).

        Example:
        >>> @namespace.route('/<int:user_guid>')
        ... class MyResource(Resource):
        ...    @namespace.resolve_object(
        ...        object_arg_name='user',
        ...        resolver=lambda kwargs: User.query.get_or_404(kwargs.pop('user_guid'))
        ...    )
        ...    def get(self, user):
        ...        # user is a User instance here
        """

        def decorator(func_or_class):
            if isinstance(func_or_class, type):
                # Handle Resource classes decoration
                # pylint: disable=protected-access
                func_or_class._apply_decorator_to_methods(decorator)
                return func_or_class

            @wraps(func_or_class)
            def wrapper(*args, **kwargs):
                kwargs[object_arg_name] = resolver(kwargs)
                return func_or_class(*args, **kwargs)

            return self.response(
                code=HTTPStatus.NOT_FOUND,
                description='**NOT FOUND**: The object could not be found by the GUID provided',
            )(wrapper)

        return decorator

    def model(self, name=None, model=None, mask=None, **kwargs):
        """
        Model registration decorator.
        """
        if isinstance(
            model, (flask_marshmallow.Schema, flask_marshmallow.base_fields.FieldABC)
        ):
            if not name:
                name = model.__class__.__name__
            api_model = Model(name, model, mask=mask)
            api_model.__apidoc__ = kwargs
            return self.add_model(name, api_model)

        return super(Namespace, self).model(name=name, model=model, **kwargs)

    def parameters(self, parameters, locations=None):
        """
        Endpoint parameters registration decorator.
        """

        def decorator(func):
            if locations is None and parameters.many:
                _locations = ('json',)
            else:
                _locations = locations
            if _locations is not None:
                parameters.context['in'] = _locations

            omit_set = {'indexed', 'elasticsearchable'}
            for omit_value in omit_set:
                parameters.fields.pop(omit_value, None)
                parameters.declared_fields.pop(omit_value, None)

            return self.doc(params=parameters)(
                self.response(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    description='**UNPROCESSABLE ENTITY**: The request was formatted correctly but contains a semantic error',
                )(self.WEBARGS_PARSER.use_args(parameters, locations=_locations)(func))
            )

        return decorator

    def response(
        self, model=None, code=HTTPStatus.OK, description=None, dump=True, **kwargs
    ):
        """
        Endpoint response OpenAPI documentation decorator.

        It automatically documents HTTPError%(code)d responses with relevant
        schemas.

        Arguments:
            model (flask_marshmallow.Schema) - it can be a class or an instance
                of the class, which will be used for OpenAPI documentation
                purposes. It can be omitted if ``code`` argument is set to an
                error HTTP status code.
            code (int) - HTTP status code which is documented.
            description (str)

        Example:
        >>> @namespace.response(BaseFamilySchema(many=True))
        ... @namespace.response(code=HTTPStatus.FORBIDDEN)
        ... def get_families():
        ...     if not user.is_admin:
        ...         abort(HTTPStatus.FORBIDDEN)
        ...     return Family.query.all()
        """
        code = HTTPStatus(code)
        if code is HTTPStatus.NO_CONTENT:
            assert model is None

        if model is None and code not in {HTTPStatus.ACCEPTED, HTTPStatus.NO_CONTENT}:
            if code.value not in http_exceptions.default_exceptions:
                raise ValueError('`model` parameter is required for code %d' % code)
            # model = self.model(
            #     name='HTTPError%d' % code, model=DefaultHTTPErrorSchema(http_code=code)
            # )

        def response_serializer_decorator(func):
            """
            This decorator handles responses to serialize the returned value
            with a given model.
            """

            def dump_wrapper(*args, **kwargs):
                # pylint: disable=missing-docstring
                response = func(*args, **kwargs)
                extra_headers = None

                if response is None:
                    if model is not None:
                        raise ValueError(
                            'Response cannot not be None with HTTP status %d' % code
                        )
                    return flask.Response(status=code)
                elif isinstance(response, flask.Response) or model is None:
                    return response
                elif isinstance(response, tuple):
                    response, _code, extra_headers = unpack(response)
                else:
                    _code = code

                if not dump:
                    _code = code

                if HTTPStatus(_code) is code and dump:
                    response = model.dump(response).data

                return response, _code, extra_headers

            return dump_wrapper

        def decorator(func_or_class):
            if code.value in http_exceptions.default_exceptions:
                # If the code is handled by raising an exception, it will
                # produce a response later, so we don't need to apply a useless
                # wrapper.
                decorated_func_or_class = func_or_class
            elif isinstance(func_or_class, type):
                # Handle Resource classes decoration
                # pylint: disable=protected-access
                func_or_class._apply_decorator_to_methods(response_serializer_decorator)
                decorated_func_or_class = func_or_class
            else:
                decorated_func_or_class = wraps(func_or_class)(
                    response_serializer_decorator(func_or_class)
                )

            if model is None:
                api_model = None
            else:
                if isinstance(model, Model):
                    api_model = model
                else:
                    api_model = self.model(model=model)
                if getattr(model, 'many', False):
                    api_model = [api_model]

            if description is None:
                if code in {HTTPStatus.OK}:
                    description_ = '**SUCCESS**'
                else:
                    description_ = '**{}**: {}'.format(
                        code.phrase.upper(), code.description
                    )
            else:
                description_ = description

            doc_decorator = self.doc(responses={code.value: (description_, api_model)})

            return doc_decorator(decorated_func_or_class)

        return decorator

    def preflight_options_handler(self, func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if 'Access-Control-Request-Method' in flask.request.headers:
                response = flask.Response(status=HTTPStatus.OK)
                response.headers['Access-Control-Allow-Methods'] = ', '.join(self.methods)
                return response
            return func(self, *args, **kwargs)

        return wrapper

    def route(self, *args, **kwargs):
        base_wrapper = super(Namespace, self).route(*args, **kwargs)

        def wrapper(cls):
            if 'OPTIONS' in cls.methods:
                cls.options = self.preflight_options_handler(
                    self.response(code=HTTPStatus.NO_CONTENT)(cls.options)
                )
            return base_wrapper(cls)

        return wrapper

    def login_required(
        self,
        oauth_scopes,
        locations=(
            'headers',
            'session',
        ),
    ):
        """
        A decorator which restricts access for authorized users only.

        This decorator automatically applies the following features:

        * ``OAuth2.require_oauth`` decorator requires authentication;
        * ``permissions.ActiveUserRolePermission`` decorator ensures
          minimal authorization level;
        * All of the above requirements are put into OpenAPI Specification with
          relevant options and in a text description.

        Arguments:
            oauth_scopes (list): a list of required OAuth2 Scopes (strings)
            locations (list): a list of locations (``headers``, ``form``) where
                the access token should be looked up.

        Example:
        >>> class Users(Resource):
        ...     @namespace.login_required(oauth_scopes=['users:read'])
        ...     def get(self):
        ...         return []
        ...
        >>> @namespace.login_required(oauth_scopes=['users:read'])
        ... class Users(Resource):
        ...     def get(self):
        ...         return []
        ...
        ...     @namespace.login_required(oauth_scopes=['users:write'])
        ...     def post(self):
        ...         return User()
        ...
        >>> @namespace.login_required(oauth_scopes=[])
        ... class Users(Resource):
        ...     @namespace.login_required(oauth_scopes=['users:read'])
        ...     def get(self):
        ...         return []
        ...
        ...     @namespace.login_required(oauth_scopes=['users:write'])
        ...     def post(self):
        ...         return User()
        """

        def decorator(func_or_class):
            """
            A helper wrapper.
            """
            if isinstance(func_or_class, type):
                # Handle Resource classes decoration
                # pylint: disable=protected-access
                func_or_class._apply_decorator_to_methods(decorator)
                return func_or_class
            func = func_or_class

            # Avoid circular dependency
            from app.extensions import oauth2
            from app.modules.users import permissions

            # Automatically apply `permissions.ActiveUserRolePermisson`
            # guard if none is yet applied.
            if getattr(func, '_role_permission_applied', False):
                protected_func = func
            else:
                protected_func = self.permission_required(
                    permissions.ActiveUserRolePermission()
                )(func)

            # Ignore the current OAuth2 scopes if another @login_required
            # decorator was applied and just copy the already applied scopes.
            if (
                hasattr(protected_func, '__apidoc__')
                and 'security' in protected_func.__apidoc__
                and '__oauth__' in protected_func.__apidoc__['security']
            ):
                _oauth_scopes = protected_func.__apidoc__['security']['__oauth__'][
                    'scopes'
                ]
            else:
                _oauth_scopes = oauth_scopes

            oauth_protection_decorator = oauth2.require_oauth(
                *_oauth_scopes, locations=locations
            )
            self._register_access_restriction_decorator(
                protected_func, oauth_protection_decorator
            )
            oauth_protected_func = oauth_protection_decorator(protected_func)

            if 'form' in locations:
                oauth_protected_func = self.param(
                    name='access_token',
                    description=(
                        'This is an alternative way of passing the access_token, useful for '
                        'making authenticated requests from the browser native forms.'
                    ),
                    _in='formData',
                    type='string',
                    required=False,
                )(oauth_protected_func)

            return self.doc(
                security={
                    # This is a temporary (namespace) configuration which gets
                    # overriden on a namespace registration (in `Api.add_namespace`).
                    '__oauth__': {'type': 'oauth', 'scopes': _oauth_scopes}
                }
            )(
                self.response(
                    code=HTTPStatus.UNAUTHORIZED,
                    description=(
                        '**UNAUTHORIZED**: This resource requires OAuth authentication'
                        if not oauth_scopes
                        else '**UNAUTHORIZED**: This resource requires the OAuth scopes %s'
                        % (', '.join(['`{}`'.format(scope) for scope in _oauth_scopes]))
                    ),
                )(oauth_protected_func)
            )

        return decorator

    def permission_required(self, permission, kwargs_on_request=None):
        """
        A decorator which restricts access for users with a specific
        permissions only.

        This decorator puts together permissions restriction code with OpenAPI
        Specification documentation.

        Arguments:
            permission (Permission) - it can be a class or an instance of
                :class:``Permission``, which will be applied to a decorated
                function, and docstrings of which will be used in OpenAPI
                Specification.
            kwargs_on_request (func) - a function which should accept only one
                ``dict`` argument (all kwargs passed to the function), and
                must return a ``dict`` of arguments which will be passed to
                the ``permission`` object.

        Example:
        >>> @namespace.permission_required(
        ...     OwnerRolePermission,
        ...     kwargs_on_request=lambda kwargs: {'obj': kwargs['family']}
        ... )
        ... def get_family(family):
        ...     # This line will be reached only if OwnerRolePermission check
        ...     # is passed!
        ...     return family
        """

        def decorator(func):
            """
            A helper wrapper.
            """
            # Avoid circilar dependency
            from app.modules.users import permissions

            if getattr(permission, '_partial', False):
                # We don't apply partial permissions, we only use them for
                # documentation purposes.
                protected_func = func
            else:
                if not kwargs_on_request:
                    _permission_decorator = permission
                else:

                    def _permission_decorator(func):
                        @wraps(func)
                        def wrapper(*args, **kwargs):
                            with permission(**kwargs_on_request(kwargs)):
                                try:
                                    return func(*args, **kwargs)
                                except elasticsearch.RequestError as ex:
                                    code = HTTPStatus.BAD_REQUEST
                                    description = {
                                        'status': code.value,
                                        'message': 'Elasticsearch encountered an error with your request',
                                    }
                                    info = ex.info
                                    error = info.get('error', None)
                                    if error is not None:
                                        description['details'] = error
                                    response = flask.make_response(description, code)
                                    return response
                                except Exception as ex:
                                    import app.extensions.logging as AuditLog  # NOQA

                                    # User errors are not audited, everything else is
                                    if not (
                                        hasattr(ex, 'code')
                                        and isinstance(ex.code, int)
                                        and 400 > ex.code > 409
                                    ):
                                        AuditLog.houston_fault(None, str(ex))

                                    # TODO is there something more sensible to do other than reraising here?
                                    raise

                        return wrapper

                protected_func = _permission_decorator(func)
                self._register_access_restriction_decorator(
                    protected_func, _permission_decorator
                )

            # Apply `_role_permission_applied` marker for Role Permissions,
            # so don't apply unnecessary permissions in `login_required`
            # decorator.
            #
            # TODO: Change this behaviour when implement advanced OPTIONS
            # method support
            if isinstance(permission, permissions.RolePermission) or (
                isinstance(permission, type)
                and issubclass(permission, permissions.RolePermission)
            ):
                protected_func._role_permission_applied = (
                    True  # pylint: disable=protected-access
                )

            permission_description = permission.__doc__.strip()
            return self.response(
                code=HTTPStatus.FORBIDDEN,
                description='**FORBIDDEN**: {}'.format(permission_description),
            )(protected_func)

        return decorator

    def _register_access_restriction_decorator(self, func, decorator_to_register):
        # pylint: disable=invalid-name
        """
        Helper function to register decorator to function to perform checks
        in options method
        """
        if not hasattr(func, '_access_restriction_decorators'):
            func._access_restriction_decorators = []  # pylint: disable=protected-access
        func._access_restriction_decorators.append(
            decorator_to_register
        )  # pylint: disable=protected-access

    def extension_required(
        self, extensions, *extension_args, resolve='error', default=None
    ):
        """
        A decorator which restricts access to a resource if the specified
        extension is enabled

        Arguments:
            extension (str or list of strings) - name of the required extension
            resolve (str) - a string of either `error' or `warn'
            default (func or object) - a default return value or function that is
                used when the resolve is `warn` and the extension is disabled

        Example:
        >>> @namespace.extension_required(
        ...     'gitlab',
        ...     resolve='warn',
        ...     deault='unknown',
        ... )
        ... def get_gitlab_version():
        ...     # This line will be reached only if the `gitlab` extension is enabled
        ...     return app.gitlab.version
        """

        def decorator(func_or_class):
            """
            A helper wrapper.
            """
            if isinstance(func_or_class, type):
                # Handle Resource classes decoration
                # pylint: disable=protected-access
                func_or_class._apply_decorator_to_methods(decorator)
                return func_or_class
            func = func_or_class

            _required_decorator = extension_required(
                extensions, *extension_args, resolve=resolve, default=default
            )

            protected_func = _required_decorator(func)
            self._register_access_restriction_decorator(
                protected_func, _required_decorator
            )

            return self.doc(
                description='**REQUIRED EXTENSIONS: {}**\n\n'.format(extensions)
            )(
                self.response(
                    code=HTTPStatus.NOT_IMPLEMENTED,
                    description='**NOT IMPLEMENTED**: Some required server-side extensions are disabled',
                )(protected_func)
            )

        return decorator

    def module_required(self, modules, *module_args, resolve='error', default=None):
        """
        A decorator which restricts access to a resource if the specified
        module is enabled

        Arguments:
            module (str or list of strings) - name of the required module
            resolve (str) - a string of either `error' or `warn'
            default (func or object) - a default return value or function that is
                used when the resolve is `warn` and the module is disabled

        Example:
        >>> @namespace.module_required(
        ...     'organization',
        ...     resolve='warn',
        ...     deault=[],
        ... )
        ... def get_user_organizations():
        ...     # This line will be reached only if the `organizations` module is enabled
        ...     return user.organizations
        """

        def decorator(func_or_class):
            """
            A helper wrapper.
            """
            if isinstance(func_or_class, type):
                # Handle Resource classes decoration
                # pylint: disable=protected-access
                func_or_class._apply_decorator_to_methods(decorator)
                return func_or_class
            func = func_or_class

            _required_decorator = module_required(
                modules, *module_args, resolve=resolve, default=default
            )

            protected_func = _required_decorator(func)
            self._register_access_restriction_decorator(
                protected_func, _required_decorator
            )

            return self.doc(description='**REQUIRED MODULES: {}**\n\n'.format(modules))(
                self.response(
                    code=HTTPStatus.NOT_IMPLEMENTED,
                    description='**NOT IMPLEMENTED**: Some required server-side modules are disabled',
                )(protected_func)
            )

        return decorator
