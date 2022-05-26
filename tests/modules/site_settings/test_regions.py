# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import pytest

from tests.utils import extension_unavailable


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_regions():
    from app.modules.site_settings.models import Regions

    top_id = 'top'
    loc1 = 'location-1'
    parent1 = 'A-1'
    loc2 = 'location-2'
    parent2 = 'B-2'
    parent3 = 'B-3'
    regions_test_data = {
        'id': top_id,
        'locationID': [
            {
                'id': parent1,
                'locationID': [
                    {
                        'id': loc1,
                    }
                ],
            },
            {
                'id': parent2,
                'locationID': [
                    {
                        'id': parent3,
                        'locationID': [
                            {
                                'id': loc2,
                            },
                            {
                                # duplicate, just to suck
                                'id': parent1,
                            },
                        ],
                    }
                ],
            },
        ],
    }
    regions = Regions(data=regions_test_data)

    assert not regions.find('fail')
    found = regions.find()
    assert len(found) == 6
    assert found == {top_id, loc1, loc2, parent1, parent2, parent3}
    found = regions.find(id_only=False)
    assert len(found) == 7  # cuz of duplicate parent1

    # second one is len=2 since we find both matching nodes
    assert len(regions.find(parent1)) == 1
    assert len(regions.find(parent1, id_only=False)) == 2

    assert not regions.full_path('fail')
    assert regions.full_path(loc1) == [top_id, parent1, loc1]
    assert regions.full_path(loc2) == [top_id, parent2, parent3, loc2]

    ancestors = regions.with_ancestors([loc1, loc2])
    assert ancestors == {top_id, parent1, parent2, parent3, loc1, loc2}
    trav = regions.traverse()
    assert len(trav) == 7

    found = regions.find_fuzzy('loocetion2')
    assert found
    assert found.get('id') == loc2
    found = regions.find_fuzzy('nothing to see')
    assert not found

    found = regions.find_fuzzy_list(['BE-3', 'pots', 'foo'])
    assert found
    assert found[0].get('id') == parent3
