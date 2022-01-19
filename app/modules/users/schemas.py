# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
User schemas
------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema
from app.modules import is_module_enabled

from .models import User


class BaseUserSchema(ModelSchema):
    """
    Base user schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = User
        fields = (
            User.guid.key,
            User.email.key,
            User.full_name.key,
        )
        dump_only = (User.guid.key,)


class UserListSchema(BaseUserSchema):
    from app.modules.fileuploads.schemas import DetailedFileUploadSchema  # noqa

    profile_fileupload = base_fields.Nested('DetailedFileUploadSchema')

    class Meta(BaseUserSchema.Meta):
        # pylint: disable=missing-docstring
        model = User
        fields = BaseUserSchema.Meta.fields + (
            User.is_active.fget.__name__,
            User.is_contributor.fget.__name__,
            User.is_exporter.fget.__name__,
            User.is_internal.fget.__name__,
            User.is_staff.fget.__name__,
            User.is_researcher.fget.__name__,
            User.is_user_manager.fget.__name__,
            User.is_admin.fget.__name__,
            User.in_alpha.fget.__name__,
            User.in_beta.fget.__name__,
            User.profile_fileupload.key,
        )
        dump_only = (User.guid.key,)


class PublicUserSchema(ModelSchema):
    """Only fields which are safe for public display (very minimal)."""

    from app.modules.fileuploads.schemas import DetailedFileUploadSchema  # noqa

    profile_fileupload = base_fields.Nested('DetailedFileUploadSchema')

    class Meta:
        # pylint: disable=missing-docstring
        model = User
        fields = (
            User.guid.key,
            User.full_name.key,
            User.profile_fileupload.key,
        )


class DetailedUserPermissionsSchema(ModelSchema):
    class Meta:
        # pylint: disable=missing-docstring
        model = User
        fields = (User.guid.key,)
        dump_only = (User.guid.key,)


class DetailedUserSchema(UserListSchema):
    """Detailed user schema exposes all fields used to render a normal user profile."""

    collaborations = base_fields.Function(User.get_collaborations_as_json)
    notification_preferences = base_fields.Function(User.get_notification_preferences)
    individual_merge_requests = base_fields.Function(User.get_individual_merge_requests)

    if is_module_enabled('missions'):
        assigned_missions = base_fields.Nested('DetailedMissionSchema', many=True)

    if is_module_enabled('tasks'):
        assigned_tasks = base_fields.Nested('DetailedTaskSchema', many=True)

    class Meta(UserListSchema.Meta):
        fields = UserListSchema.Meta.fields + (
            User.created.key,
            User.updated.key,
            User.viewed.key,
            User.affiliation.key,
            User.location.key,
            User.forum_id.key,
            User.website.key,
            'notification_preferences',
            'collaborations',
            'individual_merge_requests',
            'assigned_missions',
            'assigned_tasks',
        )


class PersonalUserSchema(DetailedUserSchema):
    """
    Personal user schema exposes all fields needed to render a user profile
    that can be edited by the currently logged in user.
    """

    class Meta(DetailedUserSchema.Meta):
        fields = DetailedUserSchema.Meta.fields + (
            User.unprocessed_asset_groups.__name__,
            User.unprocessed_sightings.__name__,
            User.default_identification_catalogue.key,
            User.shares_data.key,
            User.receive_newsletter_emails.key,
            User.receive_notification_emails.key,
            User.show_email_in_profile.key,
            User.use_usa_date_format.key,
            User.accepted_user_agreement.key,
        )
