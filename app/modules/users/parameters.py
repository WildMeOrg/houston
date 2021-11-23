# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-order
"""
Input arguments (Parameters) for User resources RESTful API
-----------------------------------------------------------
"""
import logging
from pathlib import Path

# from flask import current_app
from flask_login import current_user
from flask_marshmallow import base_fields
from flask_restx_patched import Parameters, PatchJSONParameters
from flask_restx_patched._http import HTTPStatus
from marshmallow import validates_schema
import PIL

from app.extensions.api.parameters import PaginationParameters
from app.extensions.api import abort
from app.utils import HoustonException

from . import schemas

# from . import permissions
from .models import User, db, USER_ROLES


log = logging.getLogger(__name__)


class ListUserParameters(PaginationParameters):
    """
    New user creation (sign up) parameters.
    """

    search = base_fields.String(description='Example: search@example.com', required=False)


class CreateUserParameters(Parameters, schemas.BaseUserSchema):
    """
    New user creation (sign up) parameters.
    """

    email = base_fields.Email(description='Example: root@gmail.com', required=True)
    password = base_fields.String(description='No rules yet', required=True)
    roles = base_fields.List(
        base_fields.String(),
        description=f'User roles: {", ".join(USER_ROLES)}',
        required=False,
    )

    recaptcha_key = base_fields.String(
        description=(
            'See `/<prefix>/auth/recaptcha` for details. It is required for everybody, except admins'
        ),
        required=False,
    )

    class Meta(schemas.BaseUserSchema.Meta):
        fields = schemas.BaseUserSchema.Meta.fields + (
            'email',
            'password',
            'roles',
            'recaptcha_key',
        )

    @validates_schema
    def validate_roles(self, data):
        roles = data.get('roles', [])
        invalid_roles = [role for role in roles if role not in USER_ROLES]
        if invalid_roles:
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message=f'invalid roles: {", ".join(invalid_roles)}.  Valid roles are {", ".join(USER_ROLES)}',
            )

    # @validates_schema
    # def validate_captcha(self, data):
    #     """ "
    #     Check reCAPTCHA if necessary.

    #     NOTE: we remove 'recaptcha_key' from data once checked because we don't need it
    #     in the resource
    #     """
    #     recaptcha_key = data.pop('recaptcha_key', None)

    #     captcha_is_valid = False
    #     if not recaptcha_key:
    #         no_captcha_permission = permissions.AdminRolePermission()
    #         if no_captcha_permission.check():
    #             captcha_is_valid = True
    #     elif recaptcha_key == current_app.config.get('RECAPTCHA_BYPASS', None):
    #         captcha_is_valid = True

    #     if not captcha_is_valid:
    #         abort(code=HTTPStatus.FORBIDDEN, message='CAPTCHA key is incorrect.')


class AdminUserInitializedParameters(Parameters):
    """
    New user creation (sign up) parameters.
    """

    email = base_fields.Email(description='Example: root@gmail.com', required=True)
    password = base_fields.String(description='No rules yet', required=True)


class CheckinUserParameters(Parameters):
    users_lite = base_fields.List(base_fields.Integer, required=True)


class DeleteUserParameters(Parameters):
    """
    New user creation (sign up) parameters.
    """

    user_guid = base_fields.UUID(description='The GUID of the user', required=True)


class PatchUserDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method
    """
    User details updating parameters following PATCH JSON RFC.
    """

    VALID_FIELDS = (
        'current_password',
        User.email.key,
        User.password.key,
        User.full_name.key,
        User.website.key,
        User.location.key,
        User.affiliation.key,
        User.forum_id.key,
        User.accepted_user_agreement.key,
        User.use_usa_date_format.key,
        User.show_email_in_profile.key,
        User.receive_notification_emails.key,
        User.receive_newsletter_emails.key,
        User.shares_data.key,
        User.default_identification_catalogue.key,
        User.profile_fileupload_guid.key,
        User.notification_preferences.key,
        User.is_active.fget.__name__,
        User.is_exporter.fget.__name__,
        User.is_internal.fget.__name__,
        User.is_staff.fget.__name__,
        User.is_admin.fget.__name__,
        User.is_user_manager.fget.__name__,
        User.is_researcher.fget.__name__,
        User.is_contributor.fget.__name__,
        User.in_beta.fget.__name__,
        User.in_alpha.fget.__name__,
    )

    SENSITIVE_FIELDS = (
        User.email.key,
        User.password.key,
    )

    PRIVILEGED_FIELDS = (
        User.is_active.fget.__name__,
        User.is_exporter.fget.__name__,
        User.is_internal.fget.__name__,
        User.is_staff.fget.__name__,
        User.is_admin.fget.__name__,
        User.is_user_manager.fget.__name__,
        User.is_researcher.fget.__name__,
        User.is_contributor.fget.__name__,
        User.in_beta.fget.__name__,
        User.in_alpha.fget.__name__,
    )

    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def test(cls, obj, field, value, state):
        """
        Additional check for 'current_password' as User hasn't field 'current_password'
        """
        if field == 'current_password':
            if (
                current_user.password != value and obj.password != value
            ):  # pylint: disable=consider-using-in
                abort(code=HTTPStatus.FORBIDDEN, message='Wrong password')
            else:
                state['current_password'] = value
                return True

        return PatchJSONParameters.test(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        """
        Some fields require extra permissions to be changed.

        Changing `is_active` and `is_staff` properties, current user
        must be a supervisor of the changing user, and `current_password` of
        the current user should be provided.

        Changing `is_admin` property requires current user to be Admin, and
        `current_password` of the current user should be provided..
        """
        log.debug('Updating replace field %s' % (field,))
        log.debug('sensitive %s' % (cls.SENSITIVE_FIELDS,))
        log.debug('privileged %s' % (cls.PRIVILEGED_FIELDS,))
        if field in cls.SENSITIVE_FIELDS or field in cls.PRIVILEGED_FIELDS:
            log.debug('Updating sensitive field %s' % (field,))
            if 'current_password' not in state:
                abort(
                    code=HTTPStatus.FORBIDDEN,
                    message='Updating sensitive user settings requires `current_password` test operation performed before replacements.',
                )

        # if field in {User.is_active.fget.__name__, User.is_staff.fget.__name__}:
        #     context = permissions.SupervisorRolePermission(
        #         obj=obj,
        #         password_required=True,
        #         password=state['current_password']
        #     )
        #     with context:
        #         # Access granted
        #         pass

        if field in cls.PRIVILEGED_FIELDS:
            log.debug('Updating administrator-only field %s' % (field,))
            if not current_user.is_admin:
                abort(
                    code=HTTPStatus.FORBIDDEN,
                    message='Updating administrator-only user settings requires the logged in user to be an administrator',
                )

                # context = permissions.AdminRolePermission(
                #     password_required=True,
                #     password=state['current_password']
                # )
                # with context:
                #     # Access granted
                #     pass

        if field == User.profile_fileupload_guid.key:
            value = cls.add_replace_profile_fileupload(value)

        if field == User.notification_preferences.key:
            # The current implementation of this code allows the API to set the entire set of preferences or a
            # subset.
            from app.modules.notifications.models import (
                NotificationPreferences,
                UserNotificationPreferences,
            )

            try:
                NotificationPreferences.validate_preferences(value)
            except HoustonException as ex:
                abort(ex.status_code, ex.message)

            if len(current_user.notification_preferences) != 0:
                current_user.notification_preferences[0].preferences = (
                    current_user.notification_preferences[0].preferences | value
                )
            else:
                # No existing one, create a new one
                user_prefs = UserNotificationPreferences(
                    preferences=value, user=current_user
                )
                with db.session.begin(subtransactions=True):
                    db.session.add(user_prefs)
            return True

        else:
            return super(PatchUserDetailsParameters, cls).replace(
                obj, field, value, state
            )

    @classmethod
    def remove(cls, obj, field, value, state):

        if field == User.profile_fileupload_guid.key:
            obj.remove_profile_file()

        return True

    @classmethod
    def add(cls, obj, field, value, state):
        if field == User.profile_fileupload_guid.key:
            obj.profile_fileupload_guid = cls.add_replace_profile_fileupload(value)
        return True

    @classmethod
    def add_replace_profile_fileupload(cls, value):
        if not isinstance(value, dict):
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message='Expected {"transactionId": "..."} or {"guid": "..."}',
            )

        from app.modules.fileuploads.models import FileUpload

        guid = value.get('guid')
        transaction_id = value.get('transactionId')
        if not transaction_id and not guid:
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message='"transactionId" or "guid" is mandatory',
            )

        if guid:
            fileupload = FileUpload.query.get(guid)

        if transaction_id:
            paths = [value.get('path')] if value.get('path') else None
            files = (
                FileUpload.create_fileuploads_from_tus(transaction_id, paths=paths) or []
            )
            if len(files) != 1:
                for file_ in files:
                    # Delete the files in the filesystem
                    # FileUpload isn't persisted yet so can't use .delete()
                    path = Path(file_.get_absolute_path())
                    if path.exists():
                        path.unlink()
                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message=f'Need exactly 1 asset but found {len(files)} assets',
                )
            with db.session.begin(subtransactions=True):
                db.session.add(files[0])
            fileupload = files[0]

        if value.get('crop'):
            crop = value['crop']
            if not isinstance(crop, dict) or sorted(crop.keys()) != [
                'height',
                'width',
                'x',
                'y',
            ]:
                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message='Expected {"crop": {"x": <int>, "y": <int>, "width": <int>, "height": <int>}}',
                )
            try:
                fileupload.crop(**crop)
            except PIL.UnidentifiedImageError as e:
                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message=f'UnidentifiedImageError: {str(e)}',
                )

        return str(fileupload.guid)
