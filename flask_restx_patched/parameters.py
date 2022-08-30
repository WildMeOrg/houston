# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import logging
from http import HTTPStatus

import sqlalchemy as sa
from flask import request
from flask_login import current_user
from flask_marshmallow import Schema, base_fields
from marshmallow import ValidationError, pre_load, validate, validates_schema
from six import itervalues

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Parameters(Schema):
    class Meta:
        ordered = True

    def __init__(self, **kwargs):
        super(Parameters, self).__init__(strict=True, **kwargs)
        # This is an add-hoc implementation of the feature which didn't make
        # into Marshmallow upstream:
        # https://github.com/marshmallow-code/marshmallow/issues/344
        for required_field_name in getattr(self.Meta, 'required', []):
            self.fields[required_field_name].required = True

    def __contains__(self, field):
        return field in self.fields

    def make_instance(self, data):
        # pylint: disable=unused-argument
        """
        This is a no-op function which shadows ``ModelSchema.make_instance``
        method (when inherited classes inherit from ``ModelSchema``). Thus, we
        avoid a new instance creation because it is undesirable behaviour for
        parameters (they can be used not only for saving new instances).
        """
        return

    def items(self):
        return self.fields.items()


class PostFormParameters(Parameters):
    def __init__(self, *args, **kwargs):
        super(PostFormParameters, self).__init__(*args, **kwargs)
        for field in itervalues(self.fields):
            if field.dump_only:
                continue
            if not field.metadata.get('location'):
                field.metadata['location'] = 'form'


class PatchJSONParameters(Parameters):
    """
    Base parameters class for handling PATCH arguments according to RFC 6902.
    """

    # All operations described in RFC 6902
    OP_ADD = 'add'
    OP_REMOVE = 'remove'
    OP_REPLACE = 'replace'
    OP_MOVE = 'move'
    OP_COPY = 'copy'
    OP_TEST = 'test'

    # However, we use only those which make sense in RESTful API
    OPERATION_CHOICES = (
        OP_TEST,
        OP_ADD,
        OP_REMOVE,
        OP_REPLACE,
    )

    PATH_CHOICES = None
    NON_NULL_PATHS = ()

    NO_VALUE_OPERATIONS = (OP_REMOVE,)

    op = base_fields.String(required=True)  # pylint: disable=invalid-name

    path = base_fields.String(required=True)

    value = base_fields.Raw(required=False, allow_none=True)

    guid = base_fields.UUID(
        description='The GUID of the object', required=False, allow_none=True
    )

    def __init__(self, *args, **kwargs):
        if 'many' in kwargs:
            assert kwargs['many'], "PATCH Parameters must be marked as 'many'"
        kwargs['many'] = True
        super(PatchJSONParameters, self).__init__(*args, **kwargs)
        if not self.PATH_CHOICES:
            raise ValueError('%s.PATH_CHOICES has to be set' % self.__class__.__name__)
        # Make a copy of `validators` as otherwise we will modify the behaviour
        # of all `marshmallow.Schema`-based classes
        self.fields['op'].validators = self.fields['op'].validators + [
            validate.OneOf(self.OPERATION_CHOICES)
        ]
        self.fields['path'].validators = self.fields['path'].validators + [
            validate.OneOf(self.PATH_CHOICES)
        ]

    @pre_load(pass_many=True)
    def pass_load(self, data, many, **kwargs):
        if many and len(data) == 0:
            try:
                raw = request.json
            except Exception:
                raw = {}
            if not isinstance(raw, list):
                raise ValidationError(
                    'PATCH input data must be a list of operations (JSON objects)'
                )

    @validates_schema()
    def validate_patch_structure(self, data):
        """
        Common validation of PATCH structure

        Provide check that 'value' present in all operations expect it.

        Provide check if 'path' is present. 'path' can be absent if provided
        without '/' at the start. Supposed that if 'path' is present than it
        is prepended with '/'.
        Removing '/' in the beginning to simplify usage in resource.
        """
        if data is None or not isinstance(data, dict):
            raise ValidationError('Individual PATCH operations must be JSON objects')

        if 'op' not in data:
            raise ValidationError('operation not supported')

        if data['op'] not in self.NO_VALUE_OPERATIONS and 'value' not in data:
            raise ValidationError('value is required')

        if 'path' not in data:
            raise ValidationError('Path is required and must always begin with /')
        else:
            data['field_name'] = data['path'][1:]

        if (
            data['op'] not in self.NO_VALUE_OPERATIONS
            and data['path'] in self.NON_NULL_PATHS
            and not data.get('value')
        ):
            raise ValidationError('value cannot be null')

    @classmethod
    def perform_patch(cls, operations, obj=None, obj_cls=None, state=None):
        """
        Performs all necessary operations by calling class methods with
        corresponding names.
        """
        from app.modules.users import permissions
        from app.modules.users.permissions.types import AccessOperation

        if state is None:
            state = {}

        if obj_cls is not None:
            assert obj is None, 'Cannot specify a obj when using module-level patching'

        objs = []
        for operation in operations:
            if obj_cls is not None:
                field_operaion = operation.get('op', None)
                guid = operation.get('guid', None)

                if field_operaion == cls.OP_TEST and guid is None:
                    obj = None
                else:
                    if guid is None:
                        raise ValidationError(
                            'Failed to update %s details. Operation %s could not succeed.  Must provide a "guid" with each operation when using a module-level patch'
                            % (obj.__class__.__name__, operation)
                        )
                    obj = obj_cls.query.get(guid)
                    if obj is None:
                        raise ValidationError(
                            'Failed to update %s details. Operation %s could not succeed.  The provided GUID did not match any known object'
                            % (obj.__class__.__name__, operation)
                        )
                    perm = permissions.ObjectAccessPermission(
                        obj=obj, action=AccessOperation.WRITE
                    )
                    if not perm.check():
                        raise ValidationError(
                            'Failed to update %s details. Operation %s could not succeed.  The current user does not have the permissions to modify it'
                            % (obj.__class__.__name__, operation)
                        )

            if obj is not None:
                objs.append(obj)

            if not cls._process_patch_operation(operation, obj=obj, state=state):
                log.info(
                    '%s patching has been stopped because of unknown operation %s',
                    obj.__class__.__name__,
                    operation,
                )
                raise ValidationError(
                    'Failed to update %s details. Operation %s could not succeed.'
                    % (obj.__class__.__name__, operation)
                )

        # Refresh the index for any patched object
        for obj in objs:
            if obj is not None:
                if hasattr(obj, 'index'):
                    obj.index(force=True, quiet=True)

        if obj_cls is not None:
            return objs

        return True

    @classmethod
    def _process_patch_operation(cls, operation, obj, state):
        """
        Args:
            operation (dict): one patch operation in RFC 6902 format.
            obj (object): an instance which is needed to be patched.
            state (dict): inter-operations state storage

        Returns:
            processing_status (bool): True if operation was handled, otherwise False.
        """
        field_operaion = operation['op']

        if field_operaion == cls.OP_REPLACE:
            return cls.replace(
                obj, operation['field_name'], operation['value'], state=state
            )

        elif field_operaion == cls.OP_TEST:
            return cls.test(obj, operation['field_name'], operation['value'], state=state)

        elif field_operaion == cls.OP_ADD:
            return cls.add(obj, operation['field_name'], operation['value'], state=state)

        elif field_operaion == cls.OP_MOVE:
            return cls.move(obj, operation['field_name'], operation['value'], state=state)

        elif field_operaion == cls.OP_COPY:
            return cls.copy(obj, operation['field_name'], operation['value'], state=state)

        elif field_operaion == cls.OP_REMOVE:
            # This deviates from RFC 6902 to permit field and value based removal.
            # This is used for multiple relationship tables within houston
            return cls.remove(
                obj, operation['field_name'], operation.get('value', None), state=state
            )

        return False

    @classmethod
    def replace(cls, obj, field, value, state):
        """
        This is method for replace operation. It is separated to provide a
        possibility to easily override it in your Parameters.

        Args:
            obj (object): an instance to change.
            field (str): field name
            value (str): new value
            state (dict): inter-operations state storage

        Returns:
            processing_status (bool): True
        """
        # Check for existence
        if not hasattr(obj, field):
            raise ValidationError(
                "Field '%s' does not exist, so it cannot be patched" % field
            )
        # Check for Enum objects
        try:
            obj_cls = obj.__class__
            obj_column = getattr(obj_cls, field)
            obj_column_type = obj_column.expression.type
            if isinstance(obj_column_type, sa.sql.sqltypes.Enum):
                enum_values = obj_column_type.enums
                if value not in enum_values:
                    args = (field, value, enum_values)
                    raise ValidationError(
                        "Field '%s' is an Enum and does not recognize the value '%s'.  Please select one of %r"
                        % args
                    )
        except (AttributeError):
            pass
        # Set the value
        setattr(obj, field, value)
        return True

    @classmethod
    def test(cls, obj, field, value, state):
        """
        This is method for test operation. It is separated to provide a
        possibility to easily override it in your Parameters.

        Args:
            obj (object): an instance to change.
            field (str): field name
            value (str): new value
            state (dict): inter-operations state storage

        Returns:
            processing_status (bool): True
        """
        return getattr(obj, field) == value

    @classmethod
    def add(cls, obj, field, value, state):
        raise NotImplementedError()

    @classmethod
    def remove(cls, obj, field, value, state):
        """
        This is method for removal operation. It is separated to provide a
        possibility to easily override it in your Parameters.

        Args:
            obj (object): an instance to change.
            field (str): field name
            value (str): [optional] item to remove for lists, Extension on RFC 6509
            state (dict): inter-operations state storage

        Returns:
            processing_status (bool): True
        """
        raise NotImplementedError()

    @classmethod
    def move(cls, obj, field, value, state):
        raise NotImplementedError()

    @classmethod
    def copy(cls, obj, field, value, state):
        raise NotImplementedError()


# noinspection PyAbstractClass
class PatchJSONParametersWithPassword(PatchJSONParameters):
    """
    Base parameters class for handling PATCH arguments according to RFC 6902 with specific handling for
    password validation for some sensitive fields.
    Provides test, add and remove methods.
    """

    # Some classes may require all fields to be password validated, some may require some.
    # If the SENSITIVE_FIELDS array is left as None, all fields are password protected
    SENSITIVE_FIELDS = None

    @classmethod
    def test(cls, obj, field, value, state):
        from app.extensions.api import abort

        if field == 'current_password':
            if current_user.password == value:
                state['current_password'] = value
                return True
            else:
                abort(code=HTTPStatus.FORBIDDEN, message='Wrong password')

        return PatchJSONParameters.test(obj, field, value, state)

    @classmethod
    def add(cls, obj, field, value, state):
        from app.extensions.api import abort

        """
        Some or all fields require extra permissions to be changed
        """
        if not cls.SENSITIVE_FIELDS or field in cls.SENSITIVE_FIELDS:
            if 'current_password' not in state:
                abort(
                    code=HTTPStatus.FORBIDDEN,
                    message='Updating database requires `current_password` test operation.',
                )

        # return PatchJSONParameters.add(obj, field, value, state)

    @classmethod
    def remove(cls, obj, field, value, state):
        from app.extensions.api import abort

        if not cls.SENSITIVE_FIELDS or field in cls.SENSITIVE_FIELDS:
            if 'current_password' not in state:
                abort(
                    code=HTTPStatus.FORBIDDEN,
                    message='Updating database requires `current_password` test operation.',
                )

        # return PatchJSONParameters.remove(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        from app.extensions.api import abort

        if not cls.SENSITIVE_FIELDS or field in cls.SENSITIVE_FIELDS:
            if 'current_password' not in state:
                abort(
                    code=HTTPStatus.FORBIDDEN,
                    message='Updating database requires `current_password` test operation.',
                )

        return PatchJSONParameters.replace(obj, field, value, state)


class SetOperationsJSONParameters(Parameters):
    """
    Base parameters class for handling Set Operation arguments.

    This implementation is designed to mirror the PATCH arguments according to RFC 6902.
    """

    OP_IDENTITY = ['identity', 'id', '*']
    OP_UNION = ['union', 'or', '|']
    OP_INTERSECTION = ['intersection', 'intersect', 'and', '&']
    OP_DIFFERENCE = ['difference', 'diff', '-', '->']
    OP_MIRRORED_DIFFERENCE = ['mirrored_difference', 'mirdiff', '--', '<-']
    OP_SYMMETRIC_DIFFERENCE = ['symmetric_difference', 'symmetric', 'symdiff', 'sym', '^']

    # However, we use only those which make sense in RESTful API
    OPERATION_CHOICES = (
        OP_IDENTITY
        + OP_UNION
        + OP_INTERSECTION
        + OP_DIFFERENCE
        + OP_MIRRORED_DIFFERENCE
        + OP_SYMMETRIC_DIFFERENCE
    )

    PATH_CHOICES = None

    op = base_fields.String(required=True)  # pylint: disable=invalid-name

    path = base_fields.String(required=True)

    value = base_fields.Raw(required=True)

    def __init__(self, *args, **kwargs):
        if 'many' in kwargs:
            assert kwargs['many'], "Set Operation Parameters must be marked as 'many'"
        kwargs['many'] = True
        super(SetOperationsJSONParameters, self).__init__(*args, **kwargs)
        if not self.PATH_CHOICES:
            raise ValueError('%s.PATH_CHOICES has to be set' % self.__class__.__name__)
        # Make a copy of `validators` as otherwise we will modify the behaviour
        # of all `marshmallow.Schema`-based classes
        self.fields['op'].validators = self.fields['op'].validators + [
            validate.OneOf(self.OPERATION_CHOICES)
        ]
        self.fields['path'].validators = self.fields['path'].validators + [
            validate.OneOf(self.PATH_CHOICES)
        ]

    @validates_schema
    def validate_set_operations_structure(self, data):
        """
        Common validation of POST structure

        Provide check that 'value' present in all operations expect it.

        Provide check if 'path' is present. 'path' can be absent if provided
        without '/' at the start. Supposed that if 'path' is present than it
        is prepended with '/'.
        Removing '/' in the beginning to simplify usage in resource.
        """
        if 'op' not in data:
            raise ValidationError('operation not supported')

        if 'value' not in data:
            raise ValidationError('value is required')

        if 'path' not in data:
            raise ValidationError('Path is required and must always begin with /')
        else:
            data['field_name'] = data['path'][1:]

    @classmethod
    def perform_set_operations(
        cls, operations, obj=None, obj_cls=None, starting_set=None
    ):
        """
        Performs all necessary operations by calling class methods with
        corresponding names.
        """
        working_set = set()

        if starting_set is not None:
            for starting_obj in starting_set:
                assert isinstance(starting_obj, obj_cls)
                working_set.add(starting_obj)

        identity_state = {}
        for operation in operations:
            working_set = cls._process_set_operation(
                operation, working_set, obj, obj_cls, identity_state
            )
            if working_set is None:
                log.info(
                    'Set parsing has been stopped because of unknown operation %s',
                    operation,
                )
                raise ValidationError(
                    'Failed to update set. Operation %s could not succeed.' % (operation)
                )

        return working_set, identity_state

    @classmethod
    def _process_set_operation(
        cls, operation, working_set, identity_state, obj=None, obj_cls=None
    ):
        """
        Args:
            operation (dict): one set operation.

        Returns:
            processing_status (bool): True if operation was handled, otherwise False.
        """
        field_operaion = operation['op']
        field_name = operation['field_name']
        field_value = operation['value']

        if field_operaion in cls.OP_IDENTITY:
            identity_state[field_name] = field_value
            return working_set

        resolved_set = set(cls.resolve(field_name, field_value, obj=obj))

        for resolved_obj in resolved_set:
            assert isinstance(resolved_obj, obj_cls)

        if field_operaion in cls.OP_UNION:
            return cls.union(working_set, resolved_set)

        elif field_operaion in cls.OP_INTERSECTION:
            return cls.intersection(working_set, resolved_set)

        elif field_operaion in cls.OP_DIFFERENCE:
            return cls.difference(working_set, resolved_set)

        elif field_operaion in cls.OP_MIRRORED_DIFFERENCE:
            return cls.mirrored_difference(working_set, resolved_set)

        elif field_operaion in cls.OP_SYMMETRIC_DIFFERENCE:
            return cls.symmetric_difference(working_set, resolved_set)

    @classmethod
    def resolve(cls, field, value, obj=None):
        """
        Resolve the (field, value) into an iterable of objects for the designated class
        """
        raise NotImplementedError()

    @classmethod
    def union(cls, working_set, resolved_set):
        """
        DO NOT IMPLEMENT UNLESS NEEDED, USE INDEAD cls.resolve()

        Take the intersection of the (field, value) set and the current working_set.
        This OP will merge the two sets and return all items found in either set.
        Set union is symmetric and the order does not matter.

        This function returns (A | B), where:
            A = set(working_set)
            B = set(resolved_set) = set(resolve(field, value))
        """
        return working_set | resolved_set

    @classmethod
    def intersection(cls, working_set, resolved_set):
        """
        DO NOT IMPLEMENT UNLESS NEEDED, USE INDEAD cls.resolve()

        Take the intersection of the (field, value) set and the current working_set.
        This OP will compare the two sets and return only the items found in both.
        Set intersection is symmetric and the order does not matter.

        This function returns (A & B), where:
            A = set(working_set)
            B = set(resolved_set) = set(resolve(field, value))
        """
        return working_set & resolved_set

    @classmethod
    def difference(cls, working_set, resolved_set):
        """
        DO NOT IMPLEMENT UNLESS NEEDED, USE INDEAD cls.resolve()

        Take the difference of the (field, value) set and the current working_set.
        Set difference is NOT symmetric and is directional (the order does matter).
        This OP will compare the two sets and return only the items in A that are not in B.

        This function returns (A - B), where:
            A = set(working_set)
            B = set(resolved_set) = set(resolve(field, value))
        """
        return working_set - resolved_set

    @classmethod
    def mirrored_difference(cls, working_set, resolved_set):
        """
        DO NOT IMPLEMENT UNLESS NEEDED, USE INDEAD cls.difference()

        Take the difference of the (field, value) set and the current working_set.
        Set difference is NOT symmetric and is directional (the order does matter).
        This OP will compare the two sets and return only the items in B that are not in A.

        This function returns (B - A), where:
            A = set(working_set)
            B = set(resolved_set) = set(resolve(field, value))
        """
        return cls.difference(resolved_set, working_set)

    @classmethod
    def symmetric_difference(cls, working_set, resolved_set):
        """
        DO NOT IMPLEMENT UNLESS NEEDED, USE INDEAD cls.union(), cls.intersection(), and cls.difference()

        Take the symmetric difference of the (field, value) set and the current working_set.
        Set difference is symmetric and the order does not matter.
        This OP will compare the two sets and return only the items in A or B but not items in A and B.

        This function returns (A ^ B) or (A | B) − (A & B), where:
            A = set(working_set)
            B = set(resolved_set) = set(resolve(field, value))
        """
        term_union = cls.union(working_set, resolved_set)
        term_intersection = cls.intersection(working_set, resolved_set)
        term_diff = cls.difference(term_union, term_intersection)
        return term_diff
