"""Wallet management and trade helpers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from eth_account import Account
from eth_account.signers.local import LocalAccount

from .arbitrage import ArbitrageOpportunity

LOGGER = logging.getLogger(__name__)


@dataclass
class TradeResult:
    market_id: str
    yes_order_id: Optional[str]
    no_order_id: Optional[str]
    status: str
    details: str


class Trader:
    def __init__(self, wallet_path: str, max_slippage: float = 0.01, dry_run: bool = True) -> None:
        self.wallet_path = Path(wallet_path)
        self.max_slippage = max_slippage
        self.dry_run = dry_run
        self.account = self._load_or_create_wallet()

    def _load_or_create_wallet(self) -> LocalAccount:
        if self.wallet_path.exists():
            data = json.loads(self.wallet_path.read_text())
            LOGGER.info("Loading existing wallet from %s", self.wallet_path)
            return Account.from_key(data["private_key"])
        LOGGER.info("Creating new wallet and storing it at %s", self.wallet_path)
        account: LocalAccount = Account.create()
        self.wallet_path.write_text(json.dumps({"address": account.address, "private_key": account.key.hex()}))
        return account

    def execute_arbitrage(self, opportunity: ArbitrageOpportunity, trade_amount: float) -> TradeResult:
        LOGGER.info(
            "Executing arbitrage on %s (edge %.4f) with %s USDC per side",
            opportunity.market_id,
            opportunity.edge,
            trade_amount,
        )
        if self.dry_run:
            return TradeResult(
                market_id=opportunity.market_id,
                yes_order_id=None,
                no_order_id=None,
                status="dry-run",
                details="Dry-run enabled; no on-chain orders placed.",
            )
        # Placeholder for real order submission logic.
        yes_order_id = self._submit_order(opportunity.market_id, "YES", opportunity.yes.price, trade_amount)
        no_order_id = self._submit_order(opportunity.market_id, "NO", opportunity.no.price, trade_amount)
        return TradeResult(
            market_id=opportunity.market_id,
            yes_order_id=yes_order_id,
            no_order_id=no_order_id,
            status="submitted",
            details="Orders submitted to the CLOB",
        )

    def _submit_order(self, market_id: str, outcome: str, price: float, amount: float) -> str:
        LOGGER.debug(
            "Submitting %s order to %s at price %.4f for amount %.2f (max slippage %.4f)",
            outcome,
            market_id,
            price,
            amount,
            self.max_slippage,
        )
        # Integration with Polymarket's CLOB signer should be added here.
        # Returning a pseudo order ID for now to make downstream logging clearer.
        return f"{market_id}-{outcome}-pseudo-order"
