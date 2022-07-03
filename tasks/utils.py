# -*- coding: utf-8 -*-
"""
Invoke tasks helper functions
=============================
"""
import functools
import logging
import os

from invoke import Task as BaseTask

from config.utils import _getenv

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Task(BaseTask):
    """
    A patched Invoke Task adding support for decorated functions.
    """

    def __init__(self, *args, **kwargs):
        super(Task, self).__init__(*args, **kwargs)
        # Make these tasks always contextualized (this is the only option in
        # Invoke >=0.13), so we just backport this default on Invoke 0.12.
        self.contextualized = True

    def argspec(self, body):
        """
        See details in https://github.com/pyinvoke/invoke/pull/399.
        """
        if hasattr(body, '__wrapped__'):
            return self.argspec(body.__wrapped__)
        return super(Task, self).argspec(body)


def app_context_task(*wrapper_args, **wrapper_kwargs):
    """
    A helper Invoke Task decorator with auto app context activation.

    Examples:

    >>> @app_context_task
    ... def my_task(context, some_arg, some_option='default'):
    ...     print("Done")

    >>> @app_context_task(
    ...     help={'some_arg': "This is something useful"}
    ... )
    ... def my_task(context, some_arg, some_option='default'):
    ...     print("Done")
    """
    if len(wrapper_args) == 1:
        func = wrapper_args[0]

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """
            A wrapped which tries to get ``app`` from ``kwargs`` or creates a
            new ``app`` otherwise, and actives the application context, so the
            decorated function is run inside the application context.
            """
            app = kwargs.pop('app', None)
            force_enable = kwargs.pop(
                'force_enable', bool(_getenv('FORCE_ENABLE', False))
            )
            force_disable_extensions = kwargs.pop('force_disable_extensions', None)
            force_disable_modules = kwargs.pop('force_disable_modules', None)

            edm_authentication = kwargs.get('edm_authentication', None)

            if app is None:
                from app import create_app

                config_override = {}
                if edm_authentication is not None:

                    edm_authentication = edm_authentication.split(':')
                    if len(edm_authentication) == 3:
                        edm_target, edm_username, edm_password = edm_authentication

                        try:
                            edm_target = int(edm_target)
                        except ValueError:
                            pass

                        config_override['EDM_AUTHENTICATIONS'] = {
                            edm_target: {
                                'username': edm_username,
                                'password': edm_password,
                            }
                        }
                    else:
                        log.warning(
                            'Passed an invalid CLI argument for --edm-authentication.'
                        )

                if force_enable:
                    # We want to force all modules and extensions to load, and we want all
                    # is_X_enabled functions to also work as expected
                    os.environ['FORCE_ENABLE'] = 'ON'

                app = create_app(
                    config_override=config_override,
                    force_enable=force_enable,
                    force_disable_extensions=force_disable_extensions,
                    force_disable_modules=force_disable_modules,
                )

            with app.app_context():
                return func(*args, **kwargs)

        # This is the default in Python 3, so we just make it backwards
        # compatible with Python 2
        if not hasattr(wrapper, '__wrapped__'):
            wrapper.__wrapped__ = func
        return Task(wrapper, **wrapper_kwargs)

    return lambda func: app_context_task(func, **wrapper_kwargs)


def download_file(
    url,
    local_filepath,
    chunk_size=1024 * 512,
    lock_timeout=10,
    http_timeout=None,
    session=None,
):
    # pylint: disable=too-many-arguments
    """
    A helper function which can download a file from a specified ``url`` to a
    local file ``local_filepath`` in chunks and using a file lock to prevent
    a concurrent download of the same file.
    """
    # Avoid unnecessary dependencies when the function is not used.
    import lockfile
    import requests

    log.debug("Checking file existance in '%s'", local_filepath)
    lock = lockfile.LockFile(local_filepath)
    try:
        lock.acquire(timeout=lock_timeout)
    except lockfile.LockTimeout:
        log.info(
            "File '%s' is locked. Probably another instance is still downloading it.",
            local_filepath,
        )
        raise
    try:
        if not os.path.exists(local_filepath):
            log.info("Downloading a file from '%s' to '%s'", url, local_filepath)
            if session is None:
                session = requests
            response = session.get(url, stream=True, timeout=http_timeout)
            if response.status_code != 200:
                log.error("Download '%s' is failed: %s", url, response)
                response.raise_for_status()
            with open(local_filepath, 'wb') as local_file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    # filter out keep-alive new chunks
                    if chunk:
                        local_file.write(chunk)
        log.debug("File '%s' has been downloaded", local_filepath)
        return local_filepath
    finally:
        lock.release()
