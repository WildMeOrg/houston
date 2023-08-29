# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import pytest

from tests import utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_get_set_individual_names(
    db, flask_app_client, researcher_1, researcher_2, request, test_root
):

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root
    )
    sighting_guid = uuids['sighting']
    from app.modules.sightings.models import Sighting

    sighting = Sighting.query.get(sighting_guid)
    assert sighting

    assert len(sighting.encounters) > 0
    enc = sighting.encounters[0]
    bad_guid = '00000000-0000-0000-2170-000000000000'

    # first we try with bunk data for one name
    individual_data_in = {
        'names': [
            {'context': 'A', 'value': 'value-A'},
            {'conxxxx': 'B', 'value': 'value-B'},
        ],
        'encounters': [{'id': str(enc.guid)}],
    }
    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 400, individual_data_in
    )

    # now with bunk preferring_users user guid, but name fixed
    individual_data_in = {
        'names': [
            {'context': 'A', 'value': 'value-A'},
            {'context': 'B', 'value': 'value-B', 'preferring_users': [bad_guid]},
        ],
        'encounters': [{'id': str(enc.guid)}],
    }
    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 400, individual_data_in
    )

    # fix the name and preferring_users and try again (will make our individual)
    individual_data_in['names'][1] = {
        'context': 'B',
        'value': 'value-B',
        # TODO FIXME  POST + preferring_users is currently now working
        # 'preferring_users': [{'guid':str(researcher_1.guid)}],
    }
    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    assert individual_response.json['guid'] is not None
    individual_id = individual_response.json['guid']
    request.addfinalizer(
        lambda: individual_utils.delete_individual(
            flask_app_client, researcher_1, individual_id
        )
    )

    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json

    assert len(sighting.individuals) == 1
    test_ind = next(iter(sighting.individuals))
    assert individual_json['guid'] == str(test_ind.guid)
    assert sighting.get_individual_names() == {'value-A', 'value-B'}
    assert sighting.get_individual_names_with_contexts() == {
        'A': {'value-A'},
        'B': {'value-B'},
    }

    # invalid value
    patch_data = [
        utils.patch_add_op('names', 'FAIL'),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )
    assert 'value must contain keys' in patch_individual_response.json.get('message')

    test_context = 'test-context'
    test_value = 'test-value'

    # this should fail cuz of bad user_guid in preferring_users
    patch_data = [
        utils.patch_add_op(
            'names',
            {
                'context': test_context,
                'value': test_value,
                'preferring_users': [bad_guid],
            },
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )
    assert patch_individual_response.json['message'] == f'invalid user guid {bad_guid}'

    # now this should work
    patch_data = [
        utils.patch_add_op(
            'names',
            {
                'context': test_context,
                'value': test_value,
                'preferring_users': [str(researcher_1.guid)],
            },
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client, researcher_1, individual_id, patch_data
    )
    assert patch_individual_response.json['guid'] == individual_id
    assert len(patch_individual_response.json['names']) == 3
    assert patch_individual_response.json['names'][2]['context'] == test_context
    assert patch_individual_response.json['names'][2]['value'] == test_value
    assert len(patch_individual_response.json['names'][2]['preferring_users']) == 1
    name_guid = patch_individual_response.json['names'][2]['guid']

    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, patch_individual_response.json['guid']
    ).json
    assert individual_json['names'] == patch_individual_response.json['names']

    # add a second one for kicks
    patch_data = [
        utils.patch_add_op('names', {'context': 'context2', 'value': test_value}),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client, researcher_1, individual_id, patch_data
    )
    assert len(patch_individual_response.json['names']) == 4

    # "test-value" is duplicated across 2 names, but only appears here once:
    assert sighting.get_individual_names() == {'test-value', 'value-A', 'value-B'}
    assert sighting.get_individual_names_with_contexts() == {
        'A': {'value-A'},
        'B': {'value-B'},
        'test-context': {'test-value'},
        'context2': {'test-value'},
    }

    # now this should conflict (409) due to duplicate context
    patch_data = [
        utils.patch_add_op('names', {'context': test_context, 'value': 'name-o'}),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )

    # now lets remove one (but invalid Name guid)
    patch_data = [
        utils.patch_remove_op('names', bad_guid),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )
    assert (
        patch_individual_response.json.get('message') == f'invalid name guid {bad_guid}'
    )

    # now really remove one
    patch_data = [
        utils.patch_remove_op('names', name_guid),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client, researcher_1, individual_id, patch_data
    )
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json
    assert len(individual_json['names']) == 3
    name_guid = individual_json['names'][2]['guid']

    # op=replace, but with a bad name guid
    replacement_value = 'some new value'
    patch_data = [
        utils.patch_replace_op(
            'names',
            {'guid': bad_guid, 'context': 'new-context', 'value': replacement_value},
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )
    assert (
        patch_individual_response.json.get('message') == f'invalid name guid {bad_guid}'
    )

    # op=replace, valid name guid, but bad context/value
    patch_data = [
        utils.patch_replace_op('names', {'guid': name_guid, 'foo': 'bar'}),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )
    assert 'value must contain' in patch_individual_response.json.get('message')

    # op=replace, just replace value
    patch_data = [
        utils.patch_replace_op(
            'names',
            {'guid': name_guid, 'value': replacement_value},
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client, researcher_1, individual_id, patch_data
    )
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json
    assert len(individual_json['names']) == 3
    assert individual_json['names'][2]['context'] == 'context2'
    assert individual_json['names'][2]['value'] == replacement_value

    # op=replace, try to replace context, but with one that exists
    patch_data = [
        utils.patch_replace_op(
            'names',
            {'guid': name_guid, 'context': 'A'},
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )

    # op=replace, valid context change
    patch_data = [
        utils.patch_replace_op(
            'names',
            {'guid': name_guid, 'context': 'C1'},
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client, researcher_1, individual_id, patch_data
    )
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json
    assert individual_json['names'][2]['context'] == 'C1'
    assert individual_json['names'][2]['value'] == replacement_value

    # op=replace, valid context and value change
    patch_data = [
        utils.patch_replace_op(
            'names',
            {'guid': name_guid, 'context': 'C', 'value': 'name-C'},
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client, researcher_1, individual_id, patch_data
    )
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json
    assert individual_json['names'][2]['context'] == 'C'
    assert individual_json['names'][2]['value'] == 'name-C'

    # op=add, but add a preferring_user to an existing name
    patch_data = [
        utils.patch_add_op(
            'names',
            {'guid': name_guid, 'preferring_user': str(researcher_1.guid)},
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client, researcher_1, individual_id, patch_data
    )
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json
    assert len(individual_json['names'][2]['preferring_users']) == 1
    assert individual_json['names'][2]['preferring_users'][0]['guid'] == str(
        researcher_1.guid
    )

    # op=add, but add a preferring_user *but not current_user* so it should fail
    patch_data = [
        utils.patch_add_op(
            'names',
            {'guid': name_guid, 'preferring_user': str(researcher_2.guid)},
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )
    assert (
        patch_individual_response.json['message']
        == f'invalid user guid {str(researcher_2.guid)}'
    )

    # op=add, preferring_user, but an invalid user guid
    patch_data = [
        utils.patch_add_op(
            'names',
            {'guid': name_guid, 'preferring_user': bad_guid},
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )
    assert patch_individual_response.json['message'] == f'invalid user guid {bad_guid}'

    # remove preferring_user, bad user guid
    patch_data = [
        utils.patch_remove_op('names', {'guid': name_guid, 'preferring_user': bad_guid}),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
        expected_status_code=409,
    )
    assert patch_individual_response.json['message'] == f'invalid user guid {bad_guid}'

    # remove preferring_user, but this should work
    patch_data = [
        utils.patch_remove_op(
            'names', {'guid': name_guid, 'preferring_user': str(researcher_1.guid)}
        ),
    ]
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        patch_data,
    )
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json
    assert len(individual_json['names'][2]['preferring_users']) == 0


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_get_by_name(db, flask_app_client, researcher_1, request, test_root):
    from app.modules.individuals.models import Individual
    from app.modules.names.models import DEFAULT_NAME_CONTEXT
    from app.utils import HoustonException

    individual_1_id = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': DEFAULT_NAME_CONTEXT, 'value': 'Zebra 1'},
                {'context': 'nickname', 'value': 'Nick'},
            ],
        },
    )['individual']
    individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': 'nickname', 'value': 'Nick'},
            ],
        },
    )['individual']
    individual_3_id = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': 'nickname', 'value': 'Nick Jr.'},
            ],
        },
    )['individual']

    ind1 = Individual.get_by_name('Zebra 1')
    assert str(ind1.guid) == individual_1_id

    try:
        Individual.get_by_name('Nick', context='nickname')
        assert False, 'error not thrown on duplicate names'
    except HoustonException:
        pass

    ind3 = Individual.get_by_name('Nick Jr.', context='nickname')
    assert str(ind3.guid) == individual_3_id

    none_ind = Individual.get_by_name('Nick Jr.')
    assert not none_ind


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_name_validation(
    db, flask_app_client, researcher_1, researcher_2, request, test_root
):
    from app.modules.names.models import DEFAULT_NAME_CONTEXT

    individual_1_id = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': DEFAULT_NAME_CONTEXT, 'value': 'Zebra Prime'},
                {'context': 'nickname', 'value': 'Big Dog'},
            ],
        },
    )['individual']
    individual_2_id = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': DEFAULT_NAME_CONTEXT, 'value': 'Zebra Omega'},
            ],
        },
    )['individual']
    individual_3_id = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': DEFAULT_NAME_CONTEXT, 'value': 'Zebra Omega'},
            ],
        },
    )['individual']

    flatfile_query = [
        ['Zebra Prime', 0],
        ['Big Dog', 1],
        ['Big Dog', 2],
        ['', 3],
        [None, 4],
        ['  ', 5],
        ['Zebra Omega', 6],
        ['Jennifer', 100],
    ]

    individual_utils.validate_names(
        flask_app_client, researcher_1, {'bad_data': 100}, expected_status_code=500
    )

    validation_resp = individual_utils.validate_names(
        flask_app_client, researcher_1, flatfile_query
    )

    desired_resp = [
        [
            {
                'value': 'Zebra Prime',
                'info': [
                    {
                        'message': f'Corresponds to existing individual {individual_1_id}.',
                        'level': 'info',
                    }
                ],
            },
            0,
        ],
        [
            {
                'value': 'Big Dog',
                'info': [
                    {
                        'message': 'ERROR: cannot resolve this name to an existing individual. New name creation is not yet supported in bulk upload.',
                        'level': 'error',
                    }
                ],
            },
            1,
        ],
        [
            {
                'value': 'Big Dog',
                'info': [
                    {
                        'message': 'ERROR: cannot resolve this name to an existing individual. New name creation is not yet supported in bulk upload.',
                        'level': 'error',
                    }
                ],
            },
            2,
        ],
        [
            {
                'value': 'Zebra Omega',
                'info': [
                    {
                        'message': f"ERROR: cannot resolve this name to a unique individual. Individuals sharing this name are ['{individual_2_id}', '{individual_3_id}'].",
                        'level': 'error',
                    }
                ],
            },
            6,
        ],
        [
            {
                'value': 'Jennifer',
                'info': [
                    {
                        'message': 'ERROR: cannot resolve this name to an existing individual. New name creation is not yet supported in bulk upload.',
                        'level': 'error',
                    }
                ],
            },
            100,
        ],
    ]

    assert validation_resp.json == desired_resp
