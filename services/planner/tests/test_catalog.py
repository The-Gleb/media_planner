import math

import numpy as np

from mediaplan import catalog as catalog_module
from mediaplan.contracts import Catalog


def test_catalog_channels_sorted_like_simulator(catalog: Catalog) -> None:
    assert list(catalog.channel_ids) == sorted(catalog.channel_ids)
    assert len(catalog.channels) == 8


def test_catalog_uses_range_midpoints_only() -> None:
    world_config = catalog_module.load_world_config()
    catalog = catalog_module.build_catalog(world_config)
    by_id = {spec.id: spec for spec in world_config.channels}
    for entry in catalog.channels:
        spec = by_id[entry.channel_id]
        assert math.isclose(entry.cpm_rub, math.sqrt(spec.base.cpm.range.min * spec.base.cpm.range.max))
        assert spec.base.ctr.range.min < entry.ctr < spec.base.ctr.range.max
        assert spec.base.cr.range.min < entry.cr < spec.base.cr.range.max
        assert entry.price_growth == 0.0


def test_hourly_profile_is_a_distribution_with_daytime_peak(catalog: Catalog) -> None:
    assert math.isclose(float(catalog.hourly_profile.sum()), 1.0)
    assert (catalog.hourly_profile > 0).all()
    assert 9 <= int(np.argmax(catalog.hourly_profile)) <= 22
