# -*- coding: utf-8 -*-
from selenium.webdriver.common.by import By


def test_site_initialization_and_front_page(
    browser, admin_name, site_name, login, logout
):
    login(browser)
    assert browser.find_element(By.TAG_NAME, 'h5').text == site_name
    assert browser.find_element(By.TAG_NAME, 'h4').text == admin_name
    assert browser.find_element(By.TAG_NAME, 'p').text.startswith('User since')

    logout(browser)
    assert browser.find_element(By.TAG_NAME, 'h5').text == site_name
    assert (
        browser.find_element(By.TAG_NAME, 'h1').text == f'Welcome to {site_name.lower()}'
    )
