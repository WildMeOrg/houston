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

    @classmethod
    def _log_message(cls, logger, msg, *args, **kwargs):
        if current_user and not current_user.is_anonymous:
            msg = f'{msg} executed by user :{current_user.guid} {current_user.email}'
        else:
            msg += ' executed by anonymous user'
        log_kwargs = kwargs
        if 'duration' in kwargs:
            msg += f" in {kwargs['duration']} seconds"
            log_kwargs.pop('duration')

        if logger:
            logger.log(cls.AUDIT, msg, *args, **log_kwargs)
        else:
            log.log(cls.AUDIT, msg, *args, **log_kwargs)

    # logger for calling file needed as a parameter to ensure that the file and line numbers are correct in logs
    @classmethod
    def audit_log(cls, logger, msg, audit_type=AuditType.Other, *args, **kwargs):
        assert object

        cls._log_message(logger, msg, *args, **kwargs)

        from app.modules.audit_logs.models import AuditLog

        AuditLog.create(msg, audit_type, *args, **kwargs)

    @classmethod
    def audit_log_object(
        cls, logger, obj, msg='', audit_type=AuditType.Other, *args, **kwargs
    ):
        assert obj
        assert hasattr(obj, 'guid')
        assert isinstance(audit_type, cls.AuditType)

        module_name = obj.__class__.__name__
        log_msg = f'{audit_type} of {module_name} {obj.guid} {msg}'
        cls._log_message(logger, log_msg, *args, **kwargs)

        from app.modules.audit_logs.models import AuditLog

        AuditLog.create(msg, audit_type, module_name, obj.guid, *args, **kwargs)

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
                logger, obj, msg, cls.AuditType.BackEndFault, *args, **kwargs
            )
        else:
            cls.audit_log(logger, msg, cls.AuditType.BackEndFault, *args, **kwargs)

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

        msg = ''
        for patch in patch_args:

            new_msg = f"{patch['op']} {patch['field_name']}"
            if 'value' in patch:
                new_msg += f", {patch['value']} "
            else:
                new_msg += ' '

        cls.audit_log_object(logger, obj, msg, cls.AuditType.Update, *args, **kwargs)
