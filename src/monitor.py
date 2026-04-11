"""Real-time trade monitor via HTTP polling."""

import asyncio
from typing import Any, Callable, Optional

from src.api.polygon import PolygonClient
from src.core.abi import ORDER_FILLED_TOPIC
from src.core.block_processor import POLYMARKET_CONTRACTS
from src.core.decoder import TransactionDecoder
from src.core.log_processor import LogProcessor
from src.core.wallet_filter import WalletFilter
from src.utils.logging import get_logger

log = get_logger(__name__)


class TradeMonitor:
    """Polls for Polymarket trades using eth_getLogs on a fixed interval.

    Each poll fetches all Polymarket log events since the last poll in a
    single eth_getLogs call, then fetches only the transactions that actually
    match. No WebSocket required — pure HTTP polling.
    """

    def __init__(self, wss_url: Optional[str] = None, block_delay: float = 1.0) -> None:
        self.client = PolygonClient(wss_url) if wss_url else PolygonClient()
        self.decoder = TransactionDecoder()
        self.block_delay = block_delay
        self._callbacks: dict[str, list[Callable]] = {
            "transaction": [],
            "error": [],
            "close": [],
        }
        self._running = False

    def on(self, event: str, callback: Callable) -> None:
        """Register event callback."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def emit(self, event: str, data: Any) -> None:
        """Emit event to all registered callbacks."""
        for callback in self._callbacks.get(event, []):
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(data))
            else:
                callback(data)

    async def start(self, target_wallets: list[str]) -> None:
        """Start polling for trades from target wallets."""
        self._running = True
        wallet_count = len(target_wallets) if target_wallets else 0
        log.info("Starting monitor", wallet_count=wallet_count, poll_interval=self.block_delay)

        wallet_filter = WalletFilter(target_wallets)
        processor = LogProcessor(self.client, self.decoder, wallet_filter)
        contracts = list(POLYMARKET_CONTRACTS)

        if wallet_filter.is_tracking_all:
            log.info("Tracking ALL Polymarket trades")
            # Filter by event type only — avoids fetching txs for non-OrderFilled events
            topics_filter = [ORDER_FILLED_TOPIC]
        else:
            log.info("Tracking specific wallets", count=wallet_count)
            # Pad wallet addresses to 32-byte Ethereum topic format
            padded = ["0x" + "0" * 24 + w[2:] for w in target_wallets]
            maker_filter = padded if len(padded) > 1 else padded[0]
            # topics: [event_sig, any_orderHash, maker_address]
            topics_filter = [ORDER_FILLED_TOPIC, None, maker_filter]

        log.info("Topic filter active", event=ORDER_FILLED_TOPIC[:10] + "...")

        # Alchemy free tier allows up to 10 blocks per eth_getLogs call
        MAX_BLOCK_RANGE = 10

        # Seed with current block so we don't replay old history on startup
        last_block = await self.client.get_current_block()
        log.info("Starting from block", block=last_block)

        while self._running:
            await asyncio.sleep(self.block_delay)

            try:
                current_block = await self.client.get_current_block()

                if current_block <= last_block:
                    continue  # No new blocks yet

                # Cap range to avoid Alchemy free tier limit (10 blocks per call).
                # If we've fallen behind, we'll catch up over multiple iterations.
                to_block = min(current_block, last_block + MAX_BLOCK_RANGE)

                logs = await self.client.get_logs(
                    from_block=last_block + 1,
                    to_block=to_block,
                    addresses=contracts,
                    topics=topics_filter,
                )
                last_block = to_block

                if not logs:
                    continue

                log.debug(
                    "Poll found logs",
                    blocks=f"{last_block + 1}-{current_block}",
                    logs=len(logs),
                )

                # Deduplicate by tx hash — one matchOrders tx emits multiple logs
                seen: set[str] = set()
                for log_entry in logs:
                    tx_hash = log_entry.get("transactionHash")
                    if not tx_hash or tx_hash in seen:
                        continue
                    seen.add(tx_hash)

                    trade = await processor.process_log(log_entry)
                    if trade:
                        self.emit("transaction", trade)

            except Exception as e:
                log.error("Poll error", error=str(e))
                self.emit("error", e)

        self.emit("close", {"code": 0, "reason": "stopped"})

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        await self.client.disconnect()
        log.info("Monitor stopped")
