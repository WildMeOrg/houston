# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring,redefined-outer-name
import pytest

from app.modules.encounters.models import Encounter
from app.modules.individuals.models import Individual
from app.modules.users.models import User


def _basic_user():
    _user = User(email='test@user', password='testuser', full_name='Test User')
    return _user


@pytest.fixture()
def encounter_a():
    # pylint: disable=unused-argument,invalid-name
    _encounter = Encounter(owner=_basic_user())
    return _encounter


@pytest.fixture()
def encounter_b():
    # pylint: disable=unused-argument,invalid-name
    _encounter = Encounter(owner=_basic_user())
    return _encounter


@pytest.fixture()
def empty_individual():
    # pylint: disable=unused-argument,invalid-name
    _individual = Individual()
    return _individual
