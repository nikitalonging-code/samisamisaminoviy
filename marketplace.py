from dataclasses import dataclass
import os

@dataclass
class Listing:
    listing_id: str
    gift_name: str
    price: float
    currency: str

class PortalsAdapter:
    """Thin seam for the marketplace integration.

    Keep all marketplace-specific logic here. Do not put marketplace credentials in the Mini App.
    """
    def __init__(self):
        self.enabled = os.getenv('PORTALS_ENABLED', 'false').lower() == 'true'
        self.base_url = os.getenv('PORTALS_API_BASE', '')
        self.token = os.getenv('PORTALS_API_TOKEN', '')

    async def find_listing(self, gift_name: str, max_price: float | None = None) -> Listing | None:
        if not self.enabled:
            raise RuntimeError('Portals adapter is disabled')
        raise NotImplementedError('Connect this method to the currently supported Portals API/SDK.')

    async def buy(self, listing_id: str) -> str:
        if not self.enabled:
            raise RuntimeError('Portals adapter is disabled')
        raise NotImplementedError('Connect this method to the currently supported Portals API/SDK.')
