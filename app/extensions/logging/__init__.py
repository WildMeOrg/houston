# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import logging
from flask_login import current_user  # NOQA
import enum

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Logging(object):
    """
    This is a helper extension, which adjusts logging configuration for the
    application.
    """

    # somewhere between Error and Critical to guarantee that it appears in the logs but is not interpreted as a
    # real error by the reader
    AUDIT = 45

    class AuditType(str, enum.Enum):
        UserCreate = 'User Create'
        SystemCreate = 'System Create'
        Delete = 'Delete'
        Update = 'Update'  # Generic Update
        FrontEndFault = 'Front End Fault'  # Bad message received on API
        BackEndFault = 'Back End Fault'  # Faulty message received from ACM/EDM etc
        HoustonFault = 'Houston Fault'  # Internal Error within Houston
        Other = 'Other'  # None of the above

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        """
        Common Flask interface to initialize the logging according to the
        application configuration.
        """
        # We don't need the default Flask's loggers when using our invoke tasks
        # since we set up beautiful colorful loggers globally.
        for handler in list(app.logger.handlers):
            app.logger.removeHandler(handler)
        app.logger.propagate = True

        if app.debug:
            logging.getLogger('flask_oauthlib').setLevel(logging.DEBUG)
            app.logger.setLevel(logging.DEBUG)

        # We don't need the default SQLAlchemy loggers when using our invoke
        # tasks since we set up beautiful colorful loggers globally.
        # NOTE: This particular workaround is for the SQLALCHEMY_ECHO mode,
        # when all SQL commands get printed (without these lines, they will get
        # printed twice).
        sqla_logger = logging.getLogger('sqlalchemy.engine.base.Engine')
        for hdlr in list(sqla_logger.handlers):
            sqla_logger.removeHandler(hdlr)
        sqla_logger.addHandler(logging.NullHandler())

        logging.addLevelName(self.AUDIT, 'AUDIT')

    # logger for calling file needed as a parameter to ensure that the file and line numbers are correct in logs
    @classmethod
    def audit_log(cls, logger, msg, audit_type=AuditType.Other, *args, **kwargs):
        assert object

        user_email = 'anonymous user'
        if current_user and not current_user.is_anonymous:
            msg = f'{msg} executed by user :{current_user.guid} {current_user.email}'
            user_email = current_user.email
        else:
            msg = f' {msg} executed by anonymous user'
        if logger:
            logger.log(cls.AUDIT, msg, *args, **kwargs)
        else:
            log.log(cls.AUDIT, msg, *args, **kwargs)

        from app.modules.audit_logs.models import AuditLog

        AuditLog.create(msg, audit_type, user_email)

    @classmethod
    def audit_log_object(
        cls, logger, obj, msg='', audit_type=AuditType.Other, *args, **kwargs
    ):
        assert obj
        assert hasattr(obj, 'guid')
        assert isinstance(audit_type, cls.AuditType)
        orig_msg = msg

        module_name = obj.__class__.__name__
        msg = f'{audit_type} of {module_name} {obj.guid} {msg}'
        user_email = 'anonymous user'
        if current_user and not current_user.is_anonymous:
            msg = f'{msg} executed by user :{current_user.guid} {current_user.email}'
            user_email = current_user.email
        else:
            msg = f' {msg} executed by anonymous user'
        logger.log(cls.AUDIT, msg, *args, **kwargs)
        from app.modules.audit_logs.models import AuditLog

        AuditLog.create(orig_msg, audit_type, user_email, module_name, obj.guid)

    @classmethod
    def user_create_object(cls, logger, obj, msg='', *args, **kwargs):
        cls.audit_log_object(logger, obj, msg, cls.AuditType.UserCreate, *args, **kwargs)

    @classmethod
    def system_create_object(cls, logger, obj, msg='', *args, **kwargs):
        cls.audit_log_object(logger, obj, msg, cls.AuditType.UserCreate, *args, **kwargs)

    @classmethod
    def backend_fault(cls, logger, msg='', obj=None, *args, **kwargs):
        if obj:
            cls.audit_log_object(
                logger, obj, msg, cls.AuditType.BackendFault, *args, **kwargs
            )
        else:
            cls.audit_log(logger, msg, cls.AuditType.BackendFault, *args, **kwargs)

    @classmethod
    def houston_fault(cls, logger, msg='', obj=None, *args, **kwargs):
        if obj:
            cls.audit_log_object(
                logger, obj, msg, cls.AuditType.HoustonFault, *args, **kwargs
            )
        else:
            cls.audit_log(logger, msg, cls.AuditType.HoustonFault, *args, **kwargs)

    @classmethod
    def delete_object(cls, logger, obj, msg='', *args, **kwargs):
        cls.audit_log_object(logger, obj, msg, cls.AuditType.Delete, *args, **kwargs)

    @classmethod
    def patch_object(cls, logger, obj, patch_args, *args, **kwargs):
        from app.modules.audit_logs.models import AuditMaxMessageLength

        msg = ''
        for patch in patch_args:

            new_msg = f"{patch['op']} {patch['field_name']}"
            if 'value' in patch:
                new_msg += f", {patch['value']} "
            else:
                new_msg += ' '
            # If the message gets too long, spread it across multiple audit entries
            if len(new_msg) + len(msg) >= AuditMaxMessageLength:
                cls.audit_log_object(
                    logger, obj, msg, cls.AuditType.Update, *args, **kwargs
                )
                msg = new_msg
            else:
                msg += new_msg

        cls.audit_log_object(logger, obj, msg, cls.AuditType.Update, *args, **kwargs)
