"""Transaction decoder for Polymarket orders."""
from typing import Optional

from eth_abi import decode

from src.core.abi import MATCH_ORDERS_ABI_TYPES, MATCH_ORDERS_SELECTOR
from src.core.models import DecodedOrder
from src.utils.logging import get_logger

log = get_logger(__name__)


class TransactionDecoder:
    """Decodes Polymarket transactions using ABI decoding."""

    def __init__(self) -> None:
        log.info("Decoder initialized", selector=MATCH_ORDERS_SELECTOR.hex())

    def decode(self, tx_input: str) -> Optional[list[DecodedOrder]]:
        """Decode transaction input data.

        Returns None if not a Polymarket matchOrders transaction.
        Supports both Fee Module and NegRisk Fee Module 2 contracts.
        """
        try:
            input_bytes = bytes.fromhex(
                tx_input[2:] if tx_input.startswith("0x") else tx_input
            )

            if len(input_bytes) < 4:
                return None

            # Check function selector (first 4 bytes)
            selector = input_bytes[:4]

            # Both Fee Module and NegRisk Fee Module 2 use the same selector
            if selector != MATCH_ORDERS_SELECTOR:
                return None

            decoded = decode(MATCH_ORDERS_ABI_TYPES, input_bytes[4:])

            return self._extract_orders(decoded)
        except Exception:
            # Expected for non-Polymarket transactions with same selector
            return None

    def _extract_orders(self, decoded: tuple) -> list[DecodedOrder]:
        """Extract all orders from decoded parameters."""
        orders = []

        # decoded[0] = bytes32 conditionId, decoded[1] = takerOrder, decoded[2] = makerOrders array
        taker_order = decoded[1]
        maker_orders = decoded[2]

        orders.append(self._parse_order(taker_order))
        for order in maker_orders:
            orders.append(self._parse_order(order))

        return orders

    def _parse_order(self, order_tuple: tuple) -> DecodedOrder:
        """Parse order tuple into DecodedOrder dataclass (V2 struct indices)."""
        # V2 indices: 0=salt, 1=maker, 2=signer, 3=tokenId, 4=makerAmount,
        #             5=takerAmount, 6=side, 7=signatureType, 8=timestamp,
        #             9=metadata, 10=builder, 11=signature
        return DecodedOrder(
            salt=order_tuple[0],
            maker=order_tuple[1],
            signer=order_tuple[2],
            token_id=str(order_tuple[3]),
            maker_amount=order_tuple[4],
            taker_amount=order_tuple[5],
            side=order_tuple[6],
            signature_type=order_tuple[7],
            timestamp=order_tuple[8],
            metadata=order_tuple[9],
            builder=order_tuple[10],
            signature=order_tuple[11],
        )
