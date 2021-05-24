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

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AssetGroupMetadataError(Exception):
    def __init__(self, log_message, message=None, status_code=400):
        self.message = message
        self.status_code = status_code
        if self.message is None:
            self.message = log_message
        log.warning(f'Failed: {log_message} {self.status_code}')


class BaseAssetGroupMetadata(object):
    def __init__(self, request_json):
        self.request_json = request_json
        self.request = {}
        self.files = set()

    # Helper for validating the required fields in any level dictionary
    def _validate_fields(self, dictionary, fields, error_str):
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

    def _validate_sighting(self, sighting, file_dir, sighting_debug, encounter_debug):

        sighting_fields = [
            ('locationId', str, False),
            ('startTime', str, True),
            ('context', str, True),
            ('encounters', list, True),
            ('name', str, False),
        ]
        self._validate_fields(sighting, sighting_fields, sighting_debug)

        encounter_num = 0
        # Have a sighting with multiple encounters, make sure we have all of the files
        for encounter in sighting['encounters']:
            encounter_num += 1
            if not isinstance(encounter, dict):
                raise AssetGroupMetadataError(
                    f'{encounter_debug}{encounter_num} needs to be a dict'
                )
            encounter_fields = [
                ('assetReferences', list, False),
                ('ownerEmail', str, False),
            ]
            self._validate_fields(
                encounter,
                encounter_fields,
                f'{encounter_debug}{encounter_num}',
            )

            # Can reassign encounter owner but only to a valid user
            if 'ownerEmail' in encounter:
                from app.modules.users.models import User

                if not isinstance(encounter['ownerEmail'], str):
                    raise AssetGroupMetadataError(
                        f'{encounter_debug}{encounter_num} ownerEmail must be a string'
                    )
                owner_email = encounter['ownerEmail']
                encounter_owner = User.find(email=owner_email)
                if encounter_owner is None:
                    raise AssetGroupMetadataError(
                        f'{encounter_debug}{encounter_num} owner {owner_email} not found'
                    )
                else:
                    self.owner_assignment = True

            for filename in encounter['assetReferences']:

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
                # Set ensures no duplicates
                self.files.add(filename)


# Class used to process and validate the json data. This json may be received from the frontend or
# read from a file in the case of a restart. This class creates no DB objects, it just validates
# what is read and raises an AssetGroupMetadataError on failure
class CreateAssetGroupMetadata(BaseAssetGroupMetadata):
    # Certain properties only become valid once sufficient processing of data has occurred
    class DataProcessed(str, enum.Enum):
        unprocessed = 0
        first_level = 1
        sightings = 2
        complete = 3

    def __init__(self, request_json):
        super().__init__(request_json)
        self.owner = None
        self.owner_assignment = False
        self.anonymous_submitter = None
        self.data_processed = CreateAssetGroupMetadata.DataProcessed.unprocessed

    @property
    def bulk_upload(self):
        assert self.data_processed >= CreateAssetGroupMetadata.DataProcessed.first_level
        return self.request['bulkUpload']

    @property
    def location_id(self):
        assert self.data_processed >= CreateAssetGroupMetadata.DataProcessed.first_level
        return self.request['locationId']

    @property
    def tus_transaction_id(self):
        assert self.data_processed >= CreateAssetGroupMetadata.DataProcessed.first_level
        return self.request['transactionId']

    @property
    def detection_configs(self):
        assert self.data_processed >= CreateAssetGroupMetadata.DataProcessed.first_level
        return self.request['speciesDetectionModel']

    @property
    def num_sightings(self):
        return len(self.get_sightings())

    def get_sightings(self):
        assert self.data_processed >= CreateAssetGroupMetadata.DataProcessed.first_level
        return self.request['sightings']

    @property
    def submitter_email(self):
        assert self.data_processed >= CreateAssetGroupMetadata.DataProcessed.first_level
        return (
            self.request['submitterEmail'] if 'submitterEmail' in self.request else None
        )

    @property
    def description(self):
        assert self.data_processed >= CreateAssetGroupMetadata.DataProcessed.first_level
        return self.request['description'] if 'description' in self.request else ''

    @property
    def anonymous(self):
        assert self.data_processed >= CreateAssetGroupMetadata.DataProcessed.first_level
        from app.modules.users.models import User

        return self.owner is User.get_public_user()

    def process_request(self):
        try:
            self.request.update(self.request_json)
        except Exception:
            raise AssetGroupMetadataError('Failed to parse request')

        # Parse according to docs.google.com/document/d/11TMq1qzaQxva97M3XYwaEYYUawJ5VsrRXnJvTQR_nG0/edit?pli=1#
        top_level_fields = [
            ('bulkUpload', bool, True),
            ('speciesDetectionModel', list, True),
            ('transactionId', str, True),
            ('sightings', list, True),
            ('submitterEmail', str, False),
            ('description', str, False),
        ]
        self._validate_fields(self.request, top_level_fields, 'request')

        self.data_processed = CreateAssetGroupMetadata.DataProcessed.first_level
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
        self.data_processed = CreateAssetGroupMetadata.DataProcessed.sightings

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
        self.data_processed = CreateAssetGroupMetadata.DataProcessed.complete

    def _validate_contents(self):
        # Message was valid, is the user allowed to do so
        from app.modules.users.models import User

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


class PatchAssetGroupSightingMetadata(BaseAssetGroupMetadata):
    def process_request(self, asset_group_sighting):
        # TODO is this a valid test, can we assume that "our" patch is always patch 0
        if (
            not isinstance(self.request_json, list)
            or not len(self.request_json) == 1
            or not isinstance(self.request_json[0], dict)
            or 'value' not in self.request_json[0]
        ):
            raise AssetGroupMetadataError('patch needs to be a list of 1')
        self.request = self.request_json[0]['value']

        # all files referenced must exist in the asset_group dir and the same validity checks for the
        # sighting fields are applied as for the creation
        self._validate_sighting(
            self.request,
            f'{asset_group_sighting.asset_group.get_absolute_path()}/_asset_group/',
            'AssetGroupSighting ',
            'Encounter ',
        )
