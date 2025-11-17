"""Configuration helpers for the Polymarket arbitrage bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _get_env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class BotSettings:
    """Runtime configuration loaded from environment variables.

    Attributes:
        api_base_url: Base URL for the Polymarket public API.
        clob_base_url: Base URL for the Polymarket CLOB API.
        telegram_token: Token for the Telegram bot (optional if alerts are disabled).
        telegram_chat_id: Chat ID to send alerts to.
        poll_interval: Seconds to wait between market refreshes.
        edge_threshold: Minimum total edge (1 - yes_price - no_price) required to alert.
        trade_amount: Quote amount (in USDC) to deploy per side when auto-trading.
        auto_trade: Whether to place trades automatically after detecting an opportunity.
        wallet_path: Location to persist the generated wallet private key.
        max_slippage: Maximum slippage accepted when placing orders.
        dry_run: Skip order placement while still alerting and logging.
        fee_bps: Taker/maker fee estimate (basis points) used for risk checks.
        gas_fee_cap_gwei: Maximum gas price (in gwei) willing to pay per transaction.
        min_usdc_balance: Minimum available USDC balance required before trading.
    """

    api_base_url: str = "https://gamma-api.polymarket.com"
    clob_base_url: str = "https://clob.polymarket.com"
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    poll_interval: int = 20
    edge_threshold: float = 0.02
    trade_amount: float = 20.0
    auto_trade: bool = False
    wallet_path: str = "wallet.json"
    max_slippage: float = 0.01
    dry_run: bool = True
    fee_bps: float = 35.0
    gas_fee_cap_gwei: float = 80.0
    min_usdc_balance: float = 20.0

    @classmethod
    def from_env(cls) -> "BotSettings":
        return cls(
            api_base_url=os.getenv("POLYMARKET_API_BASE", cls.api_base_url),
            clob_base_url=os.getenv("POLYMARKET_CLOB_BASE", cls.clob_base_url),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            poll_interval=int(os.getenv("POLL_INTERVAL", cls.poll_interval)),
            edge_threshold=float(os.getenv("EDGE_THRESHOLD", cls.edge_threshold)),
            trade_amount=float(os.getenv("TRADE_AMOUNT", cls.trade_amount)),
            auto_trade=_get_env_bool("AUTO_TRADE", cls.auto_trade),
            wallet_path=os.getenv("WALLET_PATH", cls.wallet_path),
            max_slippage=float(os.getenv("MAX_SLIPPAGE", cls.max_slippage)),
            dry_run=_get_env_bool("DRY_RUN", cls.dry_run),
            fee_bps=float(os.getenv("FEE_BPS", cls.fee_bps)),
            gas_fee_cap_gwei=float(os.getenv("GAS_FEE_CAP_GWEI", cls.gas_fee_cap_gwei)),
            min_usdc_balance=float(os.getenv("MIN_USDC_BALANCE", cls.min_usdc_balance)),
        )

    def ensure_alerting_is_configured(self) -> None:
        if self.telegram_token and self.telegram_chat_id:
            return
        raise RuntimeError("Telegram credentials are required for alerting. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    def should_alert(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)
