"""Telegram alert sender."""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from .arbitrage import ArbitrageOpportunity

LOGGER = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._last_update_id: Optional[int] = None

    def send_opportunity(self, opportunity: ArbitrageOpportunity, auto_trade: bool) -> Optional[dict]:
        message = self._format_message(opportunity, auto_trade)
        LOGGER.info("Sending Telegram alert for %s", opportunity.market_id)
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        return self._post("sendMessage", payload)

    def send_opportunity_with_keyboard(self, opportunity: ArbitrageOpportunity) -> Optional[int]:
        payload = {
            "chat_id": self.chat_id,
            "text": self._format_message(opportunity, auto_trade=False),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "✅ 确认下单", "callback_data": f"confirm:{opportunity.market_id}"},
                        {"text": "❌ 放弃", "callback_data": f"reject:{opportunity.market_id}"},
                    ]
                ]
            },
        }
        response = self._post("sendMessage", payload)
        if response and "result" in response and "message_id" in response["result"]:
            return int(response["result"]["message_id"])
        return None

    def send_execution_result(self, message: str) -> Optional[dict]:
        LOGGER.info("Sending execution result to Telegram")
        return self._post("sendMessage", {"chat_id": self.chat_id, "text": message})

    def await_decision(self, market_id: str, timeout: int = 90) -> Optional[bool]:
        """Block until the inline keyboard is answered or timeout reached."""

        deadline = time.time() + timeout
        while time.time() < deadline:
            updates = self._fetch_updates()
            for update in updates:
                callback = update.get("callback_query")
                if not callback:
                    continue
                data = str(callback.get("data"))
                if not data.endswith(market_id):
                    continue
                update_id = int(update.get("update_id", self._last_update_id or 0))
                self._last_update_id = update_id + 1
                if data.startswith("confirm"):
                    self._answer_callback(callback.get("id"), "已确认，下单中…")
                    return True
                if data.startswith("reject"):
                    self._answer_callback(callback.get("id"), "已拒绝信号")
                    return False
            time.sleep(2)
        return None

    def _post(self, method: str, payload: dict) -> Optional[dict]:
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            LOGGER.exception("Failed to send Telegram message")
            return None

    def _fetch_updates(self) -> list:
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {"timeout": 5}
        if self._last_update_id:
            params["offset"] = self._last_update_id
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            return payload.get("result", []) if isinstance(payload, dict) else []
        except requests.RequestException:
            LOGGER.exception("Failed to poll Telegram updates")
            return []

    def _answer_callback(self, callback_id: Optional[str], text: str) -> None:
        if not callback_id:
            return
        payload = {"callback_query_id": callback_id, "text": text, "show_alert": False}
        self._post("answerCallbackQuery", payload)

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
