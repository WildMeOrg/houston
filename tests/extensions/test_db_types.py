# -*- coding: utf-8 -*-
import datetime
import uuid

from sqlalchemy.sql.sqltypes import JSON


def test_json(db):
    class ExampleJson(db.Model):
        guid = db.Column(db.GUID, default=uuid.uuid4, primary_key=True)
        value = db.Column(db.JSON(none_as_null=True), nullable=True)

    json_null = ExampleJson(value=JSON.NULL)
    python_none = ExampleJson(value=None)

    test_uuid = uuid.uuid4()
    test_datetime = datetime.datetime(2021, 6, 1, 10, 28, 3)
    python_dict = ExampleJson(
        value={
            'test_uuid': test_uuid,
            'test_datetime': test_datetime,
            'plain': 'text',
        }
    )

    db.create_all()
    db.session.add(json_null)
    db.session.add(python_none)
    db.session.add(python_dict)

    assert ExampleJson.query.get(json_null.guid).value is None
    assert ExampleJson.query.get(python_none.guid).value is None
    assert ExampleJson.query.get(python_dict.guid).value == {
        'test_uuid': str(test_uuid),
        'test_datetime': test_datetime,
        'plain': 'text',
    }
