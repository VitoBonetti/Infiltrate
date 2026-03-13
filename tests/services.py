from django.core.exceptions import ValidationError
from tests.models import Test
from assets.models import Asset

def add_asset_to_test(test: Test, asset: Asset):
    """
    Safe add with single-market constraint even before test.clean() sees it.
    """
    existing_assets = test.assets.select_related("organization__market").all()
    existing_market_ids = {a.organization.market_id for a in existing_assets}

    new_market_id = asset.organization.market_id
    if existing_market_ids and (new_market_id not in existing_market_ids):
        raise ValidationError("Cannot add asset: test would span multiple markets.")
    test.assets.add(asset)

def remove_asset_from_test(test: Test, asset: Asset):
    test.assets.remove(asset)