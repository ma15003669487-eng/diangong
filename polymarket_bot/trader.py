"""Wallet management, risk checks, and trade helpers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from eth_account import Account
from eth_account.signers.local import LocalAccount

from .api import PolymarketClient
from .arbitrage import ArbitrageOpportunity

LOGGER = logging.getLogger(__name__)


@dataclass
class TradeResult:
    market_id: str
    yes_order_id: Optional[str]
    no_order_id: Optional[str]
    status: str
    details: str


class PositionLedger:
    """Minimal local ledger for exposure and settlements."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._positions: Dict[str, Dict[str, float]] = self._load()

    def _load(self) -> Dict[str, Dict[str, float]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except json.JSONDecodeError:
            LOGGER.warning("Positions file %s is invalid; resetting", self.path)
            return {}

    def save(self) -> None:
        self.path.write_text(json.dumps(self._positions, indent=2, sort_keys=True))

    def record_trade(self, market_id: str, outcome: str, size: float) -> None:
        market_positions = self._positions.setdefault(market_id, {"YES": 0.0, "NO": 0.0})
        market_positions[outcome] = market_positions.get(outcome, 0.0) + size
        self.save()

    def apply_settlement(self, market_id: str, outcome: str, payout: float) -> None:
        if market_id not in self._positions:
            return
        market_positions = self._positions[market_id]
        market_positions[outcome] = max(0.0, market_positions.get(outcome, 0.0) - payout)
        self.save()

    def positions(self) -> Dict[str, Dict[str, float]]:
        return self._positions


class Trader:
    def __init__(
        self,
        client: PolymarketClient,
        wallet_path: str,
        max_slippage: float = 0.01,
        dry_run: bool = True,
        fee_bps: float = 35.0,
        gas_fee_cap_gwei: float = 80.0,
        min_usdc_balance: float = 20.0,
        positions_path: str = "positions.json",
    ) -> None:
        self.client = client
        self.wallet_path = Path(wallet_path)
        self.max_slippage = max_slippage
        self.dry_run = dry_run
        self.fee_bps = fee_bps
        self.gas_fee_cap_gwei = gas_fee_cap_gwei
        self.min_usdc_balance = min_usdc_balance
        self.account = self._load_or_create_wallet()
        self.ledger = PositionLedger(Path(positions_path))

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

        self._ensure_risk_limits(trade_amount)

        yes_order_id = self._submit_order(opportunity.market_id, "YES", opportunity.yes.price, trade_amount)
        no_order_id = self._submit_order(opportunity.market_id, "NO", opportunity.no.price, trade_amount)

        self.ledger.record_trade(opportunity.market_id, "YES", trade_amount)
        self.ledger.record_trade(opportunity.market_id, "NO", trade_amount)

        return TradeResult(
            market_id=opportunity.market_id,
            yes_order_id=yes_order_id,
            no_order_id=no_order_id,
            status="submitted",
            details="Orders submitted to the CLOB",
        )

    def _ensure_risk_limits(self, trade_amount: float) -> None:
        expected_fees = trade_amount * 2 * (self.fee_bps / 10_000)
        expected_cost = trade_amount * 2 + expected_fees
        balance = self.client.fetch_usdc_balance(self.account.address)
        if balance is not None and balance < max(self.min_usdc_balance, expected_cost):
            raise RuntimeError(
                f"Insufficient USDC balance ({balance}) for trade (requires >= {expected_cost:.2f})."
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

        payload = self.client.build_order_params(
            market_id=market_id,
            outcome=outcome,
            price=self._apply_slippage(price, outcome),
            size=amount,
            signer=self.account.address,
        )
        typed_data = payload.get("typedData") or payload.get("typed_data") or payload
        signature = self.client.sign_typed_data(typed_data, private_key=self.account.key)
        order_body = payload.get("order") or payload
        order_body["signature"] = signature
        response = self.client.submit_order(order_body)
        order_id = str(response.get("id") or response.get("orderId") or response.get("order_id") or "")
        if not order_id:
            LOGGER.warning("Order response missing id: %s", response)
            order_id = f"{market_id}-{outcome}-pending"
        return order_id

    def refresh_settlements(self) -> None:
        settlements = self.client.fetch_settlements(self.account.address)
        for settlement in settlements:
            market_id = str(settlement.get("marketId") or settlement.get("market_id"))
            outcome = str(settlement.get("outcome", "")).upper() or "YES"
            payout = float(settlement.get("payout", 0))
            self.ledger.apply_settlement(market_id, outcome, payout)

    @staticmethod
    def _apply_slippage(price: float, outcome: str) -> float:
        # Favor aggressive prices to improve fill probability while staying inside bounds.
        if outcome.upper() == "YES":
            return round(price * 1.0001, 5)
        return round(price * 0.9999, 5)
