# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring


def test_BaseUserSchema_dump_empty_input():
    from app.modules.users import schemas

    dumped_result = schemas.BaseUserSchema().dump({})
    assert dumped_result.errors == {}
    assert dumped_result.data == {}


def test_BaseUserSchema_dump_user_instance(user_instance):
    from app.modules.users import schemas

    user_instance.password = 'password'
    dumped_result = schemas.BaseUserSchema().dump(user_instance)
    assert dumped_result.errors == {}
    assert 'password' not in dumped_result.data
    assert set(dumped_result.data.keys()) == {
        'guid',
        'email',
        'full_name',
    }


def test_DetailedUserSchema_dump_user_instance(user_instance):
    from app.modules.users import schemas

    user_instance.password = 'password'
    dumped_result = schemas.DetailedUserSchema().dump(user_instance)
    assert dumped_result.errors == {}
    assert 'password' not in dumped_result.data
    assert set(dumped_result.data.keys()) == {
        'guid',
        'email',
        'full_name',
        'created',
        'updated',
        'viewed',
        'is_active',
        'is_staff',
        'is_admin',
        'profile_fileupload',
        'affiliation',
        'location',
        'forum_id',
        'website',
    }


def test_ReCaptchaPublicServerKeySchema_dump():
    from app.modules.auth import schemas

    form_data = {'recaptcha_public_key': 'key'}
    dumped_result = schemas.ReCaptchaPublicServerKeySchema().dump(form_data)
    assert dumped_result.errors == {}
    assert dumped_result.data == form_data
