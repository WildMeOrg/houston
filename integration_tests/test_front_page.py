# -*- coding: utf-8 -*-
def test_front_page(browser, admin_name, site_name, login, logout):
    login(browser)
    assert browser.find_element_by_tag_name('h5').text == site_name
    assert browser.find_element_by_tag_name('h4').text == admin_name
    assert browser.find_element_by_tag_name('h6').text.startswith('User since')

    logout(browser)
    assert browser.find_element_by_tag_name('h5').text == site_name
    assert (
        browser.find_element_by_tag_name('h1').text == f'Welcome to {site_name.lower()}'
    )
