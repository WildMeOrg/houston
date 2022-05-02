# -*- coding: utf-8 -*-

from PIL import Image
import pytest

# import tests.utils as test_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_abox_format():
    from app.modules.assets.models import Asset
    from app.modules.annotations.models import Annotation

    asset = Asset()
    image = Image.new('RGB', (1000, 800))
    rtn = asset.draw_annotations(image)
    assert rtn == image

    annot = Annotation(bounds={'rect': [0, 1, 2, 3]})
    asset.annotations.append(annot)

    # no dimensions on asset, so...
    with pytest.raises(ValueError) as ve:
        asset.draw_annotations(image)
        assert str(ve) == 'unable to get original dimensions'

    # fake dimensions on asset, now should work
    asset.meta = {'derived': {'width': 100, 'height': 80}}
    rtn = asset.draw_annotations(image)
    assert rtn.width == image.width
    assert not rtn == image

    rtn = asset.draw_box(image, [1, 2, 3, 4])
    assert rtn
    assert rtn.width == image.width
    assert not rtn == image
    assert rtn.mode == 'RGB'
