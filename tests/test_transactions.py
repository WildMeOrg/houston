# -*- coding: utf-8 -*-
from app.extensions.api import api_v1, Namespace, http_exceptions
from app.modules.users.models import User
from app.modules.users.schemas import DetailedUserSchema
from flask import got_request_exception
from flask_marshmallow import base_fields
from flask_restx_patched import Resource, Parameters
from flask_restx_patched._http import HTTPStatus
import pytest
import sqlalchemy


class TransactionParameters(Parameters):
    guid = base_fields.UUID()
    email = base_fields.String()
    full_name = base_fields.String()
    locale = base_fields.String()
    website = base_fields.String()


def setup_request_transaction(transaction_api, flask_app, db):
    def before_request_func():
        db.session.begin()

    def after_request_func(response):
        try:
            db.session.commit()
        except:  # noqa
            db.session.rollback()
        return response

    try:
        # This is @flask_app.before_request
        before_request_func = flask_app.before_request(before_request_func)
        # This is @flask_app.after_request
        after_request_func = flask_app.after_request(after_request_func)
    except AssertionError:
        pytest.skip('Test expected to be run on its own')

    class TransactionResources(Resource):
        @transaction_api.parameters(TransactionParameters())
        @transaction_api.response(DetailedUserSchema())
        def get(self, args):
            user = User.query.get(args.get('guid'))
            user.full_name = args.get('full_name')
            user.locale = args.get('locale')
            db.session.merge(user)
            with db.session.begin(subtransactions=True):
                user.website = args.get('website')
                db.session.merge(user)
            user.email = args.get('email')
            db.session.merge(user)
            return user

    return TransactionResources


def setup_commit_or_abort(transaction_api, flask_app, db):
    class TransactionResources(Resource):
        @transaction_api.parameters(TransactionParameters())
        @transaction_api.response(DetailedUserSchema())
        def get(self, args):
            user = User.query.get(args.get('guid'))
            context = transaction_api.commit_or_abort(db.session)
            with context:
                user.full_name = args.get('full_name')
                user.locale = args.get('locale')
                db.session.merge(user)
                with db.session.begin(subtransactions=True):
                    user.website = args.get('website')
                    db.session.merge(user)
            # Just to make sure it's ok to do subtransactions=True when
            # it's not a subtransaction
            with db.session.begin(subtransactions=True):
                user.email = args.get('email')
                db.session.merge(user)

            return user

    return TransactionResources


@pytest.mark.separate
@pytest.mark.parametrize('setup_type', ('request_transaction', 'commit_or_abort'))
def test_transactions(flask_app, flask_app_client, db, regular_user, request, setup_type):
    orig_email = regular_user.email
    orig_full_name = regular_user.full_name
    orig_locale = regular_user.locale
    orig_website = regular_user.website

    def reset_regular_user():
        regular_user.email = orig_email
        regular_user.full_name = orig_full_name
        regular_user.locale = orig_locale
        regular_user.website = orig_website
        db.session.add(regular_user)

    request.addfinalizer(reset_regular_user)

    transaction_api = Namespace('test-transactions')
    api_v1.add_namespace(transaction_api)
    TransactionResources = globals()[f'setup_{setup_type}'](
        transaction_api, flask_app, db
    )

    def signal_handler(sender, exception, **extra):
        if isinstance(exception, sqlalchemy.exc.DataError):
            http_exceptions.abort(code=HTTPStatus.CONFLICT, message=str(exception))

    # Instead of catching exceptions in api/extensions/api/http_exceptions.py?
    got_request_exception.connect(signal_handler)

    try:
        # This is @transaction_api.route('/')
        TransactionResources = transaction_api.route('/')(TransactionResources)
    except AssertionError:
        pytest.skip('Test expected to be run on its own')

    # locale too long
    resp = flask_app_client.get(
        '/api/v1/test-transactions/',
        query_string={
            'guid': regular_user.guid,
            'email': 'nobody@example.org',
            'full_name': 'First',
            'locale': 'more than twenty characters',
            'website': 'https://example.org/',
        },
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    # make sure no changes are committed
    refreshed_user = User.query.get(regular_user.guid)
    assert refreshed_user.email == orig_email
    assert refreshed_user.full_name == orig_full_name
    assert refreshed_user.locale == orig_locale
    assert refreshed_user.website is None

    # website too long
    resp = flask_app_client.get(
        '/api/v1/test-transactions/',
        query_string={
            'guid': regular_user.guid,
            'email': 'nobody@example.org',
            'full_name': 'First',
            'locale': 'FR',
            'website': 'https://www.example.org/?{}'.format('a' * 100),
        },
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    # make sure no changes are committed
    refreshed_user = User.query.get(regular_user.guid)
    assert refreshed_user.email == orig_email
    assert refreshed_user.full_name == orig_full_name
    assert refreshed_user.locale == orig_locale
    assert refreshed_user.website is None

    resp = flask_app_client.get(
        '/api/v1/test-transactions/',
        query_string={
            'guid': regular_user.guid,
            'email': 'nobody@example.org',
            'full_name': 'First',
            'locale': 'FR',
            'website': 'https://www.example.org/',
        },
    )
    assert resp.status_code == 200
    refreshed_user = User.query.get(regular_user.guid)
    assert resp.json['email'] == refreshed_user.email == 'nobody@example.org'
    assert resp.json['full_name'] == refreshed_user.full_name == 'First'
    assert refreshed_user.locale == 'FR'
    assert resp.json['website'] == refreshed_user.website == 'https://www.example.org/'
