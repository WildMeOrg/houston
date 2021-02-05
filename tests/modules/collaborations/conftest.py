# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring,redefined-outer-name
import pytest

# from flask_login import current_user, login_user, logout_user

# from tests import utils

# from app.modules.users import models

from app.modules.users.models import User


@pytest.fixture()
def collab_user_a():
    # pylint: disable=unused-argument,invalid-name
    _user_a = User(
        email='trout@foo.bar',
        password='trout',
        full_name='Mr Trouty',
    )
    return _user_a


@pytest.fixture()
def collab_user_b():
    # pylint: disable=unused-argument,invalid-name
    _user_b = User(
        email='salmon@foo.bar',
        password='salmon',
        full_name='Mr Salmon',
    )
    return _user_b
