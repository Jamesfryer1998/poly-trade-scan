"""Log-based trade processor — event-driven alternative to block polling."""
from datetime import datetime, timezone
from typing import Optional

from src.api.polygon import PolygonClient
from src.core.decoder import TransactionDecoder
from src.core.models import TradeData
from src.core.wallet_filter import WalletFilter
from src.utils.logging import get_logger

log = get_logger(__name__)


class LogProcessor:
    """Processes individual log events into trades.

    Unlike BlockProcessor (which fetches every block + all receipts),
    LogProcessor only runs when a Polymarket contract emits a log — i.e.,
    only when an actual trade happens. Logs from successful transactions
    only, so no receipt status check is needed.
    """

    BLOCK_CACHE_MAX_SIZE = 128  # ~4 minutes of Polygon blocks

    def __init__(
        self,
        client: PolygonClient,
        decoder: TransactionDecoder,
        wallet_filter: WalletFilter,
    ) -> None:
        self.client = client
        self.decoder = decoder
        self.filter = wallet_filter
        self._block_header_cache: dict[int, dict] = {}

    async def process_log(self, log_entry: dict) -> Optional[TradeData]:
        """Process a single log event and return a TradeData if it matches."""
        tx_hash = log_entry["transactionHash"]
        block_number = int(log_entry["blockNumber"], 16)

        tx = await self.client.get_transaction(tx_hash)
        if not tx:
            log.warning("Transaction not found", tx=tx_hash)
            return None

        orders = self.decoder.decode(tx["input"])
        if not orders:
            return None

        # Logs are only emitted for successful transactions — no receipt needed
        matching_order = self.filter.filter_without_receipt(orders)
        if not matching_order:
            return None

        header = await self._get_block_header(block_number)
        ts = int(header["timestamp"], 16)
        timestamp = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        return TradeData(
            block_number=block_number,
            timestamp=timestamp,
            transaction_hash=tx_hash,
            wallet=matching_order.maker,
            token_id=matching_order.token_id,
            side=matching_order.side,
            maker_amount=matching_order.maker_amount,
            taker_amount=matching_order.taker_amount,
        )

    async def _get_block_header(self, block_number: int) -> dict:
        """Fetch block header, using cache to avoid redundant RPC calls."""
        if block_number not in self._block_header_cache:
            if len(self._block_header_cache) >= self.BLOCK_CACHE_MAX_SIZE:
                # Evict oldest block
                del self._block_header_cache[min(self._block_header_cache)]
            self._block_header_cache[block_number] = await self.client.get_block_header(
                block_number
            )
        return self._block_header_cache[block_number]
