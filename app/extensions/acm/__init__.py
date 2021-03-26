# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Asset Curation Model (ACM) manager.

"""

from flask import current_app, request, session, render_template  # NOQA
from flask_login import current_user  # NOQA
from app.extensions.restManager.RestManager import RestManager
from app.extensions import db
import logging
import uuid
import keyword
import types
import sqlalchemy

KEYWORD_SET = set(keyword.kwlist)

log = logging.getLogger(__name__)


class ACMManager(RestManager):
    # pylint: disable=abstract-method
    """"""
    NAME = 'ACM'
    ENDPOINT_PREFIX = 'api'
    # We use // as a shorthand for prefix
    # fmt: off
    ENDPOINTS = {
        # No user.session, wbia doesn't support logins
        'annotations': {
            'list': '//annot/json/',
            'data': '//annot/name/uuid/json/?annot_uuid_list=[{"__UUID__": "%s"}]',
        },
        'assets': {
            'list': '//image/json/',
            # TODO this is wrong but it's not clear what the correct option is
            # //image/annot/uuid/json/?image_uuid_list=[{"__UUID__": "%s"}]'
            # works but this doesn't
            'data': '//image/dict/json/?image_uuid_list=[{"__UUID__": "%s"}]',
        }
    }
    # fmt: on

    def __init__(self, pre_initialize=False, *args, **kwargs):
        super(ACMManager, self).__init__(False, pre_initialize, *args, **kwargs)


class ACMSyncMixin(object):
    """
    Base class for syncing data from ACM, sufficiently different to EDM that it's not practical for
    this code to be generic between them
    """

    ACM_NAME = None
    ACM_ATTRIBUTE_MAPPING = None
    ACM_LOG_ATTRIBUTES = None

    def __init__(self):
        # Must be overwritten by the derived class
        assert self.ACM_NAME is not None
        assert self.ACM_ATTRIBUTE_MAPPING is not None
        assert self.ACM_LOG_ATTRIBUTES is not None

    @classmethod
    def acm_sync_item(cls, guid):
        model_obj = cls.ensure_acm_obj(guid)

        try:
            model_obj.sync_item()
        except sqlalchemy.exc.IntegrityError:
            log.error(f'Error updating {cls.ACM_NAME} {model_obj}')
        except AttributeError:
            log.error(f'Could not find {cls.ACM_NAME} {guid}')
        finally:
            model_obj.acm_sync_complete()

    def sync_item(self):
        response = current_app.acm.get_data_item(self.guid, '%s.data' % (self.ACM_NAME,))

        assert response.success
        data = response.result

        assert uuid.UUID(data.id) == self.guid

        self._process_data(data)

    def _process_attribute(self, data, attribute):
        attribute = attribute.strip()
        attribute = attribute.strip('.')
        attribute_list = attribute.split('.')

        num_components = len(attribute_list)

        if num_components == 0:
            raise AttributeError()

        attribute_ = attribute_list[0]
        attribute_ = attribute_.strip()
        data_ = getattr(data, attribute_)

        if num_components == 1:
            return data_

        attribute_list_ = attribute_list[1:]
        attribute_ = '.'.join(attribute_list_)

        return self._process_attribute(data_, attribute_)

    def _process_data(self, data):
        unmapped_attributes = list(
            set(sorted(data._fields)) - set(self.ACM_ATTRIBUTE_MAPPING)
        )
        if len(unmapped_attributes) > 0:
            log.warning('Unmapped attributes: %r' % (unmapped_attributes,))

        for attribute_name in self.ACM_ATTRIBUTE_MAPPING:
            try:
                attribute_value = self._process_attribute(data, attribute_name)

                mapped_attribute = self.ACM_ATTRIBUTE_MAPPING[attribute_name]
                if mapped_attribute is None:
                    log.warning(f'Ignoring mapping for ACM attribute {attribute_name}')
                    continue

                if attribute_name in self.ACM_LOG_ATTRIBUTES:
                    log.info(f'Syncing acm data for {attribute_name} = {attribute_value}')

                assert hasattr(self, mapped_attribute), 'attribute not found'
                attribute_ = getattr(self, mapped_attribute)
                if isinstance(attribute_, (types.MethodType,)):
                    attribute_(attribute_value)
                else:
                    setattr(self, attribute_name, attribute_value)

            except AttributeError:
                log.warning(f'Could not find ACM attribute {attribute_name}')
            except KeyError:
                log.warning(f'Could not find ACM attribute {attribute_name}')

        with db.session.begin():
            db.session.merge(self)


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    app.acm = ACMManager()
