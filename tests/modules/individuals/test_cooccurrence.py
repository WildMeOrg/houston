# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

from app.modules.users.models import User
import tests.utils as test_utils


def test_cooccurrence(db, flask_app_client, researcher_1):
    from app.modules.sightings.models import Sighting, SightingStage
    from app.modules.individuals.models import Individual

    sighting = Sighting(stage=SightingStage.processed)
    owner = User.get_public_user()

    encounter_a = test_utils.generate_owned_encounter(owner)
    individual_1 = Individual()
    individual_1.add_encounter(encounter_a)
    sighting.add_encounter(encounter_a)

    encounter_b = test_utils.generate_owned_encounter(owner)
    individual_2 = Individual()
    individual_2.add_encounter(encounter_b)
    sighting.add_encounter(encounter_b)

    encounter_c = test_utils.generate_owned_encounter(owner)
    individual_3 = Individual()
    individual_3.add_encounter(encounter_c)
    sighting.add_encounter(encounter_c)

    assert len(sighting.get_encounters()) == 3

    with db.session.begin():
        db.session.add(sighting)
        db.session.add(encounter_a)
        db.session.add(encounter_b)
        db.session.add(encounter_c)
        db.session.add(individual_1)
        db.session.add(individual_2)
        db.session.add(individual_3)

    pals = individual_1.get_cooccurring_individuals()
    assert set(pals) == set([individual_2, individual_3])

    # since its all set up, lets test api as well
    with flask_app_client.login(researcher_1, auth_scopes=('individuals:read',)):
        response = flask_app_client.get(
            f'/api/v1/individuals/{str(individual_1.guid)}/cooccurrence'
        )
    assert len(response.json) == 2
    assert set([response.json[0]['guid'], response.json[1]['guid']]) == set(
        [str(individual_2.guid), str(individual_3.guid)]
    )

    # tests indiv.get_shared_sightings(list_individual_guids)
    individual_4 = Individual()
    sighting_two = Sighting(stage=SightingStage.processed)
    encounter_d = test_utils.generate_owned_encounter(owner)
    individual_1.add_encounter(encounter_d)
    encounter_e = test_utils.generate_owned_encounter(owner)
    individual_2.add_encounter(encounter_e)
    encounter_f = test_utils.generate_owned_encounter(owner)
    individual_4.add_encounter(encounter_f)
    sighting_two.add_encounter(encounter_d)
    sighting_two.add_encounter(encounter_e)
    sighting_two.add_encounter(encounter_f)

    with db.session.begin():
        db.session.add(individual_4)
        db.session.add(sighting_two)
        db.session.add(encounter_d)
        db.session.add(encounter_e)

    with_2 = individual_1.get_shared_sightings(individual_2)
    assert set(with_2) == set([sighting, sighting_two])
    with_3 = individual_1.get_shared_sightings(individual_3)
    assert with_3 == [sighting]
    empty = individual_4.get_shared_sightings(individual_3)
    assert len(empty) == 0
    with_2_3 = individual_1.get_shared_sightings(individual_2, individual_3)
    assert with_2_3 == [sighting]

    db.session.delete(individual_1)
    db.session.delete(individual_2)
    db.session.delete(individual_3)
    db.session.delete(individual_4)
    db.session.delete(encounter_a)
    db.session.delete(encounter_b)
    db.session.delete(encounter_c)
    db.session.delete(encounter_d)
    db.session.delete(encounter_e)
    db.session.delete(encounter_f)
    db.session.delete(sighting)
    db.session.delete(sighting_two)
