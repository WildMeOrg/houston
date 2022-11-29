# -*- coding: utf-8 -*-
"""
Data transfer from EDM to houston Invoke.
"""
import logging
import types

import sqlalchemy
import tqdm
from flask import current_app as app

import app.extensions.logging as AuditLog
from app.extensions import db
from flask_restx_patched import is_extension_enabled
from tasks.utils import app_context_task

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


# Helper base class for syncing data from EDM
class EDMDataSync(object):
    @classmethod
    def edm_sync_all(cls, verbose=True, refresh=False):
        edm_items = app.edm.get_list('{}.list'.format(cls.EDM_NAME))

        if verbose:
            log.info(
                'Checking %d EDM %ss against local cache...'
                % (len(edm_items), cls.EDM_NAME)
            )

        new_items = []
        stale_items = []
        for guid in tqdm.tqdm(edm_items):
            item_version = edm_items[guid]
            version = item_version.get('version', None)
            assert version is not None

            model_obj, is_new = cls.ensure_edm_obj(guid)
            if is_new:
                new_items.append(model_obj)

            if model_obj.version != version or refresh:
                stale_items.append((model_obj, version))

        if verbose:
            log.info(f'Added {len(new_items)} new {cls.EDM_NAME}s')
            log.info(f'Updating {len(stale_items)} stale {cls.EDM_NAME}s using EDM...')

        updated_items = []
        failed_items = []
        for model_obj, version in tqdm.tqdm(stale_items):
            try:
                model_obj._sync_item(model_obj.guid, version)
                updated_items.append(model_obj)
            except sqlalchemy.exc.IntegrityError:
                log.exception(f'Error updating {cls.EDM_NAME} {model_obj}')

                failed_items.append(model_obj)

        return edm_items, new_items, updated_items, failed_items

    def _process_edm_attribute(self, data, edm_attribute):
        edm_attribute = edm_attribute.strip()
        edm_attribute = edm_attribute.strip('.')
        edm_attribute_list = edm_attribute.split('.')

        num_components = len(edm_attribute_list)

        if num_components == 0:
            raise AttributeError()

        edm_attribute_ = edm_attribute_list[0]
        edm_attribute_ = edm_attribute_.strip()
        data_ = getattr(data, edm_attribute_)

        if num_components == 1:
            return data_

        edm_attribute_list_ = edm_attribute_list[1:]
        edm_attribute_ = '.'.join(edm_attribute_list_)

        return self._process_edm_attribute(data_, edm_attribute_)

    def _process_edm_data(self, data, claimed_version):

        unmapped_attributes = list(
            set(sorted(data._fields)) - set(self.EDM_ATTRIBUTE_MAPPING)
        )
        if len(unmapped_attributes) > 0:
            log.warning('Unmapped attributes: {!r}'.format(unmapped_attributes))

        found_version = None
        for edm_attribute in self.EDM_ATTRIBUTE_MAPPING:
            try:
                edm_value = self._process_edm_attribute(data, edm_attribute)

                attribute = self.EDM_ATTRIBUTE_MAPPING[edm_attribute]
                if attribute is None:
                    log.warning(
                        'Ignoring mapping for EDM attribute {!r}'.format(edm_attribute)
                    )
                    continue

                if edm_attribute in self.EDM_LOG_ATTRIBUTES:
                    log.info(
                        'Syncing edm data for %r = %r'
                        % (
                            edm_attribute,
                            edm_value,
                        )
                    )

                assert hasattr(self, attribute), 'attribute not found'
                attribute_ = getattr(self, attribute)
                if isinstance(attribute_, (types.MethodType,)):
                    attribute_(edm_value)
                else:
                    setattr(self, attribute, edm_value)
                    if edm_attribute == self.EDM_VERSION_ATTRIBUTE:
                        found_version = edm_value
            except AttributeError:
                AuditLog.backend_fault(
                    log, f'Could not find EDM attribute {edm_attribute}'
                )

            except KeyError:
                AuditLog.backend_fault(
                    log, f'Could not find EDM attribute {edm_attribute}'
                )

        if found_version is None:
            self.version = claimed_version
        else:
            self.version = found_version

        with db.session.begin():
            db.session.merge(self)

        if found_version is None:
            log.info('Updating to claimed version {!r}'.format(claimed_version))
        else:
            log.info('Updating to found version {!r}'.format(found_version))

    def _sync_item(self, guid, version):
        response = app.edm.get_data_item(guid, '{}.data'.format(self.EDM_NAME))
        import uuid

        assert response.success
        data = response.result

        assert uuid.UUID(data.id) == guid

        self._process_edm_data(data, version)


class UserDataSync(EDMDataSync):

    # fmt: off
    # Name of the module, used for knowing what to sync i.e user.list, user.data
    EDM_NAME = 'user'

    # The EDM attribute for the version, if reported
    EDM_VERSION_ATTRIBUTE = 'version'

    #
    EDM_LOG_ATTRIBUTES = [
        'emailAddress',
    ]

    EDM_ATTRIBUTE_MAPPING = {
        # Ignored
        'id'                    : None,
        'lastLogin'             : None,
        'username'              : None,

        # Attributes
        'acceptedUserAgreement' : 'accepted_user_agreement',
        'affiliation'           : 'affiliation',
        'emailAddress'          : 'email',
        'fullName'              : 'full_name',
        'receiveEmails'         : 'receive_notification_emails',
        'sharing'               : 'shares_data',
        'userURL'               : 'website',
        'version'               : 'version',

        # Functions
        'organizations'         : '_process_edm_user_organization',
        'profileImageUrl'       : '_process_edm_user_profile_url',
        'roles'                 : '_process_edm_user_roles',
    }
    # fmt: on

    @classmethod
    def ensure_edm_obj(cls, guid):
        from app.modules.users.models import User

        user = User.query.filter(User.guid == guid).first()
        is_new = user is None

        if is_new:
            email = '{}@localhost'.format(guid)
            password = User.initial_random_password()
            user = User(
                guid=guid,
                email=email,
                password=password,
                version=None,
                is_active=True,
                in_alpha=False,
                # contributor assumed true for all migrated edm; rest are set based on roles later
                is_contributor=True,
                is_researcher=False,
                is_user_manager=False,
            )
            with db.session.begin():
                db.session.add(user)
            db.session.refresh(user)

        return user, is_new

    def _process_edm_user_roles(self, roles):
        if not roles or not isinstance(roles, list):
            return
        if 'researcher' in roles:
            log.info('researcher role found, setting is_researcher')
            self.is_researcher = True
        if 'manager' in roles:
            log.info('manager role found, setting is_user_manager, is_admin')
            self.is_user_manager = True
            self.is_admin = True
        if 'admin' in roles:
            log.info('admin role found, setting is_user_manager, is_admin')
            self.is_user_manager = True
            self.is_admin = True

    def _process_edm_user_organization(self, orgs):
        pass

    def _process_edm_user_profile_url(self, profile):
        pass


class OrganizationEDMSync(EDMDataSync):
    # All comms with EDM to exchange timestamps will use this format so it should be in one place
    EDM_DATETIME_FMTSTR = '%Y-%m-%dT%H:%M:%S.%fZ'

    # fmt: off
    # Name of the module, used for knowing what to sync i.e organization.list, organization.data
    EDM_NAME = 'organization'

    # The EDM attribute for the version, if reported
    EDM_VERSION_ATTRIBUTE = 'version'

    EDM_LOG_ATTRIBUTES = [
        'name',
    ]

    EDM_ATTRIBUTE_MAPPING = {
        # Ignored
        'id'                    : None,
        'created'               : None,
        'modified'              : None,

        # # Attributes
        'name'                  : 'title',
        'url'                   : 'website',
        'version'               : 'version',

        # # Functions
        'members'               : '_process_members',
        'logo'                  : '_process_logo',
        'createdDate'           : '_process_created_date',
        'modifiedDate'          : '_process_modified_date',
    }
    # fmt: on

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.organizations.schemas import DetailedOrganizationSchema

        return DetailedOrganizationSchema

    def _process_members(self, members):
        from app.modules.organizations.models import OrganizationUserMembershipEnrollment
        from app.modules.users.models import User

        for member in members:
            log.info('Adding Member ID {}'.format(member.id))
            user, is_new = User.ensure_edm_obj(member.id)
            if user not in self.members:
                enrollment = OrganizationUserMembershipEnrollment(
                    organization=self,
                    user=user,
                )

                with db.session.begin():
                    self.user_membership_enrollments.append(enrollment)

    def _process_logo(self, logo):
        self.logo_guid = logo.uuid
        self.logo_url = logo.url

    def _process_created_date(self, date):
        pass

    def _process_modified_date(self, date):
        pass


def transfer_data_setting():
    from app.modules.site_settings.models import Regions, SiteSetting

    response = app.edm.get_dict('configuration.data', '__bundle_setup')
    assert isinstance(response, dict)
    assert response.get('success', False)
    edm_conf = response['response']['configuration']
    # order matters here, so lets adjust
    conf_keys = list(edm_conf.keys())
    cfcat = 'site.custom.customFieldCategories'
    if cfcat in conf_keys:  # must be before CFD
        conf_keys.remove(cfcat)
        conf_keys.insert(0, cfcat)
    for conf_key in conf_keys:
        new_key = conf_key
        if conf_key == 'site.custom.customFields.Occurrence':
            new_key = 'site.custom.customFields.Sighting'
        if conf_key == 'site.custom.customFields.MarkedIndividual':
            new_key = 'site.custom.customFields.Individual'
        if not SiteSetting.is_valid_setting(new_key):
            print(f'{new_key} unknown houston_setting; skipping')
            continue
        value = edm_conf[conf_key].get('value')
        if conf_key == 'site.custom.regions':
            Regions.guidify(value)  # adds a real uuid for ids, if not already
        SiteSetting.set_key_value(new_key, value)


def transfer_data_encounter():
    import app.modules.utils as util
    from app.modules.encounters.models import Encounter
    from app.modules.site_settings.models import Regions, Taxonomy

    reg = Regions()
    encs = Encounter.query.all()
    print('encounter edm data transfer started')
    for enc in tqdm.tqdm(encs):
        response = app.edm.get_dict('encounter.data_complete', enc.guid)
        if not isinstance(response, dict):
            log.warning(f'encounter {enc.guid} missing from EDM: response=({response})')
            continue
        assert response.get('success', False)
        edm_data = response['result']
        dlat = edm_data.get('decimalLatitude')
        if dlat:
            dlat = float(dlat)
            if not util.is_valid_latitude(dlat):
                raise ValueError(f'invalid decimalLatitude {dlat} on enc {enc.guid}')
        enc.decimal_latitude = dlat
        dlon = edm_data.get('decimalLongitude')
        if dlon:
            dlon = float(dlon)
            if not util.is_valid_longitude(dlon):
                raise ValueError(f'invalid decimalLongitude {dlon} on enc {enc.guid}')
        enc.decimal_longitude = dlon
        sex = edm_data.get('sex')
        if sex and not util.is_valid_sex(sex):
            raise ValueError(f'invalid sex "{sex}" on enc {enc.guid}')
        enc.sex = sex
        enc.verbatim_locality = edm_data.get('verbatimLocality')

        loc = edm_data.get('locationId')
        if loc:
            found = reg.transfer_find(loc)
            if found and found.get('id'):
                enc.location_guid = found['id']
            else:  # TODO handle better?
                raise ValueError(f'unknown locationId "{loc}" on enc {enc.guid}')

        tx_id = edm_data.get('taxonomy')
        if tx_id:
            Taxonomy(tx_id)  # will raise ValueError if bad id
            enc.taxonomy_guid = tx_id

        edm_custom_fields = edm_data.get('customFields', {})
        try:
            enc.set_custom_field_values(edm_custom_fields)
        except ValueError as ve:
            if str(ve).startswith('Value "" is not valid for'):
                log.info(f'attempting to repair: {edm_custom_fields}')
                for key in edm_custom_fields:
                    if edm_custom_fields[key] == '':
                        edm_custom_fields[key] = None
                log.info(f'repaired candidate: {edm_custom_fields}')
                enc.set_custom_field_values(edm_custom_fields)
            else:
                log.error(f'unrepairable fail on {edm_custom_fields} for {enc}')
                raise ve
    db.session.flush()
    print('encounter edm data transfer complete')


def transfer_data_sighting():
    import app.modules.utils as util
    from app.modules.sightings.models import Sighting
    from app.modules.site_settings.models import Regions, Taxonomy

    reg = Regions()
    sightings = Sighting.query.all()
    print('sighting edm data transfer started')
    for sighting in tqdm.tqdm(sightings):
        response = app.edm.get_dict('sighting.data_complete', sighting.guid)
        if not isinstance(response, dict):
            log.warning(
                f'sighting {sighting.guid} missing from EDM: response=({response})'
            )
            continue
        assert response.get('success', False)
        edm_data = response['result']
        dlat = edm_data.get('decimalLatitude')
        if dlat:
            dlat = float(dlat)
            if not util.is_valid_latitude(dlat):
                raise ValueError(
                    f'invalid decimalLatitude {dlat} on sighting {sighting.guid}'
                )
        sighting.decimal_latitude = dlat
        dlon = edm_data.get('decimalLongitude')
        if dlon:
            dlon = float(dlon)
            if not util.is_valid_longitude(dlon):
                raise ValueError(
                    f'invalid decimalLongitude {dlon} on sighting {sighting.guid}'
                )
        sighting.decimal_longitude = dlon
        sighting.verbatim_locality = edm_data.get('verbatimLocality')
        sighting.comments = edm_data.get('comments')

        loc = edm_data.get('locationId')
        if loc:
            found = reg.transfer_find(loc)
            if found and found.get('id'):
                sighting.location_guid = found['id']
            else:  # TODO handle better?
                raise ValueError(
                    f'unknown locationId "{loc}" on sighting {sighting.guid}'
                )

        txs = edm_data.get('taxonomies', [])
        taxonomies = []
        for tx_id in txs:
            # will raise ValueError if bad id
            taxonomies.append(Taxonomy(tx_id))
        if taxonomies:
            sighting.set_taxonomies(taxonomies)

        edm_custom_fields = edm_data.get('customFields', {})
        try:
            sighting.set_custom_field_values(edm_custom_fields)
        except ValueError as ve:
            if str(ve).startswith('Value "" is not valid for'):
                log.info(f'attempting to repair: {edm_custom_fields}')
                for key in edm_custom_fields:
                    if edm_custom_fields[key] == '':
                        edm_custom_fields[key] = None
                log.info(f'repaired candidate: {edm_custom_fields}')
                sighting.set_custom_field_values(edm_custom_fields)
            else:
                log.error(f'unrepairable fail on {edm_custom_fields} for {sighting}')
                raise ve
    db.session.flush()
    print('sighting edm data transfer complete')


def transfer_data_individual():
    import datetime

    import app.modules.utils as util
    from app.modules.individuals.models import Individual
    from app.modules.site_settings.models import Taxonomy

    indivs = Individual.query.all()
    print('individual edm data transfer started')
    for indiv in tqdm.tqdm(indivs):
        response = app.edm.get_dict('individual.data_complete', indiv.guid)
        if not isinstance(response, dict):
            log.warning(
                f'individual {indiv.guid} missing from EDM: response=({response})'
            )
            continue
        assert response.get('success', False)
        edm_data = response['result']
        sex = edm_data.get('sex')
        if sex and not util.is_valid_sex(sex):
            raise ValueError(f'invalid sex "{sex}" on individual {indiv.guid}')
        indiv.sex = sex
        indiv.comments = edm_data.get(
            'comments'
        )  # TODO are comments staying here or customField via migration? FIXME

        tx_id = edm_data.get('taxonomy')
        if tx_id:
            Taxonomy(tx_id)  # will raise ValueError if bad id
            indiv.taxonomy_guid = tx_id

        tob = edm_data.get('timeOfBirth')
        if tob and tob != '0':
            try:
                # i am not sure if the value is in ms or sec?  FIXME
                indiv.time_of_birth = datetime.datetime.fromtimestamp(float(tob) / 1000.0)
            except Exception:
                log.warning(f'could not get datetime from "{tob}"')
        tod = edm_data.get('timeOfDeath')
        if tod and tod != '0':
            try:
                indiv.time_of_death = datetime.datetime.fromtimestamp(float(tod) / 1000.0)
            except Exception:
                log.warning(f'could not get datetime from "{tod}"')

        edm_custom_fields = edm_data.get('customFields', {})
        indiv.set_custom_field_values(edm_custom_fields)
    db.session.flush()
    print('individual edm data transfer complete')


@app_context_task(
    help={
        'section': 'setting, user, individual, encounter, sighting (note: setting MUST be run before any others will work)',
    }
)
def transfer_data(context, section=None, refresh=True):
    """
    Transfer data
    """
    if not is_extension_enabled('edm'):
        raise RuntimeError('EDM must be enabled')

    valid_sections = ['user', 'setting', 'individual', 'encounter', 'sighting']
    if section:
        if section not in valid_sections:
            raise ValueError(
                'invalid section; must be one of: '
                + ', '.join(valid_sections)
                + ' (or omitted for all, minus users)'
            )
        sections = [
            section,
        ]
    else:
        sections = valid_sections
        sections.pop(0)  # we dont want user as part of all

    for sect in sections:
        if sect == 'setting':
            transfer_data_setting()
        elif sect == 'individual':
            transfer_data_individual()
        elif sect == 'encounter':
            transfer_data_encounter()
        elif sect == 'sighting':
            transfer_data_sighting()
        elif sect == 'user':
            UserDataSync.edm_sync_all(refresh=refresh)
        # TODO Organisations at some point


@app_context_task()
def fix_pending_sightings(context):
    """
    Fix config on AssetGroupSightings which are not processed
    """
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )
    from app.modules.site_settings.models import Regions

    reg = Regions()

    agss = (
        db.session.query(AssetGroupSighting)
        .filter(AssetGroupSighting.stage != AssetGroupSightingStage.processed)
        .all()
    )
    for ags in agss:
        loc = ags.config['sighting'].get('locationId')
        print(f'{ags.guid}: {loc}')
        if loc:
            found = reg.transfer_find(loc)
            if found and found.get('id'):
                ags.config['sighting']['locationId'] = found['id']
            else:
                raise ValueError(
                    f'unknown locationId "{loc}" on sighting ags.config.sighting'
                )
        cfv = ags.config['sighting'].get('customFields')
        if cfv:
            for cf_id in cfv:
                if cfv[cf_id] == '':
                    cfv[cf_id] = None
            ags.config['sighting']['customFields'] = cfv

        encs = ags.config['sighting'].get('encounters', [])
        for i in range(len(encs)):
            eloc = encs[i].get('locationId')
            print(f"+ enc {encs[i].get('guid')}: {eloc}")
            if eloc:
                found = reg.transfer_find(eloc)
                if found and found.get('id'):
                    ags.config['sighting']['encounters'][i]['locationId'] = found['id']
                else:
                    raise ValueError(f'unknown locationId "{loc}" on enc {encs[i]}')
            ecfv = encs[i].get('customFields')
            if ecfv:
                for cf_id in ecfv:
                    if ecfv[cf_id] == '':
                        ecfv[cf_id] = None
                ags.config['sighting']['encounters'][i]['customFields'] = ecfv
        ags.config = ags.config
    db.session.flush()


# note: will overwrite existing value currently
@app_context_task(
    help={
        'cfguid': 'GUID of the customField',
        'filename': 'filename to read data from (tab-delimited: model_guid, value)',
    }
)
def custom_field_import(context, cfclass, cfguid, filename):
    """
    Import customField values from a file
    """
    from app.modules.encounters.models import Encounter
    from app.modules.individuals.models import Individual
    from app.modules.sightings.models import Sighting
    from app.modules.site_settings.helpers import SiteSettingCustomFields

    defn = SiteSettingCustomFields.get_definition(cfclass, cfguid)
    if not defn:
        raise ValueError(f'{cfclass}/{cfguid} invalid')

    cls = None
    if cfclass == 'Encounter':
        cls = Encounter
    elif cfclass == 'Sighting':
        cls = Sighting
    elif cfclass == 'Individual':
        cls = Individual
    if not cls:
        raise ValueError('invalid class')  # snh

    with open(filename) as f:
        contents = f.readlines()
    ct = 1
    for line in contents:
        val = line.strip().split('\t')
        obj = cls.query.get(val[0])
        if not obj:
            print(f'>>> could not find guid={val[0]}')
            continue
        obj.set_custom_field_value(cfguid, val[1])
        print(
            f'[{ct}/{len(contents)}] Set cfguid={cfguid} on {cfclass}={val[0]}: {val[1]}'
        )
        ct += 1
