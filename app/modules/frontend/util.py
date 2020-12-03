from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from app.modules.users.models import User
import logging

log = logging.getLogger(__name__)

def ensure_admin_exists(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user and not User.adminUserInitialized():
            return redirect(url_for('backend.admin_init'))
        return func(*args, **kwargs)
    return decorated_function