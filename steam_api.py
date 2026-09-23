"""
Steam Storefront API client and data models.
Handles querying https://store.steampowered.com/api/storesearch/
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import requests

AUTOCOMPLETE_URL = "https://store.steampowered.com/api/storesearch/"
USER_AGENT = "SteamSearchDesktop/1.0 (Windows NT 10.0; Win64; x64)"


@dataclass
class SteamGame:
    id: int
    name: str
    type: str = "app"
    tiny_image: str = ""
    header_image: str = ""
    price_formatted: str = "Free / N/A"
    initial_price: Optional[float] = None
    final_price: Optional[float] = None
    currency: str = "USD"
    metascore: Optional[str] = None
    platforms: Dict[str, bool] = field(default_factory=dict)
    controller_support: Optional[str] = None

    @property
    def store_url(self) -> str:
        return f"https://store.steampowered.com/app/{self.id}/"

    @property
    def steam_client_url(self) -> str:
        return f"steam://store/{self.id}"


def parse_price(price_data: Optional[Dict[str, Any]]) -> str:
    """Format price data from the Steam Storefront API."""
    if not price_data:
        return "Free / N/A"
    
    currency = price_data.get("currency", "USD")
    final_cents = price_data.get("final")
    initial_cents = price_data.get("initial")
    
    if final_cents is None:
        return "Free / N/A"
    
    if final_cents == 0:
        return "Free to Play"
    
    currency_symbol = "$" if currency == "USD" else f"{currency} "
    final_val = f"{currency_symbol}{final_cents / 100:.2f}"
    
    if initial_cents and initial_cents > final_cents:
        discount = int(round((initial_cents - final_cents) / initial_cents * 100))
        initial_val = f"{currency_symbol}{initial_cents / 100:.2f}"
        return f"{final_val} (-{discount}%) [was {initial_val}]"
    
    return final_val


def search_games(query: str, limit: int = 25, country: str = "US", language: str = "english") -> List[SteamGame]:
    """
    Search Steam games using the Steam Storefront Autocomplete / Store Search API.
    
    GET https://store.steampowered.com/api/storesearch/?term={QUERY}&l=english&cc=US
    """
    query = query.strip()
    if not query:
        return []

    params = {
        "term": query,
        "l": language,
        "cc": country,
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    response = requests.get(AUTOCOMPLETE_URL, params=params, headers=headers, timeout=8)
    response.raise_for_status()
    data = response.json()

    items = data.get("items", [])
    results: List[SteamGame] = []

    for item in items[:limit]:
        app_id = item.get("id")
        if not app_id:
            continue

        name = item.get("name", "Unknown Title")
        tiny_image = item.get("tiny_image", "")
        # High quality header image standard URL on Steam CDN
        header_image = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg"
        
        price_info = item.get("price")
        price_formatted = parse_price(price_info)
        
        metascore = item.get("metascore")
        platforms = item.get("platforms", {})
        controller = item.get("controller_support")

        results.append(
            SteamGame(
                id=app_id,
                name=name,
                type=item.get("type", "app"),
                tiny_image=tiny_image,
                header_image=header_image,
                price_formatted=price_formatted,
                metascore=str(metascore) if metascore else None,
                platforms=platforms,
                controller_support=controller,
            )
        )

    return results
