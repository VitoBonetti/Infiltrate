from regions.models import Regions
from markets.models import Market
from organizations.models import Organization
from assets.models import Asset
from tests.models import Test

def scope_kind(obj) -> str:
    if isinstance(obj, Regions): return "region"
    if isinstance(obj, Market): return "market"
    if isinstance(obj, Organization): return "organization"
    if isinstance(obj, Asset): return "asset"
    if isinstance(obj, Test): return "test"
    raise TypeError(f"Unsupported scope type: {type(obj)}")

def get_market_for_scope_any(obj) -> Market:
    if isinstance(obj, Market):
        return obj
    if isinstance(obj, Organization):
        return obj.market
    if isinstance(obj, Asset):
        return obj.organization.market
    if isinstance(obj, Test):
        # Test must be single-market via assets
        assets = obj.assets.select_related("organization__market").all()
        market_ids = {a.organization.market_id for a in assets}
        if len(market_ids) == 0:
            raise ValueError("Test has no assets yet; market is undefined.")
        if len(market_ids) > 1:
            raise ValueError("Test spans multiple markets; forbidden by design.")
        return assets[0].organization.market
    if isinstance(obj, Regions):
        raise ValueError("Region has many markets.")
    raise TypeError

def get_region_for_scope_any(obj) -> Regions:
    if isinstance(obj, Regions):
        return obj
    if isinstance(obj, Market):
        return obj.region
    if isinstance(obj, Organization):
        return obj.market.region
    if isinstance(obj, Asset):
        return obj.organization.market.region
    if isinstance(obj, Test):
        market = get_market_for_scope_any(obj)
        return market.region
    raise TypeError