# -*- coding: utf-8 -*-
import datetime
import re
from unittest import mock

import pytest


# Mark this module as only working for codex.
pytestmark = [pytest.mark.only_for_codex]


# To produce the value for INDIVIDUAL_SQL_QUERY_RESULTS,
# use something like the following run within `invoke codex.shell`:
#     from app.modules.elasticsearch.tasks import create_wildbook_engine, WILDBOOK_MARKEDINDIVIDUAL_SQL_QUERY
#     engine = create_wildbook_engine()
#     print(dict(engine.execute(WILDBOOK_MARKEDINDIVIDUAL_SQL_QUERY).fetchone()))
INDIVIDUAL_SQL_QUERY_RESULTS = [
    {
        'id': '6d1d65e9-0801-4fbd-8c59-01258e9aae47',
        'name': 'IBEIS_UNKNOWN_3833',
        'nickname': '',
        'alias': None,
        'taxonomy': None,
        'sex': 'male',
        'birth': 0,
        'death': 0,
        'encounters': [
            {
                'id': '94c41ce1-f0b4-4136-af42-e2b45be512df',
                'point': '0.501208333333333,36.84964',
                'sex': 'male',
                'submitter_id': 'unknown',
                'date_occurred': '2016-01-31T02:47:00+00:00',
                'taxonomy': 'Equus grevyi',
                'has_annotation': True,
            },
            {
                'id': '71c4c176-cdbe-4e19-a8df-c63fbd909e6b',
                'point': '0.441366666666667,36.8529933333333',
                'sex': 'male',
                'submitter_id': 'unknown',
                'date_occurred': '2016-01-31T02:46:00+00:00',
                'taxonomy': 'Equus grevyi',
                'has_annotation': True,
            },
        ],
    },
    {
        'id': 'f3b2798c-5c8e-4756-9524-ee055458b726',
        'name': '01_063',
        'nickname': '',
        'alias': None,
        'taxonomy': None,
        'sex': 'unknown',
        'birth': 0,
        'death': 0,
        'encounters': [
            {
                'id': '4251b7eb-1bd7-4da0-ad4e-eef9677bd8b1',
                'point': None,
                'sex': None,
                'submitter_id': 'unknown',
                'date_occurred': '2013-01-17T11:45:00+00:00',
                'taxonomy': 'Equus quagga',
                'has_annotation': True,
            }
        ],
    },
]


ENUM_TYPE_LIST_SQL_QUERY_RESULTS = [
    ('keywordsource', ['user', 'wbia']),
    ('tokentypes', ['Bearer']),
]


ENCOUNTERS_INDEX_SQL_RESULTS = [
    {
        'id': '0001b6e4-2f31-460c-a868-03620bad8fd6',
        'point': None,
        'locationid': 'Ol Jogi',
        'sex': 'female',
        'taxonomy': 'Equus grevyi',
        'living_status': None,
        'datetime': datetime.datetime(2014, 4, 3, 21, 0),
        'timezone': '+03:00',
        'time_specificity': 'time',
        'custom_fields': '[{"4dfdde5c-5767-454a-92eb-1edb65496fe3":"bachelor"}]',
    },
    {
        'id': '4741f978-ce2e-4827-b4d8-6e12eede4784',
        'point': '0.329942743091,37.0890847601924',
        'locationid': 'Pyramid',
        'sex': 'male',
        'taxonomy': 'Equus grevyi',
        'living_status': 'alive',
        'datetime': None,
        'timezone': None,
        'time_specificity': None,
        'custom_fields': None,
    },
]


SIGHTINGS_INDEX_SQL_RESULTS = [
    {
        'id': '00012f77-f284-4c74-952b-efc43520c6fc',
        'point': None,
        'datetime': datetime.datetime(2000, 1, 1, 1, 23, 45, 678900),
        'timezone': '+00:00',
        'time_specificity': 'year',
        'taxonomy': 'Equus quagga',
        'comments': 'None',
        'custom_fields': None,
    },
    {
        'id': '00126fd2-813d-4d46-b80f-d2fba3fb7590',
        'point': None,
        'datetime': datetime.datetime(2000, 1, 1, 1, 23, 45, 678900),
        'timezone': '+00:00',
        'time_specificity': 'year',
        'taxonomy': None,
        'comments': 'None',
        'custom_fields': '[{"2fe1c780-983c-41b9-9974-44d77a9a9035":"no wind"},{"9acc33ef-caa1-4341-b475-9a5d762cd243":"Grazing"},{"9acc33ef-caa1-4341-b475-9a5d762cd243":"A second value"}]',
    },
]


def test_load_codex_indexes(monkeypatch, flask_app):
    from app.modules.elasticsearch import tasks

    # Mock the response from the wildbook database query
    mock_wildbook_engine = mock.MagicMock()
    monkeypatch.setattr(tasks, 'create_wildbook_engine', lambda: mock_wildbook_engine)
    wildbook_create_stmts = []

    def mock_wildbook_connection_execute(text_clause, *args, **kwargs):
        normalized_clause = re.sub(r'\s+', ' ', str(text_clause).lower())
        if 'from "markedindividual"' in normalized_clause:
            return INDIVIDUAL_SQL_QUERY_RESULTS
        elif 'from pg_type' in normalized_clause:
            return mock.Mock(fetchall=lambda: [])
        elif 'from "encounter"' in normalized_clause:
            return ENCOUNTERS_INDEX_SQL_RESULTS
        elif 'from "occurrence"' in normalized_clause:
            return SIGHTINGS_INDEX_SQL_RESULTS
        elif 'from information_schema.schemata' in normalized_clause:
            return mock.Mock(fetchone=lambda: None)
        elif normalized_clause.startswith('create'):
            wildbook_create_stmts.append(text_clause)
            return
        raise NotImplementedError(f'normalized_clause={normalized_clause}')

    mock_wildbook_engine.connect.return_value.__enter__.return_value = mock.Mock(
        execute=mock_wildbook_connection_execute
    )

    mock_houston_engine = mock.MagicMock()
    monkeypatch.setattr(tasks, 'create_houston_engine', lambda: mock_houston_engine)

    houston_create_stmts = []

    def mock_houston_connection_execute(text_clause, *args, **kwargs):
        normalized_clause = re.sub(r'\s+', ' ', str(text_clause).lower())
        if 'from pg_type' in normalized_clause:
            return mock.Mock(fetchall=lambda: ENUM_TYPE_LIST_SQL_QUERY_RESULTS)
        elif normalized_clause.startswith('create'):
            houston_create_stmts.append(text_clause)
            return
        raise NotImplementedError

    mock_houston_engine.connect.return_value.__enter__.return_value = mock.Mock(
        execute=mock_houston_connection_execute
    )

    # Capture elasticsearch object saving for proof checks
    from gumby.models import Individual, Encounter, Sighting

    individuals_saved = []
    monkeypatch.setattr(
        Individual, 'save', lambda individual, **kw: individuals_saved.append(individual)
    )
    encounters_saved = []
    monkeypatch.setattr(
        Encounter, 'save', lambda encounter, **kw: encounters_saved.append(encounter)
    )
    sightings_saved = []
    monkeypatch.setattr(
        Sighting, 'save', lambda sighting, **kw: sightings_saved.append(sighting)
    )

    # Call the target function
    tasks.load_codex_indexes()

    # Check import houston tables into wildbook database
    assert houston_create_stmts == []

    # Check for the expected documents within the index
    assert len(individuals_saved) == len(INDIVIDUAL_SQL_QUERY_RESULTS)
    assert [
        individual.to_dict(skip_empty=False) for individual in individuals_saved
    ] == INDIVIDUAL_SQL_QUERY_RESULTS

    assert len(encounters_saved) == len(ENCOUNTERS_INDEX_SQL_RESULTS)
    assert encounters_saved[0]['datetime'].isoformat() == '2014-04-03T21:00:00+03:00'
    assert encounters_saved[0]['time_specificity'] == 'time'
    assert encounters_saved[0]['custom_fields'] == {
        '4dfdde5c-5767-454a-92eb-1edb65496fe3': 'bachelor',
    }
    assert encounters_saved[1]['datetime'] is None
    assert encounters_saved[1]['time_specificity'] is None
    assert encounters_saved[1]['custom_fields'] is None

    assert len(sightings_saved) == len(SIGHTINGS_INDEX_SQL_RESULTS)
    assert (
        sightings_saved[0]['datetime'].isoformat() == '2000-01-01T01:23:45.678900+00:00'
    )
    assert sightings_saved[0]['time_specificity'] == 'year'
    assert sightings_saved[0]['custom_fields'] is None
    assert (
        sightings_saved[1]['datetime'].isoformat() == '2000-01-01T01:23:45.678900+00:00'
    )
    assert sightings_saved[1]['time_specificity'] == 'year'
    assert sightings_saved[1]['custom_fields'] == {
        '2fe1c780-983c-41b9-9974-44d77a9a9035': 'no wind',
        '9acc33ef-caa1-4341-b475-9a5d762cd243': ['Grazing', 'A second value'],
    }

    # rtn = tasks.load_individual_index()


def test_catchup_indexing():
    from app.modules.elasticsearch import tasks

    conf = {}
    rtn = tasks.catchup_index_set(conf)  # fail due to bad conf
    assert not rtn
    rtn = tasks.catchup_index_get()
    assert not rtn

    bdate = '1900-01-01 00:11:22'
    conf = {'before': bdate}
    tasks.catchup_index_set(conf)
    conf = tasks.catchup_index_get()
    assert conf
    assert 'before' in conf
    assert conf['before'] == bdate
    assert 'batch_size' in conf
    assert conf['batch_size'] == 250
    assert conf['sighting_mark'] == '00000000-0000-0000-0000-000000000000'
    assert conf['encounter_mark'] == '00000000-0000-0000-0000-000000000000'
    assert conf['individual_mark'] == '00000000-0000-0000-0000-000000000000'

    # test combine_names()
    row = [('foo', 'bar'), ('test', True)]
    res = tasks.combine_names(row)
    assert 'name' not in res
    row.append(('name_dict', {'context0': 'value0', 'context1': 'value1'}))
    res = tasks.combine_names(row)
    assert 'name' in res
    assert len(res['name']) == 2
    row = [('foo', 'bar'), ('test', True), ('name_dict', {'context0': 'value0', 'default': 'value1'})]
    res = tasks.combine_names(row)
    assert 'name' in res
    assert len(res['name']) == 2
    assert res['name'][0] == 'value1'

    # now blow away conf data
    tasks.catchup_index_reset()
    rtn = tasks.catchup_index_get()
    assert not rtn
