# -*- coding: utf-8 -*-
import os

SITE_NAME = os.getenv('SITE_NAME', 'My test site')


def test_site_setup(
    session,
    codex_url,
    admin_name,
    admin_email,
    admin_password,
    login,
):
    tagline = f'Welcome to {SITE_NAME.lower()}'
    tagline_subtitle = 'Exactly how many levels of site description do we really need'
    description = 'Developers use my test site to do some testing.'
    site_data = session.get(codex_url('/api/v1/site-settings/data')).json()
    if not site_data['site.adminUserInitialized']:
        session.post(
            codex_url('/api/v1/users/admin_user_initialized'),
            json={'email': admin_email, 'password': admin_password},
        )
        login(session)
        new_site_data = {
            'site.needsSetup': False,
            'site.general.tagline': tagline,
            'site.general.taglineSubtitle': tagline_subtitle,
            'site.name': SITE_NAME,
            'site.general.description': description,
        }
        session.post(
            codex_url('/api/v1/site-settings/data'),
            json=new_site_data,
        )
        me = session.get(codex_url('/api/v1/users/me')).json()
        name_patch = [
            {
                'op': 'replace',
                'path': '/full_name',
                'value': admin_name,
            },
        ]
        session.patch(
            codex_url(f"/api/v1/users/{me['guid']}"),
            json=name_patch,
        )
    else:
        login(session)

    # Now read it back and make sure that it's what we set
    site_data = session.get(codex_url('/api/v1/site-settings/data')).json()
    assert site_data['site.name']['value'] == SITE_NAME
    assert site_data['site.general.description']['value'] == description
    assert site_data['site.general.tagline']['value'] == tagline
    assert site_data['site.general.taglineSubtitle']['value'] == tagline_subtitle

    me = session.get(codex_url('/api/v1/users/me')).json()
    assert me['full_name'] == admin_name
    assert me['email'] == admin_email
