"""Data models for trade monitoring."""
from dataclasses import dataclass


@dataclass
class DecodedOrder:
    """Represents a decoded order from the blockchain transaction (V2 struct).

    V2 changes vs V1: removed taker, expiration, nonce, fee_rate_bps;
    added timestamp (ms), metadata (bytes32), builder (bytes32).
    """

    salt: int
    maker: str
    signer: str
    token_id: str
    maker_amount: int
    taker_amount: int
    timestamp: int   # ms epoch (uniqueness replaces nonce)
    metadata: bytes  # bytes32
    builder: bytes   # bytes32 builder attribution code
    side: int        # 0 = BUY, 1 = SELL
    signature_type: int
    signature: bytes


@dataclass
class TradeData:
    """Trade data emitted when a matching transaction is found."""

    block_number: int
    timestamp: str  # ISO 8601 UTC timestamp from block
    transaction_hash: str
    wallet: str  # The wallet address that made the trade
    token_id: str
    side: int  # 0 = BUY, 1 = SELL
    maker_amount: int
    taker_amount: int
