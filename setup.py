#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division
import subprocess
import os

from setuptools import setup


PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))


def git_version():
    """
    Return the sha1 of local git HEAD as a string.
    """

    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH', 'PYTHONPATH']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'
        out = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env).communicate()[0]
        return out

    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', 'HEAD'])
        git_revision = out.strip().decode('ascii')
    except OSError:
        git_revision = 'unknown-git'
    return git_revision


CLASSIFIERS = """
Development Status :: 3 - Alpha
Intended Audience :: Developers
Intended Audience :: System Administrators
License :: OSI Approved :: GNU General Public License v3 (GPLv3)
Natural Language :: English
Operating System :: POSIX
Operating System :: Unix
Operating System :: MacOS
Programming Language :: Python
Programming Language :: Python :: 3.7
Topic :: Internet :: WWW/HTTP :: Dynamic Content
"""
NAME = 'Houston'
MAINTAINER = 'Wild Me, non-profit'
MAINTAINER_EMAIL = 'dev@wildme.org'
DESCRIPTION = 'The backend server for the new Wildbook frontend and API.'
LONG_DESCRIPTION = DESCRIPTION
KEYWORDS = ['wild me', 'hoston', 'wildbook']
URL = 'https://hoston.dyn.wildme.io/'
DOWNLOAD_URL = ''
LICENSE = 'Apache'
AUTHOR = MAINTAINER
AUTHOR_EMAIL = MAINTAINER_EMAIL
PLATFORMS = ['Linux', 'Mac OS-X', 'Unix']
MAJOR = 0
MINOR = 1
MICRO = 0
REVISION = git_version()
SUFFIX = REVISION[:8]
VERSION = '%d.%d.%d' % (MAJOR, MINOR, MICRO)
if SUFFIX:
    VERSION = '%s.%s' % (VERSION, SUFFIX)
PACKAGES = ['.']


def write_version_py(filename=os.path.join(PROJECT_ROOT, 'app', 'version.py')):
    cnt = """
# THIS FILE IS GENERATED FROM SETUP.PY
version = '%(version)s'
git_revision = '%(git_revision)s'
full_version = '%%(version)s.%%(git_revision)s' %% {
    'version': version,
    'git_revision': git_revision,
}
"""
    FULL_VERSION = VERSION
    if os.path.isdir('.git'):
        GIT_REVISION = REVISION
    elif os.path.exists(filename):
        GIT_REVISION = 'RELEASE'
    else:
        GIT_REVISION = 'unknown'

    FULL_VERSION += '.' + GIT_REVISION
    text = cnt % {'version': VERSION, 'git_revision': GIT_REVISION}
    try:
        with open(filename, 'w') as a:
            a.write(text)
    except Exception as e:
        print(e)


def parse_requirements(fname='requirements.txt', with_version=True):
    """
    Parse the package dependencies listed in a requirements file but strips
    specific versioning information.

    Args:
        fname (str): path to requirements file
        with_version (bool, default=True): if true include version specs

    Returns:
        List[str]: list of requirements items

    CommandLine:
        python -c "import setup; print(setup.parse_requirements())"
        python -c "import setup; print(chr(10).join(setup.parse_requirements(with_version=True)))"
    """
    import re
    import sys
    from os.path import exists

    require_fpath = fname

    def parse_line(line):
        """
        Parse information from a line in a requirements text file
        """
        if line.startswith('-r '):
            # Allow specifying requirements in other files
            target = line.split(' ')[1]
            for info in parse_require_file(target):
                yield info
        else:
            info = {'line': line}
            if line.startswith('-e '):
                info['package'] = line.split('#egg=')[1]
            else:
                # Remove versioning from the package
                pat = '(' + '|'.join(['>=', '==', '>']) + ')'
                parts = re.split(pat, line, maxsplit=1)
                parts = [p.strip() for p in parts]

                info['package'] = parts[0]
                if len(parts) > 1:
                    op, rest = parts[1:]
                    if ';' in rest:
                        # Handle platform specific dependencies
                        # http://setuptools.readthedocs.io/en/latest/setuptools.html#declaring-platform-specific-dependencies
                        version, platform_deps = map(str.strip, rest.split(';'))
                        info['platform_deps'] = platform_deps
                    else:
                        version = rest  # NOQA
                    info['version'] = (op, version)
            yield info

    def parse_require_file(fpath):
        with open(fpath, 'r') as f:
            for line in f.readlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    for info in parse_line(line):
                        yield info

    def gen_packages_items():
        if exists(require_fpath):
            for info in parse_require_file(require_fpath):
                parts = [info['package']]
                if with_version and 'version' in info:
                    parts.extend(info['version'])
                if not sys.version.startswith('3.4'):
                    # apparently package_deps are broken in 3.4
                    platform_deps = info.get('platform_deps')
                    if platform_deps is not None:
                        parts.append(';' + platform_deps)
                item = ''.join(parts)
                yield item

    packages = list(gen_packages_items())
    return packages


def do_setup():
    # Define requirements
    requirements = []
    requirements.extend(parse_requirements('tasks/requirements.txt'))
    requirements.extend(parse_requirements('app/requirements.txt'))
    # Define optional requirements (e.g. `pip install ".[testing]"`)
    optional_requirements = {
        'testing': parse_requirements('tests/requirements.txt'),
        'docs': parse_requirements('docs/requirements.txt'),
    }

    write_version_py()
    setup(
        name=NAME,
        version=VERSION,
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        classifiers=CLASSIFIERS,
        author=AUTHOR,
        author_email=AUTHOR_EMAIL,
        url=URL,
        license=LICENSE,
        platforms=PLATFORMS,
        packages=PACKAGES,
        install_requires=requirements,
        extras_require=optional_requirements,
        keywords=CLASSIFIERS.replace('\n', ' ').strip(),
    )


if __name__ == '__main__':
    do_setup()
