# -*- coding: utf-8 -*-
import os
import pathlib
import subprocess
import time
from urllib.parse import urljoin

import pytest
import requests
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

TIMEOUT = int(os.getenv('TIMEOUT', 20))
POLL_FREQUENCY = int(os.getenv('POLL_FREQUENCY', 1))
CODEX_URL = os.getenv('CODEX_URL', 'http://localhost:84/')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'root@example.org')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'password')
ADMIN_NAME = os.getenv('ADMIN_NAME', 'Test admin')
BROWSER = os.getenv('BROWSER', 'chrome').lower()
BROWSER_HEADLESS = os.getenv('BROWSER_HEADLESS', 'true').lower() in ('true', 'yes')


def _codex_url(relative_path):
    return urljoin(CODEX_URL, relative_path)


@pytest.fixture
def codex_url():
    return _codex_url


@pytest.fixture
def admin_email():
    return ADMIN_EMAIL


@pytest.fixture
def admin_password():
    return ADMIN_PASSWORD


@pytest.fixture
def admin_name():
    return ADMIN_NAME


def pytest_addoption(parser):
    parser.addoption(
        '--delete-site',
        action='store_true',
        default=False,
        help='Clear the houston, edm and sage databases.  Can be used to test initialization',
    )


@pytest.fixture(scope='session', autouse=True)
def delete_site(pytestconfig):
    if pytestconfig.getoption('delete_site'):
        services = [
            'sage',
            'houston',
            'celery_worker',
            'celery_beat',
        ]
        databases = ['wildbook', 'houston', 'sage']
        commands = (['docker-compose', 'rm', '-f', '--stop'] + services,)
        db = ['docker-compose', 'exec', 'db']
        for database in databases:
            commands += (
                db + ['dropdb', '-U', 'postgres', database],
                db + ['createdb', '-O', database, '-U', 'postgres', database],
            )
        commands += (
            [
                'docker',
                'volume',
                'rm',
                'houston_sage-database-var',
                'houston_sage-cache-var',
            ],
        )
        commands += (['docker-compose', 'up', '-d'] + services,)
        for command in commands:
            print(f'Running {command}')
            subprocess.run(command)
        print('Wait for sage to be up')
        response = None
        timeout = 180  # timeout after 3 minutes
        while response is None and timeout >= 0:
            try:
                response = requests.get('http://localhost:82')
                break
            except requests.exceptions.ConnectionError:
                time.sleep(5)
                timeout -= 5
                pass
        else:
            assert False, 'Unable to connect to sage'


@pytest.fixture(autouse=True, scope='session')
def cleanup():
    yield
    session = requests.Session()
    # Remove all groups
    # Run the integration test enough times and it leaves a load of groups which causes the limit to be reached
    login_session(session)
    groups = session.get(_codex_url('/api/v1/asset_groups/'))
    for group_dat in groups.json():
        group_guid = group_dat['guid']
        session.delete(_codex_url(f'/api/v1/asset_groups/{group_guid}'))


def wait_until(browser, func, timeout=TIMEOUT, poll_frequency=POLL_FREQUENCY):
    WebDriverWait(browser, timeout, poll_frequency).until(func)


def login_session(session, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    return session.post(
        urljoin(CODEX_URL, '/api/v1/auth/sessions'),
        {'email': email, 'password': password},
    )


@pytest.fixture
def login():
    def _login(session, *args, **kwargs):
        return login_session(session, *args, **kwargs)

    return _login


@pytest.fixture
def logout():
    def _logout(session, *args, **kwargs):
        return session.post(urljoin(CODEX_URL, '/logout'))

    return _logout


@pytest.fixture
def browser():
    if BROWSER.lower() == 'chrome':
        options = webdriver.ChromeOptions()
        if BROWSER_HEADLESS:
            options.add_argument('--headless')
        browser = webdriver.Chrome(options=options)
    elif BROWSER.lower() == 'firefox':
        options = webdriver.firefox.options.Options()
        if BROWSER_HEADLESS:
            options.headless = True
        browser = webdriver.Firefox(options=options)
    else:
        raise ValueError(
            f'Unrecognized browser "{BROWSER}". Valid choices are: chrome, firefox'
        )
    browser.set_window_size(1920, 1080)
    try:
        yield browser
    except Exception:
        browser_failure_handler(browser)
        raise
    finally:
        browser.quit()


@pytest.fixture
def session(browser):
    # Depends on browser for the initialization stuff
    yield requests.Session()


def browser_failure_handler(browser):
    with open('codex.html', 'w') as f:
        f.write(browser.page_source)
    browser.save_screenshot('codex.png')
    if BROWSER.lower() != 'firefox':
        # Firefox doesn't seem to support getting the browser console log:
        #   selenium.common.exceptions.WebDriverException: Message: HTTP method not allowed
        print('Browser console log:')
        for log in browser.get_log('browser'):
            print(log)
    print('See codex.html and codex.png')


def pytest_exception_interact(node, call, report):
    if (
        hasattr(node, 'funcargs')
        and 'browser' in node.funcargs
        and 'session' not in node.funcargs
    ):
        # Save screenshot and page source when there's an exception
        browser = node.funcargs['browser']
        browser_failure_handler(browser)


@pytest.fixture
def test_root():
    return pathlib.Path('tests/asset_groups/test-000/')
