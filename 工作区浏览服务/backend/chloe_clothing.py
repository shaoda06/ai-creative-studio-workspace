"""Clothing API uses the shared reference-asset reader."""
from functools import partial
from backend.chloe_reference_assets import CLOTHING, asset_cards, asset_detail, asset_file, asset_router

clothing_cards = partial(asset_cards, kind=CLOTHING)
clothing_detail = partial(asset_detail, kind=CLOTHING)
clothing_file = partial(asset_file, kind=CLOTHING)
router = asset_router(CLOTHING)
