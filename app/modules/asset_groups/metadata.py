# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
Asset_groups metadata
Classes for parsing and validating the received metadata in requests
--------------------------
"""
import enum
import logging
import os
import uuid

from flask import current_app
from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog
import app.modules.utils as util
from app.utils import HoustonException

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AssetGroupMetadataError(HoustonException):
    def __init__(self, logger, log_message, message=None, status_code=400):
        if message:
            super(AssetGroupMetadataError, self).__init__(
                logger,
                log_message=f'AssetGroupMetadata {log_message}',
                message=message,
                status_code=status_code,
            )
        else:
            super(AssetGroupMetadataError, self).__init__(
                logger,
                log_message=f'AssetGroupMetadata {log_message}',
                message=log_message,
                status_code=status_code,
            )


# Class used to process and validate the json data. This json may be received from the frontend or
# read from a file in the case of a restart. This class creates no DB objects, it just validates
# what is read and raises an AssetGroupMetadataError on failure
class AssetGroupMetadata(object):
    # Certain properties only become valid once sufficient processing of data has occurred
    class DataProcessed(str, enum.Enum):
        unprocessed = 0
        first_level = 1
        sightings = 2
        complete = 3

    def __init__(self, request_json):
        self.request_json = request_json
        self.request = {}
        self.files = set()
        self.owner = None
        self.owner_assignment = False
        self.anonymous_submitter = None
        self.data_processed = AssetGroupMetadata.DataProcessed.unprocessed

    @classmethod
    def _validate_field_type(cls, dictionary, field, field_type, error_str):
        assert field in dictionary.keys()
        # FE sends taxonomy guid as None if not populated so need to accept this
        if field_type == uuid.UUID and dictionary[field]:
            if not util.is_valid_uuid_string(dictionary[field]):
                raise AssetGroupMetadataError(
                    log, f'{field} is not a valid uuid string in {error_str}'
                )
        elif not isinstance(dictionary[field], field_type):

            # change the int type to what it should be
            if field_type == float and isinstance(dictionary[field], int):
                # change the int type to what it should be
                dictionary[field] = float(dictionary[field])
            elif dictionary[field]:
                # if present it must be the correct type
                raise AssetGroupMetadataError(
                    log,
                    f'{field} field had incorrect type, expected {field_type.__name__} in {error_str}',
                )
            # most fields can be None (as that is what the FE sends for ints, floats and strings)
            # but lists and dicts must be the correct type
            elif field_type == dict or field_type == list:
                raise AssetGroupMetadataError(
                    log,
                    f'{field} field had incorrect type, expected {field_type.__name__} in {error_str}',
                )

    # Helper for validating the required fields in any level dictionary
    @classmethod
    def _validate_fields(cls, dictionary, fields, error_str):
        for field, field_type, mandatory in fields:
            if mandatory:
                if field not in dictionary:
                    raise AssetGroupMetadataError(
                        log, f'{field} field missing from {error_str}'
                    )
                cls._validate_field_type(dictionary, field, field_type, error_str)
                if field_type == list:
                    # All mandatory lists must have at least one entry
                    if len(dictionary[field]) < 1:
                        raise AssetGroupMetadataError(
                            log, f'{field} in {error_str} must have at least one entry'
                        )
            elif field in dictionary:
                cls._validate_field_type(dictionary, field, field_type, error_str)

    @classmethod
    def validate_id_configs(cls, id_configs, debug):
        id_config_fields = [
            ('algorithms', list, True),
        ]
        # 'matching_set' is now optional here, but would not be validated here anyway

        num_configs = len(id_configs)
        if num_configs > 1:
            raise AssetGroupMetadataError(
                log, f'found multiple {num_configs} ID configs, only support one'
            )

        for config_id in range(num_configs):
            from app.modules.ia_config_reader import IaConfig

            id_config = id_configs[config_id]
            cls._validate_fields(id_config, id_config_fields, debug)

            ia_config_reader = IaConfig()
            for algorithm in id_config['algorithms']:
                try:
                    ia_config_reader.get(f'_identifiers.{algorithm}')
                except KeyError:
                    raise AssetGroupMetadataError(log, f'failed to find {algorithm}')

    @classmethod
    def validate_owner_email(cls, owner_email, debug):
        from app.modules.users.models import User

        if not isinstance(owner_email, str):
            raise AssetGroupMetadataError(log, f'{debug} ownerEmail must be a string')
        encounter_owner = User.find(email=owner_email)
        if encounter_owner is None:
            raise AssetGroupMetadataError(log, f'{debug} owner {owner_email} not found')

    @classmethod
    def _validate_lat_long(cls, dictionary, error_str):
        if ('decimalLatitude' in dictionary and 'decimalLongitude' not in dictionary) or (
            'decimalLatitude' not in dictionary and 'decimalLongitude' in dictionary
        ):
            raise AssetGroupMetadataError(
                log,
                f'Need both or neither of decimalLatitude and decimalLongitude in {error_str}',
            )

        # Both may be null but if only one is, it's a failure
        if not dictionary['decimalLatitude'] and not dictionary['decimalLongitude']:
            return
        if not dictionary['decimalLatitude'] or not dictionary['decimalLongitude']:
            raise AssetGroupMetadataError(
                log,
                f'Need both or neither of decimalLatitude and decimalLongitude in {error_str}',
            )

        # Strings are permitted on creation but must convert to valid floats
        if isinstance(dictionary['decimalLatitude'], str):
            try:
                dictionary['decimalLatitude'] = float(dictionary['decimalLatitude'])
            except ValueError:
                raise AssetGroupMetadataError(
                    log, f'decimalLatitude needs to be a float in {error_str}'
                )
        if isinstance(dictionary['decimalLongitude'], str):
            try:
                dictionary['decimalLongitude'] = float(dictionary['decimalLongitude'])
            except ValueError:
                raise AssetGroupMetadataError(
                    log, f'decimalLongitude needs to be a float in {error_str}'
                )
        lat_val = dictionary['decimalLatitude']
        long_val = dictionary['decimalLongitude']

        # Check it worked
        if not isinstance(lat_val, float):
            raise AssetGroupMetadataError(
                log, f'decimalLatitude needs to be a float in {error_str}'
            )
        if not isinstance(long_val, float):
            raise AssetGroupMetadataError(
                log, f'decimalLongitude needs to be a float in {error_str}'
            )

        # Validate range
        if not util.is_valid_latitude(lat_val):
            raise AssetGroupMetadataError(
                log, f'decimalLatitude {lat_val} out of range in {error_str}'
            )

        if not util.is_valid_longitude(long_val):
            raise AssetGroupMetadataError(
                log, f'decimalLongitude {long_val} out of range in {error_str}'
            )

    @classmethod
    def validate_individual(cls, individual_uuid, debug):
        from app.modules.individuals.models import Individual

        try:
            individual = Individual.query.get(individual_uuid)
        except Exception:
            raise AssetGroupMetadataError(
                log, f'{debug} individual {individual_uuid} not valid'
            )

        if individual is None:
            raise AssetGroupMetadataError(
                log, f'{debug} individual {individual_uuid} not found'
            )

    @classmethod
    def validate_annotations(cls, asset_group_sighting, annotations, debug):
        from app.modules.annotations.models import Annotation
        from app.modules.asset_groups.models import AssetGroupSightingStage

        if not asset_group_sighting.stage == AssetGroupSightingStage.curation:
            raise AssetGroupMetadataError(
                log, f'{debug} annotations:{str(annotations)} not in curating group'
            )

        for annot_uuid in annotations:
            annot = Annotation.query.get(annot_uuid)
            if not annot:
                raise AssetGroupMetadataError(
                    log, f'{debug} annotation:{str(annot_uuid)} not found'
                )
            ags_s = annot.asset.get_asset_group_sightings()
            # There should be only one
            if len(ags_s) != 1:
                message = f'Asset {annot.asset.guid} has {len(ags_s)} AGS'
                AuditLog.audit_log_object_warning(log, annot.asset, message)
                log.warning(message)
            # and it should be this one
            if asset_group_sighting not in ags_s:
                raise AssetGroupMetadataError(
                    log, f'{debug} Asset cannot be in multiple sightings'
                )

    @classmethod
    def validate_encounters(cls, encounters, debug):
        encounter_num = 0
        owner_assignment = False

        # Have a sighting with multiple encounters, make sure we have all of the files
        for encounter in encounters:
            encounter_num += 1
            if not isinstance(encounter, dict):
                raise AssetGroupMetadataError(
                    log, f'{debug}{encounter_num} needs to be a dict'
                )
            encounter_fields = [
                ('locationId', uuid.UUID, False),
                ('taxonomy', uuid.UUID, False),
                ('decimalLatitude', float, False),
                ('decimalLongitude', float, False),
                ('verbatimLocality', str, False),
                ('customFields', dict, False),
                ('ownerEmail', str, False),
                ('sex', str, False),
                ('annotations', list, False),
                ('individualUuid', str, False),
            ]
            cls._validate_fields(
                encounter,
                encounter_fields,
                f'{debug}{encounter_num}',
            )

            # individual must be valid
            if 'individualUuid' in encounter:
                cls.validate_individual(
                    encounter['individualUuid'], f'{debug}{encounter_num}'
                )
            # Can reassign encounter owner but only to a valid user
            if 'ownerEmail' in encounter:
                cls.validate_owner_email(
                    encounter['ownerEmail'], f'{debug}{encounter_num}'
                )
                owner_assignment = True

            if 'decimalLatitude' in encounter or 'decimalLongitude' in encounter:
                cls._validate_lat_long(encounter, f'{debug}{encounter_num}')

        return owner_assignment

    def _validate_sighting(self, sighting, file_dir, sighting_debug, encounter_debug):

        sighting_fields = [
            ('locationId', uuid.UUID, True),
            ('decimalLatitude', float, False),
            ('decimalLongitude', float, False),
            ('verbatimLocality', str, False),
            ('time', str, True),
            ('timeSpecificity', str, True),
            ('encounters', list, True),
            ('name', str, False),
            ('assetReferences', list, False),
            ('idConfigs', list, False),
            ('customFields', dict, False),
        ]
        self._validate_fields(sighting, sighting_fields, sighting_debug)
        from app.utils import get_stored_filename

        if 'assetReferences' in sighting:
            for filename in sighting['assetReferences']:
                if not isinstance(filename, str):
                    raise AssetGroupMetadataError(
                        log, f'Invalid assetReference data {filename}'
                    )
                stored_filename = get_stored_filename(filename)
                file_path = os.path.join(file_dir, stored_filename)
                file_size = 0
                try:
                    file_size = os.path.getsize(file_path)  # 2for1
                except OSError as err:
                    raise AssetGroupMetadataError(
                        log, f'Failed to find {filename} in transaction {err} '
                    )
                if file_size < 1:
                    raise AssetGroupMetadataError(f'found zero-size file for {filename}')
                if filename in self.files:
                    raise AssetGroupMetadataError(
                        log, f'found {filename} in multiple sightings'
                    )

                # Set ensures no duplicates
                self.files.add(filename)

        if 'idConfigs' in sighting:
            self.validate_id_configs(sighting['idConfigs'], sighting_debug)

        if 'decimalLatitude' in sighting or 'decimalLongitude' in sighting:
            self._validate_lat_long(sighting, sighting_debug)

        self.owner_assignment = self.validate_encounters(
            sighting['encounters'], f'{encounter_debug}'
        )
        from app.modules.sightings.models import Sighting

        unsupported_fields = Sighting.get_unsupported_fields(sighting.keys())
        # These are not valid on a Sighting but are perfectly correct on an AGS
        if 'assetReferences' in unsupported_fields:
            unsupported_fields.remove('assetReferences')
        if 'idConfigs' in unsupported_fields:
            unsupported_fields.remove('idConfigs')
        if 'speciesDetectionModel' in unsupported_fields:
            unsupported_fields.remove('speciesDetectionModel')

        if unsupported_fields:
            raise AssetGroupMetadataError(
                log, f'{unsupported_fields} are not valid field name(s)'
            )

    @property
    def bulk_upload(self):
        assert self.data_processed >= AssetGroupMetadata.DataProcessed.first_level
        return 'uploadType' in self.request and self.request['uploadType'] == 'bulk'

    @property
    def location_id(self):
        assert self.data_processed >= AssetGroupMetadata.DataProcessed.first_level
        return self.request['locationId']

    @property
    def tus_transaction_id(self):
        assert self.data_processed >= AssetGroupMetadata.DataProcessed.first_level
        return self.request.get('transactionId', None)

    @property
    def detection_configs(self):
        assert self.data_processed >= AssetGroupMetadata.DataProcessed.first_level
        return self.request['speciesDetectionModel']

    @property
    def num_sightings(self):
        return len(self.get_sightings())

    def get_sightings(self):
        assert self.data_processed >= AssetGroupMetadata.DataProcessed.first_level
        return self.request['sightings']

    @property
    def submitter_email(self):
        assert self.data_processed >= AssetGroupMetadata.DataProcessed.first_level
        return (
            self.request['submitterEmail'] if 'submitterEmail' in self.request else None
        )

    @property
    def description(self):
        assert self.data_processed >= AssetGroupMetadata.DataProcessed.first_level
        return self.request['description'] if 'description' in self.request else ''

    @property
    def anonymous(self):
        assert self.data_processed >= AssetGroupMetadata.DataProcessed.first_level
        from app.modules.users.models import User

        return self.owner is User.get_public_user()

    def process_request(self):
        try:
            self.request.update(self.request_json)
        except Exception:
            raise AssetGroupMetadataError('Failed to parse request')

        # Parse according to docs.google.com/document/d/11TMq1qzaQxva97M3XYwaEYYUawJ5VsrRXnJvTQR_nG0/edit?pli=1#
        top_level_fields = [
            ('uploadType', str, True),
            ('speciesDetectionModel', list, True),
            ('transactionId', str, False),
            ('sightings', list, True),
            ('submitterEmail', str, False),
            ('description', str, False),
        ]
        self._validate_fields(self.request, top_level_fields, 'request')

        self.data_processed = AssetGroupMetadata.DataProcessed.first_level
        if len(self.detection_configs) > 1:
            raise AssetGroupMetadataError(
                'only support a single detection config for now'
            )
        else:
            from app.modules.ia_config_reader import IaConfig

            ia_config_reader = IaConfig()
            detectors = ia_config_reader.get('_detectors')

            for config in self.detection_configs:
                if config and config != 'None' and config not in detectors.keys():
                    raise AssetGroupMetadataError(
                        log, f'detection config {config} not supported'
                    )

            pass

        # validate num sightings
        if not self.bulk_upload and self.num_sightings != 1:
            raise AssetGroupMetadataError(
                log,
                'Incorrect num sightings in form submission, there must be exactly one',
            )

        # Ensure that the sighting (and encounters within them) received are valid
        self._validate_sightings()
        self.data_processed = AssetGroupMetadata.DataProcessed.sightings

        if not self.bulk_upload and len(self.request['sightings'][0]['encounters']) != 1:
            raise AssetGroupMetadataError(
                log,
                'Incorrect num encounters in form submission, there must be exactly one',
            )

        from app.modules.users.models import User

        if current_user and not current_user.is_anonymous:
            self.owner = current_user
        else:
            self.owner = User.get_public_user()

        # individual fields in the message are all valid, now check that it's valid in total
        self._validate_contents()
        self.data_processed = AssetGroupMetadata.DataProcessed.complete

    def _validate_contents(self):
        # Message was valid, is the user allowed to do so
        from app.modules.users.models import User

        if 'uploadType' not in self.request:
            raise AssetGroupMetadataError(
                log, "Use uploadType to define type 'bulk' or 'form'"
            )

        if self.anonymous:
            if self.bulk_upload:
                raise AssetGroupMetadataError(
                    log, 'anonymous users not permitted to do bulk upload'
                )
            if self.owner_assignment:
                raise AssetGroupMetadataError(
                    log, 'anonymous users not permitted to assign owners'
                )

            log.info(
                f'Anonymous asset_group posted, submitter_email={self.submitter_email}'
            )

            # if not provided, submitter_guid is allowed to be null
            if self.submitter_email is not None:
                self.anonymous_submitter = User.find(email=self.submitter_email)

                if (
                    self.anonymous_submitter is not None
                    and self.anonymous_submitter.is_active
                ):
                    # Active users must log in, no spoofing
                    raise AssetGroupMetadataError(
                        log,
                        f'Anonymous submitter using active user email {self.submitter_email}; rejecting',
                        'Invalid submitter data',
                        403,
                    )
        elif not current_user.is_researcher:
            if self.bulk_upload:
                raise AssetGroupMetadataError(log, 'User not permitted to do bulk upload')
            if self.owner_assignment:
                raise AssetGroupMetadataError(log, 'User not permitted to assign owners')
        elif self.bulk_upload:
            for group in current_user.get_asset_groups():
                if group.bulk_upload and not group.is_processed():
                    # Only one unprocessed bulk upload allowed at a time
                    raise AssetGroupMetadataError(
                        log,
                        f'Bulk Upload {group.guid} not processed, please finish this before creating new bulk upload',
                    )

    def _validate_sightings(self):
        from app.extensions.tus import tus_upload_dir

        file_dir = tus_upload_dir(current_app, transaction_id=self.tus_transaction_id)

        asset_refs = []
        sighting_num = 0
        # validate sightings content
        for sighting in self.request['sightings']:
            # name is optional so don't check it
            sighting_num += 1
            if not isinstance(sighting, dict):
                raise AssetGroupMetadataError(
                    log, f'Sighting {sighting_num} needs to be a dict'
                )

            # all files referenced must exist in the tus dir
            self._validate_sighting(
                sighting,
                file_dir,
                f'Sighting {sighting_num}',
                f'Encounter {sighting_num}.',
            )
            sighting_asset_refs = sighting.get('asset_references', [])
            for ref in sighting_asset_refs:
                if ref in asset_refs:
                    raise AssetGroupMetadataError(
                        log, f'{ref} can be in at most one Sighting'
                    )
            asset_refs.extend(sighting_asset_refs)
