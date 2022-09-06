# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('annotations'), reason='Annotations module disabled'
)
def test_viewpoint_utils():
    from app.modules.annotations.models import Annotation

    all_viewpoints = {
        'right',
        'frontright',
        'front',
        'frontleft',
        'left',
        'backleft',
        'back',
        'backright',
        'up',
        'upfront',
        'upback',
        'upleft',
        'upright',
        'upfrontleft',
        'upfrontright',
        'upbackleft',
        'upbackright',
        'down',
        'downfront',
        'downback',
        'downleft',
        'downright',
        'downfrontleft',
        'downfrontright',
        'downbackleft',
        'downbackright',
    }

    # just generic validation
    for vp in all_viewpoints:
        assert Annotation.coord_to_viewpoint(Annotation.viewpoint_to_coord(vp)) == vp

    assert not Annotation.viewpoint_to_coord('unknown')

    annot = Annotation(bounds={'rect': [0, 1, 2, 3]})
    for vp in all_viewpoints:
        annot.viewpoint = vp
        n = annot.get_neighboring_viewpoints()
        assert vp in n
        n = annot.get_neighboring_viewpoints(include_self=False)
        assert vp not in n
