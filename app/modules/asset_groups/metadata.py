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

from flask import current_app
from flask_login import current_user  # NOQA
from app.utils import HoustonException

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AssetGroupMetadataError(HoustonException):
    def __init__(self, log_message, message=None, status_code=400):
        if message:
            super(AssetGroupMetadataError, self).__init__(
                log_message=f'AssetGroupMetadata {log_message}',
                message=message,
                status_code=status_code,
            )
        else:
            super(AssetGroupMetadataError, self).__init__(
                log_message=f'AssetGroupMetadata {log_message}',
                message=log_message,
                status_code=status_code,
            )
        log.warning(f'Failed: {log_message} {self.status_code}')


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

    # Helper for validating the required fields in any level dictionary
    @classmethod
    def _validate_fields(cls, dictionary, fields, error_str):
        for field, field_type, mandatory in fields:
            if mandatory:
                if field not in dictionary or not isinstance(
                    dictionary[field], field_type
                ):
                    raise AssetGroupMetadataError(
                        f'{field} field missing from {error_str}'
                    )
                elif (
                    field_type == list
                ):  # All mandatory lists must have at least one entry
                    if len(dictionary[field]) < 1:
                        raise AssetGroupMetadataError(
                            f'{field} in {error_str} must have at least one entry'
                        )

            elif field in dictionary:
                if not isinstance(dictionary[field], field_type):
                    raise AssetGroupMetadataError(
                        f'{field} incorrect type in {error_str}'
                    )

    @classmethod
    def validate_id_configs(cls, id_configs, debug):
        id_config_fields = [
            ('algorithms', list, True),
            ('matchingSetDataOwners', str, True),
            ('matchingSetRegions', list, False),
        ]

        num_configs = len(id_configs)
        if num_configs > 1:
            raise AssetGroupMetadataError(
                f'found multiple {num_configs} ID configs, only support one'
            )

        for config_id in range(num_configs):
            id_config = id_configs[config_id]
            cls._validate_fields(id_config, id_config_fields, debug)
            owners = id_config['matchingSetDataOwners']
            from app.modules.sightings.models import Sighting

            supported_owners = Sighting.get_matching_set_options()
            if owners not in supported_owners:
                raise AssetGroupMetadataError(
                    f'dataOwners {owners} not supported, only support {supported_owners}'
                )

    @classmethod
    def validate_owner_email(cls, owner_email, debug):
        from app.modules.users.models import User

        if not isinstance(owner_email, str):
            raise AssetGroupMetadataError(f'{debug} ownerEmail must be a string')
        encounter_owner = User.find(email=owner_email)
        if encounter_owner is None:
            raise AssetGroupMetadataError(f'{debug} owner {owner_email} not found')

    @classmethod
    def validate_individual(cls, individual_uuid, debug):
        from app.modules.individuals.models import Individual

        try:
            individual = Individual.query.get(individual_uuid)
        except Exception:
            raise AssetGroupMetadataError(
                f'{debug} individual {individual_uuid} not valid'
            )

        if individual is None:
            raise AssetGroupMetadataError(
                f'{debug} individual {individual_uuid} not found'
            )

    @classmethod
    def validate_annotations(cls, annotations, debug):
        from app.modules.annotations.models import Annotation
        from app.modules.asset_groups.models import AssetGroupSightingStage

        for annot_uuid in annotations:
            annot = Annotation.query.get(annot_uuid)
            if not annot:
                raise AssetGroupMetadataError(
                    f'{debug} annotation:{str(annot_uuid)} not found'
                )

            if not annot.asset.asset_group.is_partially_in_stage(
                AssetGroupSightingStage.curation
            ):
                raise AssetGroupMetadataError(
                    f'{debug} annotation:{str(annot_uuid)} not in curating group'
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
                    f'{debug}{encounter_num} needs to be a dict'
                )
            encounter_fields = [
                ('ownerEmail', str, False),
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

            # can assign annotations (in patch only) but they must be valid
            if 'annotations' in encounter:
                cls.validate_annotations(encounter['annotations'])
                from app.modules.annotations.models import Annotation
                from app.modules.asset_groups.models import AssetGroupSightingStage

                for annot_uuid in encounter['annotations']:
                    annot = Annotation.query.get(annot_uuid)
                    if not annot:
                        raise AssetGroupMetadataError(
                            f'{debug}{encounter_num} annotation:{str(annot_uuid)} not found'
                        )

                    if not annot.asset.asset_group.is_partially_in_stage(
                        AssetGroupSightingStage.curation
                    ):
                        raise AssetGroupMetadataError(
                            f'{debug}{encounter_num} annotation:{str(annot_uuid)} not in curating group'
                        )
        return owner_assignment

    def _validate_sighting(self, sighting, file_dir, sighting_debug, encounter_debug):

        sighting_fields = [
            ('locationId', str, False),
            ('startTime', str, True),
            ('encounters', list, True),
            ('name', str, False),
            ('assetReferences', list, False),
            ('idConfigs', list, False),
        ]
        self._validate_fields(sighting, sighting_fields, sighting_debug)

        if 'assetReferences' in sighting:
            for filename in sighting['assetReferences']:

                file_path = os.path.join(file_dir, filename)
                file_size = 0
                try:
                    file_size = os.path.getsize(file_path)  # 2for1
                except OSError as err:
                    raise AssetGroupMetadataError(
                        f'Failed to find {filename} in transaction {err} '
                    )
                if file_size < 1:
                    raise AssetGroupMetadataError(f'found zero-size file for {filename}')
                if filename in self.files:
                    raise AssetGroupMetadataError(
                        f'found {filename} in multiple sightings'
                    )

                # Set ensures no duplicates
                self.files.add(filename)

        if 'idConfigs' in sighting:
            id_config_fields = [
                ('algorithms', list, True),
                ('matchingSetDataOwners', str, True),
                ('matchingSetRegions', list, False),
            ]

            num_configs = len(sighting['idConfigs'])
            if num_configs > 1:
                raise AssetGroupMetadataError(
                    f'found multiple {num_configs} ID configs, only support one'
                )

            for config_id in range(num_configs):
                id_config = sighting['idConfigs'][config_id]
                self._validate_fields(id_config, id_config_fields, sighting_debug)
                owners = id_config['matchingSetDataOwners']
                from app.modules.sightings.models import Sighting

                supported_owners = Sighting.get_matching_set_options()
                if owners not in supported_owners:
                    raise AssetGroupMetadataError(
                        f'dataOwners {owners} not supported, only support {supported_owners}'
                    )

        self.owner_assignment = self.validate_encounters(
            sighting['encounters'], f'{encounter_debug}'
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
            # TODO when the definition of what a detection config is is finalised, validate it
            pass

        # validate num sightings
        if not self.bulk_upload and self.num_sightings != 1:
            raise AssetGroupMetadataError(
                'Incorrect num sightings in form submission, there must be exactly one'
            )

        # Ensure that the sighting (and encounters within them) received are valid
        self._validate_sightings()
        self.data_processed = AssetGroupMetadata.DataProcessed.sightings

        if not self.bulk_upload and len(self.request['sightings'][0]['encounters']) != 1:
            raise AssetGroupMetadataError(
                'Incorrect num encounters in form submission, there must be exactly one'
            )

        from app.modules.users.models import User

        if current_user is not None and not current_user.is_anonymous:
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
                "Use uploadType to define type 'bulk' or 'form'"
            )

        if self.anonymous:
            if self.bulk_upload:
                raise AssetGroupMetadataError(
                    'anonymous users not permitted to do bulk upload'
                )
            if self.owner_assignment:
                raise AssetGroupMetadataError(
                    'anonymous users not permitted to assign owners'
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
                        f'Anonymous submitter using active user email {self.submitter_email}; rejecting',
                        'Invalid submitter data',
                        403,
                    )
        elif self.bulk_upload:
            for group in current_user.asset_groups:
                if group.bulk_upload and not group.is_processed():
                    # Only one unprocessed bulk upload allowed at a time
                    raise AssetGroupMetadataError(
                        f'Bulk Upload {group.guid} not processed, please finish this before creating new bulk upload'
                    )

        else:  # Form upload by logged in user
            unprocessed_groups = 0
            for group in current_user.asset_groups:
                if not group.is_processed() and not group.bulk_upload:
                    unprocessed_groups += 1
            # TODO arbitrary limit chosen for now
            if unprocessed_groups > 10:
                raise AssetGroupMetadataError(
                    f'You have {unprocessed_groups} Asset groups outstanding, please finish these first'
                )

    def _validate_sightings(self):
        from app.extensions.tus import tus_upload_dir

        file_dir = tus_upload_dir(current_app, transaction_id=self.tus_transaction_id)

        sighting_num = 0
        # validate sightings content
        for sighting in self.request['sightings']:
            # name is optional so don't check it
            sighting_num += 1
            if not isinstance(sighting, dict):
                raise AssetGroupMetadataError(
                    f'Sighting {sighting_num} needs to be a dict'
                )

            # all files referenced must exist in the tus dir
            self._validate_sighting(
                sighting,
                file_dir,
                f'Sighting {sighting_num}',
                f'Encounter {sighting_num}.',
            )
