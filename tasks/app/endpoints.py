# -*- coding: utf-8 -*-
from ._utils import app_context_task


@app_context_task()
def list(context):
    from flask import current_app as app

    rules = []
    max_url_len, max_methods_len, max_endpoint_len = 0, 0, 0
    for rule in app.url_map.iter_rules():
        # Partially copied from __repr__ definition on `werkzeug.routing.Rule`
        parts = []
        for is_dynamic, data in rule._trace:
            if is_dynamic:
                parts.append(f'<{data}>')
            else:
                parts.append(data)
        url = ''.join(parts).lstrip('|')
        methods = ', '.join(rule.methods) if rule.methods is not None else ''

        max_url_len = max(max_url_len, len(url))
        max_methods_len = max(max_methods_len, len(methods))
        max_endpoint_len = max(max_endpoint_len, len(rule.endpoint))
        rules.append(
            (
                url,
                methods,
                rule.endpoint,
            )
        )

    # Print the endpoints in a table format
    print(
        f"{'URL': ^{max_url_len}} | {'Methods': ^{max_methods_len}} | {'Endpoint': ^{max_endpoint_len}}"
    )
    print('-' * (max_url_len + 3 + max_methods_len + 3 + max_endpoint_len))
    for url, methods, endpoint in rules:
        print(
            f'{url: <{max_url_len}} | {methods: <{max_methods_len}} | {endpoint: <{max_endpoint_len}}'
        )
