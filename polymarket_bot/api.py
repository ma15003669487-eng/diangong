"""HTTP clients for Polymarket public APIs and CLOB trading."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
from eth_account import Account
from eth_account.messages import encode_structured_data

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
        self._last_gas_price: Optional[float] = None

    # ------------ Market data ------------
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

    # ------------ Wallet state ------------
    def fetch_usdc_balance(self, address: str) -> Optional[float]:
        """Fetch USDC balance for an address using the public API."""

        url = f"{self.api_base_url}/balances"
        params = {"address": address}
        LOGGER.debug("Fetching balance for %s", address)
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            return float(payload.get("USDC", 0))
        except requests.RequestException:
            LOGGER.exception("Failed to fetch balances")
            return None

    def fetch_positions(self, address: str) -> List[Dict[str, object]]:
        """Return raw position objects for the address."""

        url = f"{self.api_base_url}/positions"
        params = {"address": address}
        LOGGER.debug("Fetching positions for %s", address)
        response = self.session.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def fetch_settlements(self, address: str) -> List[Dict[str, object]]:
        """Query settlements/resolutions for an address."""

        url = f"{self.api_base_url}/settlements"
        params = {"address": address}
        LOGGER.debug("Fetching settlements for %s", address)
        try:
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []
        except requests.RequestException:
            LOGGER.exception("Failed to fetch settlements")
            return []

    # ------------ Orders ------------
    def build_order_params(
        self,
        market_id: str,
        outcome: str,
        price: float,
        size: float,
        signer: str,
        side: str = "BUY",
        expiration_seconds: int = 120,
    ) -> Dict[str, object]:
        """Ask the CLOB API for typed data to sign for an order."""

        url = f"{self.clob_base_url}/orders/params"
        payload = {
            "market": market_id,
            "side": side,
            "outcome": outcome,
            "price": price,
            "size": size,
            "signer": signer,
            "expiration": expiration_seconds,
        }
        LOGGER.debug("Requesting order params for %s %s %s", market_id, outcome, price)
        response = self.session.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    def submit_order(self, order_payload: Dict[str, object]) -> Dict[str, object]:
        url = f"{self.clob_base_url}/orders"
        LOGGER.debug("Submitting signed order to %s", url)
        response = self.session.post(url, json=order_payload, timeout=20)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def sign_typed_data(typed_data: Dict[str, object], private_key: str) -> str:
        """Sign typed data returned by Polymarket's CLOB using EIP-712."""

        message = encode_structured_data(typed_data=typed_data)
        signed = Account.sign_message(message, private_key=private_key)
        return signed.signature.hex()
