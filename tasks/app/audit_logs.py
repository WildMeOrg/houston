# -*- coding: utf-8 -*-
"""
Audit Log related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task()
def print_all_audit_logs(context):
    """Print out all of the audit logs"""
    from app.modules.audit_logs.models import AuditLog

    logs = AuditLog.query.all()
    for log in logs:
        message = f'{log.created}: {log.audit_type} executed by {log.user_email} '
        if log.module_name:
            message += f'on {log.module_name} guid: {log.item_guid} '
        if log.duration:
            message += f'in {log.duration} seconds '
        if log.message:
            message += f'message: {log.message}'

        print(message)
