"""HTTP client for Polymarket public APIs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

LOGGER = logging.getLogger(__name__)


@dataclass
class Market:
    id: str
    question: str
    slug: str
    volume: float
    end_date: str


@dataclass
class OrderbookLevel:
    price: float
    size: float
    outcome: str


class PolymarketClient:
    def __init__(self, api_base_url: str, clob_base_url: str, session: Optional[requests.Session] = None) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.clob_base_url = clob_base_url.rstrip("/")
        self.session = session or requests.Session()

    def fetch_markets(self, limit: int = 100) -> List[Market]:
        url = f"{self.api_base_url}/markets"
        params: Dict[str, object] = {"limit": limit}
        LOGGER.debug("Fetching markets from %s", url)
        response = self.session.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        markets: List[Market] = []
        for entry in payload:
            markets.append(
                Market(
                    id=entry.get("id") or entry.get("marketMakerAddress"),
                    question=entry.get("question", ""),
                    slug=entry.get("slug", ""),
                    volume=float(entry.get("volume", 0)),
                    end_date=entry.get("endDate", ""),
                )
            )
        return markets

    def fetch_best_prices(self, market_id: str) -> Tuple[Optional[OrderbookLevel], Optional[OrderbookLevel]]:
        """Return best ask for YES and NO outcomes."""

        url = f"{self.clob_base_url}/orderbook"
        params = {"market": market_id, "limit": 1}
        LOGGER.debug("Fetching orderbook for market %s", market_id)
        response = self.session.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        asks: List[Dict[str, object]] = payload.get("asks", []) if isinstance(payload, dict) else []
        best_yes = self._extract_best(asks, target_outcome="YES")
        best_no = self._extract_best(asks, target_outcome="NO")
        return best_yes, best_no

    @staticmethod
    def _extract_best(orders: List[Dict[str, object]], target_outcome: str) -> Optional[OrderbookLevel]:
        filtered = [order for order in orders if str(order.get("outcome")) == target_outcome]
        if not filtered:
            return None
        best = min(filtered, key=lambda o: float(o.get("price", 0)))
        return OrderbookLevel(
            price=float(best.get("price", 0)),
            size=float(best.get("size", 0)),
            outcome=target_outcome,
        )
