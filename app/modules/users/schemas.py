# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
User schemas
------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema
from app.modules.fileuploads.schemas import DetailedFileUploadSchema  # noqa

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


class PublicUserSchema(ModelSchema):
    """ Only fields which are safe for public display (very minimal). """

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


class DetailedUserSchema(BaseUserSchema):
    """ Detailed user schema exposes all fields used to render a normal user profile. """

    profile_fileupload = base_fields.Nested('DetailedFileUploadSchema')

    class Meta(BaseUserSchema.Meta):
        fields = BaseUserSchema.Meta.fields + (
            User.created.key,
            User.updated.key,
            User.viewed.key,
            User.is_active.fget.__name__,
            User.is_contributor.fget.__name__,
            User.is_researcher.fget.__name__,
            User.is_user_manager.fget.__name__,
            User.is_admin.fget.__name__,
            User.affiliation.key,
            User.location.key,
            User.forum_id.key,
            User.website.key,
            User.profile_fileupload.key,
        )


class PersonalUserSchema(DetailedUserSchema):
    """
    Personal user schema exposes all fields needed to render a user profile
    that can be edited by the currently logged in user.
    """

    class Meta(DetailedUserSchema.Meta):
        fields = DetailedUserSchema.Meta.fields + (
            User.default_identification_catalogue.key,
            User.shares_data.key,
            User.receive_newsletter_emails.key,
            User.receive_notification_emails.key,
            User.show_email_in_profile.key,
            User.use_usa_date_format.key,
            User.accepted_user_agreement.key,
        )
