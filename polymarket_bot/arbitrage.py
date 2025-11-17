"""Arbitrage search logic."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from .api import OrderbookLevel, PolymarketClient

LOGGER = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    market_id: str
    question: str
    yes: OrderbookLevel
    no: OrderbookLevel

    @property
    def edge(self) -> float:
        return 1.0 - (self.yes.price + self.no.price)


def find_opportunities(client: PolymarketClient, edge_threshold: float) -> List[ArbitrageOpportunity]:
    markets = client.fetch_markets()
    opportunities: List[ArbitrageOpportunity] = []
    for market in markets:
        yes_level, no_level = client.fetch_best_prices(market.id)
        if yes_level is None or no_level is None:
            LOGGER.debug("Skipping market %s because of missing depth", market.id)
            continue
        current_edge = 1.0 - (yes_level.price + no_level.price)
        if current_edge >= edge_threshold:
            LOGGER.info(
                "Found edge %.4f on market %s (%s)",
                current_edge,
                market.id,
                market.question,
            )
            opportunities.append(
                ArbitrageOpportunity(
                    market_id=market.id, question=market.question, yes=yes_level, no=no_level
                )
            )
    return opportunities
