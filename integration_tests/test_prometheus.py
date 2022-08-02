# -*- coding: utf-8 -*-
import re


def test_prometheus_metrics(session, codex_url):
    response = session.get(codex_url('/metrics'))
    assert response.headers['Content-Type'] == 'text/plain; charset=utf-8'
    content = response.content.decode('utf-8')
    assert 'python_info' in content
    assert 'process_virtual_memory_bytes' in content
    assert 'process_resident_memory_bytes' in content
    assert 'process_start_time_seconds' in content
    assert 'process_cpu_seconds_total' in content
    assert 'info_info' in content
    assert re.search('models{cls="app.modules.users.models.User"} [0-9]+.0', content)
    matches = re.search(
        'requests_total{endpoint="/metrics",method="GET"} ([0-9]+).0', content
    )
    assert matches
    assert re.search(
        'requests_created{endpoint="/metrics",method="GET"} [0-9.]+', content
    )
    requests_total = int(matches.group(1))
    if requests_total > 1:
        responses_total = [
            line for line in content.splitlines() if line.startswith('responses_total')
        ]
        assert (
            f'responses_total{{code="200",endpoint="/metrics",method="GET"}} {requests_total - 1}.0'
            in responses_total
        )
        assert re.search(
            'responses_created{code="200",endpoint="/metrics",method="GET"} [0-9.]+',
            content,
        )
    else:
        assert not re.search(
            'responses_total{{code="200",endpoint="/metrics",method="GET"}} [0-9]+.0',
            content,
        )
        assert not re.search(
            'responses_created{code="200",endpoint="/metrics",method="GET"} [0-9.]+',
            content,
        )
