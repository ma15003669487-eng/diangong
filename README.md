# Polymarket 套利 Bot

一个简单的命令行应用，用来扫描 Polymarket 市场中 `YES + NO < 1` 的套利机会，并通过 Telegram 提醒，可选择手动确认或自动下单。示例代码包含钱包生成、行情拉取、套利筛选、Telegram 推送以及下单占位逻辑。

## 功能
- 周期性抓取市场与盘口，筛选 `YES + NO` 价格和低于 1 的机会。
- Telegram 推送套利信号，支持自动交易或手动确认后交易。
- 本地生成/加载以太坊钱包（`wallet.json`），可扩展至真实签名与下单。
- `dry_run` 模式便于测试，无需发送真实交易。

## 运行
1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 设置环境变量（示例）：
   ```bash
   export TELEGRAM_BOT_TOKEN="<your_bot_token>"
   export TELEGRAM_CHAT_ID="<chat_id>"
   export EDGE_THRESHOLD=0.02   # 至少 2% 边
   export TRADE_AMOUNT=20        # 每边部署的 USDC 数量
   export AUTO_TRADE=false       # true 则自动下单
   export DRY_RUN=true           # false 时会调用下单函数
   ```

3. 运行扫描器：
   ```bash
   python main.py
   ```
   手动模式下，终端会询问是否下单；自动模式会直接调用交易逻辑。

## 主要文件
- `main.py`：应用入口，负责循环扫描、提醒与触发交易。
- `polymarket_bot/config.py`：环境配置读取与校验。
- `polymarket_bot/api.py`：Polymarket 公共/盘口 API 客户端。
- `polymarket_bot/arbitrage.py`：套利机会筛选逻辑。
- `polymarket_bot/trader.py`：钱包生成、下单占位逻辑（可扩展为真实执行）。
- `polymarket_bot/telegram_client.py`：Telegram 推送封装。

## 进一步扩展
- 接入 Polymarket 官方签名与 CLOB 下单接口，将占位方法替换为真实交易。
- 在 Telegram 端实现 inline keyboard，实现聊天内确认/拒绝。
- 新增风险参数（手续费、Gas、余额检查）以及持仓与结算跟踪。
