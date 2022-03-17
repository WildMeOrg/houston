# -*- coding: utf-8 -*-
"""
Serialization schemas for Audit Logs resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import AuditLog


class BaseAuditLogSchema(ModelSchema):
    """
    Base AuditLog schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = AuditLog
        fields = (
            AuditLog.guid.key,
            'elasticsearchable',
            AuditLog.indexed.key,
        )
        dump_only = (AuditLog.guid.key,)


class DetailedAuditLogSchema(BaseAuditLogSchema):
    """
    Detailed AuditLog schema exposes all useful fields.
    """

    class Meta(BaseAuditLogSchema.Meta):
        fields = BaseAuditLogSchema.Meta.fields + (
            AuditLog.created.key,
            AuditLog.module_name.key,
            AuditLog.item_guid.key,
            AuditLog.audit_type.key,
            AuditLog.user_email.key,
            AuditLog.message.key,
            AuditLog.duration.key,
        )
        dump_only = BaseAuditLogSchema.Meta.dump_only + (
            AuditLog.created.key,
            AuditLog.updated.key,
        )
