# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import datetime
import logging
from unittest import mock

import pytest

import tests.utils as test_utils
from tests.utils import module_unavailable

log = logging.getLogger(__name__)


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_encounter_add_owner(db):
    from app.modules.users.models import User

    test_user = User(
        email='testuser@localhost',
        password='testpassword',
        full_name='Gregor Samsa ',
    )

    public_owner = User.get_public_user()
    test_encounter = test_utils.generate_owned_encounter(public_owner)

    with db.session.begin():
        db.session.add(test_encounter)
        db.session.add(test_user)

    db.session.refresh(test_encounter)
    db.session.refresh(test_user)

    assert test_encounter.get_owner() is public_owner

    test_user.owned_encounters.append(test_encounter)

    with db.session.begin():
        db.session.add(test_encounter)
        db.session.add(test_user)

    db.session.refresh(test_encounter)
    db.session.refresh(test_user)

    assert test_encounter.get_owner() is not None
    assert test_encounter.get_owner().guid == test_user.guid
    test_encounter.delete()


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_encounter_set_individual(db, empty_individual, encounter_1):

    assert empty_individual is not None
    encounter_1.set_individual(empty_individual)
    assert encounter_1.individual is not None
    assert encounter_1.individual.guid == empty_individual.guid


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_owned_encounters_ordering(db, request):
    from app.modules.encounters.models import Encounter
    from app.modules.users.models import User

    public_owner = User.get_public_user()
    encounters = []
    for i in range(10):
        encounters.append(Encounter(owner=public_owner))

    encounters.sort(key=lambda e: e.guid)

    def cleanup():
        for encounter in encounters:
            db.session.delete(encounter)

    request.addfinalizer(cleanup)

    assert public_owner.owned_encounters == encounters


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_encounter_time(db, request):
    from app.modules.complex_date_time.models import ComplexDateTime, Specificities
    from app.modules.encounters.models import Encounter
    from app.modules.users.models import User

    public_owner = User.get_public_user()
    test_encounter = test_utils.generate_owned_encounter(public_owner)
    request.addfinalizer(test_encounter.delete)

    dt = datetime.datetime.utcnow()
    cdt = ComplexDateTime(dt, 'US/Pacific', Specificities.day)
    test_encounter.time = cdt
    with db.session.begin():
        db.session.add(test_encounter)

    again = Encounter.query.get(test_encounter.guid)
    assert cdt.isoformat_in_timezone() == again.time.isoformat_in_timezone()


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_get_taxonomy_names(db, request):
    from app.modules.encounters.models import Encounter
    from app.modules.site_settings.models import SiteSetting

    orig_site_species = SiteSetting.get_value('site.species')
    request.addfinalizer(
        lambda: SiteSetting.set_key_value('site.species', orig_site_species)
    )

    quagga_guid = 'e46c8573-90a3-4992-80d6-79ad51af4cd5'
    grevyi_guid = 'bb5d6625-0d27-4a2d-95f5-c6d8d5af5124'
    SiteSetting.set_key_value(
        'site.species',
        [
            {
                'commonNames': ['Quagga'],
                'scientificName': 'Equus quagga quagga',
                'itisTsn': 926245,
                'id': quagga_guid,
            },
            {
                'commonNames': ['Grevyi'],
                'scientificName': 'Equus grevyi',
                'id': grevyi_guid,
            },
        ],
    )

    encounter = mock.Mock()
    encounter.get_taxonomy_guid.return_value = quagga_guid
    encounter.get_taxonomy_names.side_effect = lambda: Encounter.get_taxonomy_names(
        encounter
    )
    assert encounter.get_taxonomy_names() == ['Quagga', 'Equus quagga quagga']
