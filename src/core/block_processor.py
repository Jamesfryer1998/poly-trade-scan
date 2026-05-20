"""Block processing for trade extraction."""
from datetime import datetime, timezone
from typing import Optional

from src.api.polygon import PolygonClient
from src.core.abi import CTF_MATCH_ORDERS_SELECTOR, NEGRISK_MATCH_ORDERS_SELECTOR
from src.core.decoder import TransactionDecoder
from src.core.models import TradeData
from src.core.wallet_filter import WalletFilter
from src.utils.logging import get_logger

log = get_logger(__name__)

# Known Polymarket contract addresses (V2 — updated April 28, 2026)
POLYMARKET_CONTRACTS = {
    "0xe111180000d2663c0091e4f400237545b87b996b",  # CTF Exchange V2
    "0xe2222d279d744050d28e00520010520000310f59",  # NegRisk CTF Exchange V2
    "0xd91e80cf2e7be2e162c6513ced06f1dd0da35296",  # NegRisk Adapter V2
}


class BlockProcessor:
    """Processes blocks and extracts matching trades."""

    def __init__(
        self,
        client: PolygonClient,
        decoder: TransactionDecoder,
        wallet_filter: WalletFilter,
    ) -> None:
        self.client = client
        self.decoder = decoder
        self.filter = wallet_filter

    async def process_block(self, block_number: int) -> list[TradeData]:
        """Process all transactions in a block."""
        trades = []
        block = await self.client.get_block_with_transactions(block_number)
        receipts = await self.client.get_block_receipts(block_number)

        # Extract block timestamp (hex Unix epoch → ISO 8601)
        block_ts = int(block["timestamp"], 16)
        timestamp = datetime.fromtimestamp(block_ts, tz=timezone.utc).isoformat()

        # Build receipt lookup by tx hash
        receipt_map = {r["transactionHash"]: r for r in receipts}

        log.info("Processing block", block=block_number, txs=len(block["transactions"]))

        # Debug: check for Polymarket transactions
        ctf_selector = "0x" + CTF_MATCH_ORDERS_SELECTOR.hex()
        negrisk_selector = "0x" + NEGRISK_MATCH_ORDERS_SELECTOR.hex()

        for tx in block["transactions"]:
            tx_input = tx.get("input", "")
            tx_to = (tx.get("to") or "").lower()

            # Check if this is a Polymarket contract
            if tx_to in POLYMARKET_CONTRACTS:
                selector = tx_input[:10] if len(tx_input) >= 10 else "none"
                log.info(
                    "Found Polymarket contract tx",
                    to=tx_to[:10],
                    selector=selector,
                    matches_ctf=(selector == ctf_selector),
                    matches_negrisk=(selector == negrisk_selector),
                )

            receipt = receipt_map.get(tx["hash"])
            trade = self._process_transaction(tx, block_number, timestamp, receipt)
            if trade:
                trades.append(trade)

        return trades

    def _process_transaction(
        self, tx: dict, block_number: int, timestamp: str, receipt: Optional[dict]
    ) -> Optional[TradeData]:
        """Process single transaction and return TradeData if matching."""
        orders = self.decoder.decode(tx["input"])
        if not orders:
            return None

        matching_order = self.filter.filter(orders, receipt)
        if not matching_order:
            return None

        return TradeData(
            block_number=block_number,
            timestamp=timestamp,
            transaction_hash=tx["hash"],
            wallet=matching_order.maker,
            token_id=matching_order.token_id,
            side=matching_order.side,
            maker_amount=matching_order.maker_amount,
            taker_amount=matching_order.taker_amount,
        )
