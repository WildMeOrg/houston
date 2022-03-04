# -*- coding: utf-8 -*-
import pytest

from tests.utils import extension_unavailable


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'), reason='Elasticsearch extension disabled'
)
def test_indexing_with_elasticsearch(db, flask_app_client):
    from app.extensions import elasticsearch as es
    from app.modules.users.models import User
    from app.modules.assets.models import AssetTags

    assert User in es.REGISTERED_MODELS
    assert AssetTags not in es.REGISTERED_MODELS

    User.index_all()
    AssetTags.index_all()


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'), reason='Elasticsearch extension disabled'
)
def test_index_cls_conversion(db, flask_app_client, admin_user):
    from app.extensions import elasticsearch as es
    from app.modules.users.models import User

    index = es.get_elasticsearch_index_name(User)
    cls = es.get_elasticsearch_cls_from_index(index)
    assert cls == User
