# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
def test_raising_faults():
    from app.modules.audit_logs.models import AuditLog
    import app.extensions.logging as AuditLogExtension  # NOQA

    houston_fault_msg = (
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
    )
    AuditLogExtension.houston_fault(None, houston_fault_msg)
    houston_faults = (
        AuditLog.query.filter_by(audit_type=AuditLogExtension.AuditType.HoustonFault)
        .order_by(AuditLog.created)
        .all()
    )
    houston_faults.reverse()
    assert houston_fault_msg in houston_faults[0].message
    backend_fault_msg = (
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
    )
    AuditLogExtension.backend_fault(None, backend_fault_msg)
    backend_faults = (
        AuditLog.query.filter_by(audit_type=AuditLogExtension.AuditType.BackEndFault)
        .order_by(AuditLog.created)
        .all()
    )
    backend_faults.reverse()
    assert backend_fault_msg in backend_faults[0].message
