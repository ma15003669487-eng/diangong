"""CLI entrypoint for the Polymarket arbitrage bot."""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional

from polymarket_bot.api import PolymarketClient
from polymarket_bot.arbitrage import ArbitrageOpportunity, find_opportunities
from polymarket_bot.config import BotSettings
from polymarket_bot.telegram_client import TelegramNotifier
from polymarket_bot.trader import Trader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)


def _confirm(opportunity: ArbitrageOpportunity) -> bool:
    try:
        answer = input(
            f"发现套利机会（edge {opportunity.edge:.4f}）。是否下单? [y/N]: "
        ).strip()
        return answer.lower() in {"y", "yes"}
    except EOFError:
        return False


def main() -> int:
    settings = BotSettings.from_env()
    client = PolymarketClient(api_base_url=settings.api_base_url, clob_base_url=settings.clob_base_url)
    trader = Trader(
        client=client,
        wallet_path=settings.wallet_path,
        max_slippage=settings.max_slippage,
        dry_run=settings.dry_run,
        fee_bps=settings.fee_bps,
        gas_fee_cap_gwei=settings.gas_fee_cap_gwei,
        min_usdc_balance=settings.min_usdc_balance,
    )
    notifier: Optional[TelegramNotifier] = None
    if settings.should_alert():
        notifier = TelegramNotifier(settings.telegram_token, settings.telegram_chat_id)  # type: ignore[arg-type]

    LOGGER.info("Starting Polymarket arbitrage scanner (auto_trade=%s, dry_run=%s)", settings.auto_trade, settings.dry_run)
    while True:
        try:
            opportunities = find_opportunities(client, edge_threshold=settings.edge_threshold)
            for opp in opportunities:
                decision: Optional[bool] = None
                if settings.auto_trade:
                    decision = True
                    if notifier:
                        notifier.send_opportunity(opp, auto_trade=True)
                elif notifier:
                    notifier.send_opportunity_with_keyboard(opp)
                    decision = notifier.await_decision(opp.market_id)
                    if decision is None:
                        LOGGER.info("Inline keyboard timed out; falling back to CLI prompt")
                        decision = _confirm(opp)
                else:
                    decision = _confirm(opp)

                if decision:
                    result = trader.execute_arbitrage(opp, trade_amount=settings.trade_amount)
                    if notifier:
                        notifier.send_execution_result(
                            f"市场 {opp.market_id} 下单完成: 状态={result.status}, 详情={result.details}"
                        )
            trader.refresh_settlements()
            time.sleep(settings.poll_interval)
        except KeyboardInterrupt:
            LOGGER.info("Shutting down scanner")
            return 0
        except Exception:  # pragma: no cover - top-level guard
            LOGGER.exception("Scan loop failed; retrying after a pause")
            time.sleep(settings.poll_interval)
            continue


if __name__ == "__main__":
    sys.exit(main())
