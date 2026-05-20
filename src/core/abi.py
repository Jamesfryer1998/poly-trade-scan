"""Polymarket ABI definitions for transaction decoding."""
from eth_utils import keccak

# V2 Order struct: (salt, maker, signer, tokenId, makerAmount, takerAmount,
#                   side, signatureType, timestamp, metadata, builder, signature)
# Removed vs V1: taker (address), expiration (uint256), nonce (uint256), feeRateBps (uint256)
# Added vs V1:   timestamp (uint256, ms), metadata (bytes32), builder (bytes32)
# Field ordering changed vs V1: side/signatureType now before timestamp/metadata/builder
ORDER_TUPLE_TYPE = "(uint256,address,address,uint256,uint256,uint256,uint8,uint8,uint256,bytes32,bytes32,bytes)"

# matchOrders selector - from 4byte.directory for V2 contract (verified against live txs)
# Full sig: matchOrders(bytes32,(Order),(Order)[],uint256,uint256[],uint256,uint256[])
MATCH_ORDERS_SELECTOR = bytes.fromhex("3c2b4399")

# ABI types for matchOrders V2:
# (bytes32 conditionId, takerOrder, makerOrders[], takerFillAmount, makerFillAmounts[], uint256, uint256[])
MATCH_ORDERS_ABI_TYPES = [
    "bytes32",                  # conditionId / market ID
    ORDER_TUPLE_TYPE,           # takerOrder
    f"{ORDER_TUPLE_TYPE}[]",    # makerOrders array
    "uint256",                  # takerFillAmount
    "uint256[]",                # makerFillAmounts
    "uint256",                  # extra param
    "uint256[]",                # extra array
]

# Legacy aliases (both contracts use same selector)
CTF_MATCH_ORDERS_SELECTOR = MATCH_ORDERS_SELECTOR
NEGRISK_MATCH_ORDERS_SELECTOR = MATCH_ORDERS_SELECTOR

# OrderFilled event topic (keccak256 of event signature)
# V2: event OrderFilled(bytes32 indexed orderHash, address indexed maker, address indexed taker,
#                       uint8 side, uint256 makerAssetId, uint256 takerAssetId,
#                       uint256 makerAmountFilled, uint256 takerAmountFilled,
#                       bytes32 metadata, bytes32 builder)
ORDER_FILLED_TOPIC = "0x" + keccak(
    text="OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)"
).hex()
