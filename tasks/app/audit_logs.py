# -*- coding: utf-8 -*-
"""
Audit Log related tasks for Invoke.
"""

from tasks.utils import app_context_task


def format_log_message(log):
    message = f'{log.created}: {log.audit_type} executed by {log.user_email} '
    if log.module_name:
        message += f'on {log.module_name} guid: {log.item_guid} '
    if log.duration:
        message += f'in {log.duration} seconds '
    if log.message:
        message += f'message: {log.message}'
    return message


@app_context_task()
def all(context):
    """Print out all of the audit logs"""
    from app.modules.audit_logs.models import AuditLog

    for log in AuditLog.query.all():
        print(format_log_message(log))


@app_context_task()
def all_faults(context):
    """Print out all of the audit log faults"""
    from app.modules.audit_logs.models import AuditLog
    import app.extensions.logging as AuditLogExtension  # NOQA
    from sqlalchemy import desc

    faults = (
        AuditLog.query.filter(
            (AuditLog.audit_type == AuditLogExtension.AuditType.HoustonFault.value)
            | (AuditLog.audit_type == AuditLogExtension.AuditType.BackEndFault.value)
            | (AuditLog.audit_type == AuditLogExtension.AuditType.FrontEndFault.value)
        )
        .order_by(desc(AuditLog.created))
        .all()
    )
    for log in faults:
        print(format_log_message(log))


@app_context_task(help={'guid': 'guid of object to investigate'})
def object_logs(context, guid):
    """Print out the audit logs for that guid"""
    from app.modules.audit_logs.models import AuditLog

    for log in AuditLog.query.filter_by(item_guid=guid).all():
        print(format_log_message(log))


