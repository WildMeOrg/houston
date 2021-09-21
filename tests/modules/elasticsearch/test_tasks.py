# -*- coding: utf-8 -*-
from unittest import mock


# To produce the value for SQL_QUERY_RESULTS,
# use something like the following run within `invoke app.shell`:
#     from app.modules.elasticsearch.tasks import create_wildbook_engine, WILDBOOK_MARKEDINDIVIDUAL_SQL_QUERY
#     engine = create_wildbook_engine()
#     print(dict(engine.execute(WILDBOOK_MARKEDINDIVIDUAL_SQL_QUERY).fetchone()))
SQL_QUERY_RESULTS = [
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


def test_load_indexes(monkeypatch, flask_app):
    from app.modules.elasticsearch import tasks

    # Mock the response from the wildbook database query
    mock_engine = mock.MagicMock()
    monkeypatch.setattr(tasks, 'create_wildbook_engine', lambda: mock_engine)
    mock_engine.connect.return_value.__enter__.return_value.execute.return_value = (
        SQL_QUERY_RESULTS
    )
    # Capture elasticsearch object saving for proof checks
    captures = []
    capture_save = lambda self, **kwargs: captures.append([self, kwargs])  # noqa: E731
    from gumby.models import Individual

    monkeypatch.setattr(Individual, 'save', capture_save)

    # Call the target function
    tasks.load_indexes()

    # Check for the expected documents within the index
    assert len(captures) == len(SQL_QUERY_RESULTS)
    assert [s.to_dict(skip_empty=False) for s, kw in captures] == SQL_QUERY_RESULTS
