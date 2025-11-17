"""Telegram alert sender."""

from __future__ import annotations

import logging
from typing import Optional

import requests

from .arbitrage import ArbitrageOpportunity

LOGGER = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send_opportunity(self, opportunity: ArbitrageOpportunity, auto_trade: bool) -> Optional[dict]:
        message = self._format_message(opportunity, auto_trade)
        LOGGER.info("Sending Telegram alert for %s", opportunity.market_id)
        return self._post("sendMessage", {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"})

    def send_execution_result(self, message: str) -> Optional[dict]:
        LOGGER.info("Sending execution result to Telegram")
        return self._post("sendMessage", {"chat_id": self.chat_id, "text": message})

    def _post(self, method: str, payload: dict) -> Optional[dict]:
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            LOGGER.exception("Failed to send Telegram message")
            return None

    @staticmethod
    def _format_message(opportunity: ArbitrageOpportunity, auto_trade: bool) -> str:
        edge = opportunity.edge * 100
        return (
            f"<b>Polymarket 套利信号</b>\n"
            f"问题: {opportunity.question}\n"
            f"市场: {opportunity.market_id}\n"
            f"YES 最优卖价: {opportunity.yes.price:.4f} (size {opportunity.yes.size:.2f})\n"
            f"NO 最优卖价: {opportunity.no.price:.4f} (size {opportunity.no.size:.2f})\n"
            f"总和: {(opportunity.yes.price + opportunity.no.price):.4f}\n"
            f"净边: {edge:.2f}%\n"
            f"模式: {'自动下单' if auto_trade else '手动确认'}"
        )
