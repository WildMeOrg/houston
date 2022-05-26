# -*- coding: utf-8 -*-
import os
import pathlib
import subprocess
import time
from urllib.parse import urljoin

import pytest
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

TIMEOUT = int(os.getenv('TIMEOUT', 20))
POLL_FREQUENCY = int(os.getenv('POLL_FREQUENCY', 1))
CODEX_URL = os.getenv('CODEX_URL', 'http://localhost:84/')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'root@example.org')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'password')
ADMIN_NAME = os.getenv('ADMIN_NAME', 'Test admin')
SITE_NAME = os.getenv('SITE_NAME', 'My test site')
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


@pytest.fixture
def site_name():
    return SITE_NAME


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
            'edm',
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


def login_browser(browser, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    browser.get(CODEX_URL)
    wait_until(browser, lambda b: b.find_element(By.LINK_TEXT, 'Login'))
    browser.find_element(By.LINK_TEXT, 'Login').click()
    wait_until(browser, lambda b: b.find_element(By.ID, 'email'))
    browser.find_element(By.ID, 'email').send_keys(email)
    browser.find_element(By.ID, 'password').send_keys(password + Keys.ENTER)
    wait_until(browser, lambda b: 'User since' in b.page_source)


def login_session(session, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    return session.post(
        urljoin(CODEX_URL, '/api/v1/auth/sessions'),
        {'email': email, 'password': password},
    )


@pytest.fixture
def login():
    def _login(browser_or_session, *args, **kwargs):
        if isinstance(browser_or_session, requests.sessions.Session):
            return login_session(browser_or_session, *args, **kwargs)
        return login_browser(browser_or_session, *args, **kwargs)

    return _login


def logout_browser(browser):
    header = browser.find_element(By.CLASS_NAME, 'MuiToolbar-root')
    last_button = header.find_elements(By.TAG_NAME, 'button')[-1]
    last_button.click()
    for li in browser.find_elements(By.TAG_NAME, 'li'):
        if li.text == 'Log out':
            li.click()
    wait_until(browser, lambda b: b.find_element(By.LINK_TEXT, 'Login'))


def logout_session(session):
    return session.post(urljoin(CODEX_URL, '/logout'))


@pytest.fixture
def logout():
    def _logout(browser_or_session, *args, **kwargs):
        if isinstance(browser_or_session, requests.sessions.Session):
            return logout_session(browser_or_session, *args, **kwargs)
        return logout_browser(browser_or_session, *args, **kwargs)

    return _logout


def initialize(browser):
    browser.get(CODEX_URL)
    timeout = 240
    while True:
        wait_until(browser, lambda b: '</title>' in b.page_source)
        if 'Server unavailable' not in browser.page_source:
            break
        time.sleep(10)
        browser.refresh()
        timeout -= 10
        if timeout <= 0:
            assert False, 'Server unavailable'
    wait_until(
        browser,
        lambda b: 'Codex initialized!' in b.page_source
        or b.find_element(By.LINK_TEXT, 'Login'),
    )
    if 'Codex initialized!' not in browser.page_source:
        # Already initialized
        return

    browser.find_element(By.ID, 'email').send_keys(ADMIN_EMAIL)
    browser.find_element(By.ID, 'password1').send_keys(ADMIN_PASSWORD)
    browser.find_element(By.ID, 'password2').send_keys(ADMIN_PASSWORD)
    browser.find_element(By.ID, 'createAdminUser').click()

    wait_until(browser, lambda b: 'Welcome to Codex!' in b.page_source)
    inputs = browser.find_elements(By.TAG_NAME, 'input')
    # Site name
    # inputs[0].clear() does not work in chrome
    # len(inputs[0].text) returns 0 in chrome
    inputs[0].send_keys(Keys.BACKSPACE * 50)
    inputs[0].send_keys(SITE_NAME)
    # Tagline
    inputs[3].send_keys(Keys.BACKSPACE * 50)
    inputs[3].send_keys(f'Welcome to {SITE_NAME.lower()}')

    textareas = browser.find_elements(By.TAG_NAME, 'textarea')
    # Tagline subtitle
    textareas[0].send_keys(Keys.BACKSPACE * len(textareas[0].text))
    textareas[0].send_keys('AI for the conservation of zebras.')
    # Site description
    textareas[2].send_keys(Keys.BACKSPACE * len(textareas[2].text))
    textareas[2].send_keys(
        'Researchers use my test site to identify and organize sightings of zebras.'
    )

    for button in browser.find_elements(By.TAG_NAME, 'button'):
        if button.text == 'FINISH SETUP':
            button.click()
            break

    wait_until(browser, lambda b: 'Set up profile' in b.page_source)
    browser.find_element(By.ID, 'name').send_keys(ADMIN_NAME)
    browser.find_element(By.ID, 'saveProfile').click()
    wait_until(
        browser, lambda b: b.find_element(By.TAG_NAME, 'p').text.startswith('User since')
    )

    logout_browser(browser)


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
        initialize(browser)
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
