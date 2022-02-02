# -*- coding: utf-8 -*-
from flask import Blueprint, request, make_response
import base64
import os
import redis
import uuid
from urllib.parse import urljoin
from werkzeug.utils import secure_filename as werkzeug_secure_filename

# Find the stack on which we want to store the database connection.
# Starting with Flask 0.9, the _app_ctx_stack is the correct one,
# before that we need to use the _request_ctx_stack.
try:
    from flask import _app_ctx_stack as stack
except ImportError:  # pragma: no cover
    from flask import _request_ctx_stack as stack


class TusManager(object):
    def __init__(self, app=None, overwrite=True, upload_finish_cb=None):
        self.tus_api_version = '1.0.0'
        self.tus_api_version_supported = '1.0.0'
        self.tus_api_extensions = ['creation', 'termination', 'file-check']
        self.tus_max_file_size = 4294967296  # 4GByte (in bytes)
        self.file_overwrite = overwrite
        self.upload_finish_cb = upload_finish_cb
        self.upload_file_handler_cb = None

        self.blueprint = Blueprint('tus-manager', __name__)

        if app is not None:
            self.init_app(app)

    def init_app(self, app, upload_url='/file-upload'):
        self.upload_url = app.config.get('tus_uploads_url', upload_url)
        self.upload_folder = app.config['UPLOADS_DATABASE_PATH']
        self.tus_max_file_size = app.config.get('tus_max_file_size_in_bytes', 4294967296)
        self.file_overwrite = app.config.get('tus_file_overwrite', True)
        self.redis_connection_string = app.config['REDIS_CONNECTION_STRING']

        self._register_routes()
        self.app = app
        self.app.register_blueprint(self.blueprint)

    def _register_routes(self):

        # Note on routing names and method names.
        # Use '-' to separate words/parts in endpoint.
        # Use '_" to separate words/parts in method name.
        # Use "tus" to start name
        #   followed by "core" or the extension name
        #   followed by protocol version (ommitting any trailing ".0"s and replacing '.' with '-' or '_')
        #   followed by a brief human redable description of what this method does
        #
        # Use "proprietary" instead of "core" or extension name for any features that are proprietary to this
        # implementation.

        # routes without resource id
        self.blueprint.add_url_rule(
            self.upload_url,
            'tus-proprietary-get-file-exists',
            self.tus_proprietary_get_file_exists,
            methods=['GET'],
            provide_automatic_options=False,
        )
        self.blueprint.add_url_rule(
            self.upload_url,
            'tus-1-get-server-info',
            self.tus_1_get_server_info,
            methods=['OPTIONS'],
        )
        # Tus protocol docs Creation section 6.a.iii
        self.blueprint.add_url_rule(
            self.upload_url,
            'tus-creation-1-create',
            self.tus_creation_1_create,
            methods=['POST'],
        )

        # routes with resource id
        # Tus protocol docs Core section 5.c.i.
        self.blueprint.add_url_rule(
            f'{self.upload_url}/<resource_id>',
            'tus-1-get-resume-info',
            self.tus_1_get_resume_info,
            methods=['HEAD'],
        )
        # Tus protocol docs Core section 5.c.ii
        self.blueprint.add_url_rule(
            f'{self.upload_url}/<resource_id>',
            'tus-1-upload-chunk',
            self.tus_1_upload_chunk,
            methods=['PATCH'],
        )
        # Tus protocol docs Termination section 6.e.i
        self.blueprint.add_url_rule(
            f'{self.upload_url}/<resource_id>',
            'tus-1-delete',
            self.tus_1_delete,
            methods=['DELETE'],
        )

    def upload_file_handler(self, callback):
        self.upload_file_handler_cb = callback
        return callback

    # handle redis server connection
    def redis_connect(self):
        return redis.from_url(self.redis_connection_string)

    @property
    def redis_connection(self):
        ctx = stack.top
        if ctx is not None:
            if not hasattr(ctx, 'tus_redis'):
                ctx.tus_redis = self.redis_connect()
            return ctx.tus_redis

    def _parse_metadata(self):
        metadata = {}
        upload_metadata = request.headers.get('Upload-Metadata')
        if upload_metadata:
            for kv in upload_metadata.split(','):
                (key, value) = kv.split(' ')
                metadata[key] = base64.b64decode(value).decode('utf-8')

        insecure_filename = metadata.get('filename', None)
        if insecure_filename is not None:
            secure_filename = werkzeug_secure_filename(insecure_filename)
            metadata['filename'] = secure_filename

        return metadata

    # Untested. Possibly unused.
    def tus_proprietary_get_file_exists(self):
        # print('begin tus_proprietary_get_file_exists')
        response = make_response('', 200)
        if 'Upload-Metadata' in request.headers:
            response.headers['Upload-Metadata'] = request.headers['Upload-Metadata']

        metadata = self._parse_metadata()

        if metadata.get('filename', None) is None:
            return make_response('metadata filename is not set', 404)

        (filename_name, extension) = os.path.splitext(metadata.get('filename'))
        if filename_name.upper() in [
            os.path.splitext(f)[0].upper() for f in os.listdir(self.upload_folder)
        ]:
            response.headers['Tus-File-Name'] = metadata.get('filename')
            response.headers['Tus-File-Exists'] = True
        else:
            response.headers['Tus-File-Exists'] = False
        return response

    def create_resource_id(self):
        return str(uuid.uuid4())

    def create_url(self, resource_id):
        url_root = request.url_root
        # assuming(!) we only ever want to upgrade from http to https, not the other way around
        if (
            'X-Forwarded-Proto' in request.headers
            and request.headers.get('X-Forwarded-Proto') == 'https'
            and url_root.lower().startswith('http:')
        ):
            url_root = 'https://' + url_root[7:]
        return urljoin(url_root, f'{self.upload_url}/{resource_id}')

    def tus_creation_1_create(self):
        """Implements POST to create file according to Tus protocol Creation extension"""
        # print('begin tus_creation_1_create')
        response = make_response('', 200)
        response.headers['Tus-Resumable'] = self.tus_api_version
        response.headers['Tus-Version'] = self.tus_api_version_supported

        if 'Upload-Metadata' in request.headers:
            response.headers['Upload-Metadata'] = request.headers['Upload-Metadata']

        if request.headers.get('Tus-Resumable') is None:
            self.app.logger.warning(
                'Received File upload for unsupported file transfer protocol'
            )
            response.data = 'Received File upload for unsupported file transfer protocol'
            response.status_code = 500
            return response

        # process upload metadata
        metadata = self._parse_metadata()

        if (
            os.path.lexists(os.path.join(self.upload_folder, metadata.get('filename')))
            and self.file_overwrite is False
        ):
            response.status_code = 409
            return response

        file_size = int(request.headers.get('Upload-Length', '0'))
        resource_id = self.create_resource_id()

        p = self.redis_connection.pipeline()
        p.setex(
            'file-uploads/{}/filename'.format(resource_id),
            3600,
            '{}'.format(metadata.get('filename')),
        )
        p.setex('file-uploads/{}/file_size'.format(resource_id), 3600, file_size)
        p.setex('file-uploads/{}/offset'.format(resource_id), 3600, 0)
        p.setex(
            'file-uploads/{}/upload-metadata'.format(resource_id),
            3600,
            request.headers.get('Upload-Metadata'),
        )
        p.execute()

        try:
            open(os.path.join(self.upload_folder, resource_id), 'w').close()
        except IOError as e:
            self.app.logger.error('Unable to create file: {}'.format(e))
            response.status_code = 500
            return response

        response.status_code = 201
        response.headers['Location'] = self.create_url(resource_id)
        response.headers['Tus-Temp-Filename'] = resource_id
        response.autocorrect_location_header = False

        return response

    # Untested. should be part of protocol, identify sections and verify correctness
    def tus_1_get_server_info(self):
        # print('begin tus_1_get_server_info')
        response = make_response('', 200)
        if 'Upload-Metadata' in request.headers:
            response.headers['Upload-Metadata'] = request.headers['Upload-Metadata']

        if request.headers.get('Access-Control-Request-Method', None) is not None:
            # CORS option request, return 200
            return response

        response.headers['Tus-Resumable'] = self.tus_api_version
        response.headers['Tus-Version'] = self.tus_api_version_supported

        response.headers['Tus-Extension'] = ','.join(self.tus_api_extensions)
        response.headers['Tus-Max-Size'] = self.tus_max_file_size

        response.status_code = 204
        return response

    def tus_1_get_resume_info(self, resource_id):
        """Implements HEAD according to Tus Core protocol."""
        response = make_response('', 204)
        response.headers['Tus-Resumable'] = self.tus_api_version
        response.headers['Tus-Version'] = self.tus_api_version_supported
        response.headers['Cache-Control'] = 'no-store'

        offset = self.redis_connection.get('file-uploads/{}/offset'.format(resource_id))
        length = self.redis_connection.get(
            'file-uploads/{}/file_size'.format(resource_id)
        )
        metadata = self.redis_connection.get(
            'file-uploads/{}/upload-metadata'.format(resource_id)
        )

        if offset is None:
            response.status_code = 404
            return response

        response.status_code = 200
        response.headers['Upload-Offset'] = offset
        if length is not None:
            response.headers['Upload-Length'] = length
        if metadata is None:
            response.headers['Upload-Metadata'] = request.headers['Upload-Metadata']

        return response

    def tus_1_upload_chunk(self, resource_id):
        """Implements DELETE according to Tus Core protocol"""
        response = make_response('', 204)
        response.headers['Tus-Resumable'] = self.tus_api_version
        response.headers['Tus-Version'] = self.tus_api_version_supported

        # TODO: update following variable names to reflect "ours" (from redis) and "supplied" from headers
        filename = self.redis_connection.get(
            'file-uploads/{}/filename'.format(resource_id)
        ).decode('utf-8')
        file_size = int(
            self.redis_connection.get('file-uploads/{}/file_size'.format(resource_id))
        )
        redis_offset = self.redis_connection.get(
            'file-uploads/{}/offset'.format(resource_id)
        ).decode('utf-8')

        file_offset = int(request.headers.get('Upload-Offset', 0))
        chunk_size = int(request.headers.get('Content-Length', 0))
        header_offset = request.headers.get('Upload-Offset')

        upload_file_path = os.path.join(self.upload_folder, resource_id)

        if filename is None or os.path.lexists(upload_file_path) is False:
            self.app.logger.info(
                'PATCH sent for resource_id that does not exist. {}'.format(resource_id)
            )
            response.status_code = 410
            return response

        if header_offset != redis_offset:
            response.status_code = 409  # HTTP 409 Conflict
            return response

        try:
            f = open(upload_file_path, 'r+b')
        except IOError:
            f = open(upload_file_path, 'wb')
        finally:
            f.seek(file_offset)
            f.write(request.data)
            f.close()

        new_offset = self.redis_connection.incrby(
            'file-uploads/{}/offset'.format(resource_id), chunk_size
        )
        response.headers['Upload-Offset'] = new_offset
        response.headers['Tus-Temp-Filename'] = resource_id

        if (
            file_size == new_offset
        ):  # file transfer complete, rename from resource id to actual filename
            try:
                secure_filename = werkzeug_secure_filename(filename)
                if self.upload_file_handler_cb is None:
                    os.rename(
                        upload_file_path,
                        os.path.join(self.upload_folder, secure_filename),
                    )
                else:
                    filename = self.upload_file_handler_cb(
                        upload_file_path, secure_filename, request, self.app
                    )
            finally:
                self._remove_resources(resource_id)

            if self.upload_finish_cb is not None:
                self.upload_finish_cb()

        return response

    def _remove_resources(self, resource_id):
        p = self.redis_connection.pipeline()
        p.delete('file-uploads/{}/filename'.format(resource_id))
        p.delete('file-uploads/{}/file_size'.format(resource_id))
        p.delete('file-uploads/{}/offset'.format(resource_id))
        p.delete('file-uploads/{}/upload-metadata'.format(resource_id))
        p.execute()

        upload_file_path = os.path.join(self.upload_folder, resource_id)
        try:
            os.remove(upload_file_path)
        except FileNotFoundError:
            pass

    def tus_1_delete(self, resource_id):
        """Implements DELETE according to Tus Termination protocol"""
        response = make_response('', 204)
        response.headers['Tus-Resumable'] = self.tus_api_version
        response.headers['Tus-Version'] = self.tus_api_version_supported

        self._remove_resources(resource_id)

        response.status_code = 204
        return response
