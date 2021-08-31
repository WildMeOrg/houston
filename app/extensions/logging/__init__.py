# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import logging
import enum
from flask_login import current_user  # NOQA


class AuditType(str, enum.Enum):
    Create = 'Create'
    Delete = 'Delete'
    Update = 'Update'  # Generic Update


# somewhere between Error and Critical
AUDIT = 45


# logger for calling file needed as a parameter to ensure that the file and line numbers are correct in logs
def audit_log(logger, msg, *args, **kwargs):
    assert object

    # First iteration. Timestamp added by logger so no need to add manually
    if current_user is not None and not current_user.is_anonymous:
        msg = f'{msg} executed by user :{current_user.guid} {current_user.email}'
    else:
        msg = f' {msg} executed by anonymous user'
    logger.log(AUDIT, msg, *args, **kwargs)


# As per above but this time an object must be passed that must have a guid member
def audit_log_object(logger, obj, audit_type, msg, *args, **kwargs):
    assert obj
    assert hasattr(obj, 'guid')
    assert isinstance(audit_type, AuditType)

    msg = f'{audit_type} of {obj.__class__.__name__} {obj.guid} {msg}'
    # First iteration. Timestamp added by logger so no need to add manually
    if current_user is not None and not current_user.is_anonymous:
        msg = f'{msg} executed by user :{current_user.guid} {current_user.email}'
    else:
        msg = f' {msg} executed by anonymous user'
    logger.log(AUDIT, msg, *args, **kwargs)


class Logging(object):
    """
    This is a helper extension, which adjusts logging configuration for the
    application.
    """

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

        logging.addLevelName(AUDIT, 'AUDIT')
