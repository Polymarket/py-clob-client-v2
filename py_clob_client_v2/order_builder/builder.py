import time
from typing import Union

from .helpers import (
    to_token_decimals,
    round_down,
    round_normal,
    round_up,
    decimal_places,
)
from .constants import BUY, SELL
from ..config import get_contract_config
from ..constants import ZERO_ADDRESS, BYTES32_ZERO
from ..signer import Signer
from ..clob_types import (
    OrderArgsV1,
    OrderArgsV2,
    MarketOrderArgsV1,
    MarketOrderArgsV2,
    CreateOrderOptions,
    TickSize,
    RoundConfig,
    OrderSummary,
    OrderType,
)
from ..order_utils import (
    ExchangeOrderBuilderV1,
    ExchangeOrderBuilderV2,
    SignatureTypeV1,
    SignatureTypeV2,
    Side,
)
from ..order_utils.model.order_data_v1 import OrderDataV1, SignedOrderV1
from ..order_utils.model.order_data_v2 import OrderDataV2, SignedOrderV2

ROUNDING_CONFIG: dict = {
    "0.1":    RoundConfig(price=1, size=2, amount=3),
    "0.01":   RoundConfig(price=2, size=2, amount=4),
    "0.001":  RoundConfig(price=3, size=2, amount=5),
    "0.0001": RoundConfig(price=4, size=2, amount=6),
}

class OrderBuilder:
    def __init__(
        self,
        signer: Signer,
        signature_type: SignatureTypeV2 = None,
        funder: str = None,
    ):
        self.signer = signer

        # Signature type used to sign orders, defaults to EOA
        self.signature_type = (
            signature_type if signature_type is not None else SignatureTypeV2.EOA
        )

        # Address which holds funds. Defaults to the signer address.
        # Used for Polymarket proxy wallets and other smart contract wallets.
        self.funder = funder if funder is not None else (self.signer.address() if self.signer else None)

    def _v2_order_signer(self) -> str:
        if self.signature_type == SignatureTypeV2.POLY_1271:
            return self.funder
        return self.signer.address()

    def get_order_amounts(
        self, side, size: float, price: float, round_config: RoundConfig
    ):
        """Returns (Side, maker_amount, taker_amount) for a limit order."""
        if isinstance(side, Side):
            side = BUY if side == Side.BUY else SELL
        raw_price = round_normal(price, round_config.price)

        if side == BUY:
            raw_taker_amt = round_down(size, round_config.size)
            raw_maker_amt = raw_taker_amt * raw_price
            if decimal_places(raw_maker_amt) > round_config.amount:
                raw_maker_amt = round_up(raw_maker_amt, round_config.amount + 4)
                if decimal_places(raw_maker_amt) > round_config.amount:
                    raw_maker_amt = round_down(raw_maker_amt, round_config.amount)

            return Side.BUY, to_token_decimals(raw_maker_amt), to_token_decimals(raw_taker_amt)

        elif side == SELL:
            raw_maker_amt = round_down(size, round_config.size)
            raw_taker_amt = raw_maker_amt * raw_price
            if decimal_places(raw_taker_amt) > round_config.amount:
                raw_taker_amt = round_up(raw_taker_amt, round_config.amount + 4)
                if decimal_places(raw_taker_amt) > round_config.amount:
                    raw_taker_amt = round_down(raw_taker_amt, round_config.amount)

            return Side.SELL, to_token_decimals(raw_maker_amt), to_token_decimals(raw_taker_amt)

        else:
            raise ValueError(f"order_args.side must be '{BUY}' or '{SELL}'")

    def get_market_order_amounts(
        self, side, amount: float, price: float, round_config: RoundConfig
    ):
        """Returns (Side, maker_amount, taker_amount) for a market order."""
        if isinstance(side, Side):
            side = BUY if side == Side.BUY else SELL
        # V2 change: market orders use round_down for price (v1 used round_normal)
        raw_price = round_down(price, round_config.price)

        if side == BUY:
            raw_maker_amt = round_down(amount, round_config.size)
            raw_taker_amt = raw_maker_amt / raw_price
            if decimal_places(raw_taker_amt) > round_config.amount:
                raw_taker_amt = round_up(raw_taker_amt, round_config.amount + 4)
                if decimal_places(raw_taker_amt) > round_config.amount:
                    raw_taker_amt = round_down(raw_taker_amt, round_config.amount)

            return Side.BUY, to_token_decimals(raw_maker_amt), to_token_decimals(raw_taker_amt)

        elif side == SELL:
            raw_maker_amt = round_down(amount, round_config.size)
            raw_taker_amt = raw_maker_amt * raw_price
            if decimal_places(raw_taker_amt) > round_config.amount:
                raw_taker_amt = round_up(raw_taker_amt, round_config.amount + 4)
                if decimal_places(raw_taker_amt) > round_config.amount:
                    raw_taker_amt = round_down(raw_taker_amt, round_config.amount)

            return Side.SELL, to_token_decimals(raw_maker_amt), to_token_decimals(raw_taker_amt)

        else:
            raise ValueError(f"order_args.side must be '{BUY}' or '{SELL}'")

    def build_order(
        self,
        order_args: Union[OrderArgsV1, OrderArgsV2],
        options: CreateOrderOptions,
        version: int = 2,
        fee_rate_bps: int = None,
    ) -> Union[SignedOrderV1, SignedOrderV2]:
        """
        Creates and signs a limit order.
        version=2 (default) uses the V2 exchange contract.
        version=1 uses the V1 exchange contract (legacy).
        """
        round_config = ROUNDING_CONFIG[options.tick_size]
        side, maker_amount, taker_amount = self.get_order_amounts(
            order_args.side,
            order_args.size,
            order_args.price,
            round_config,
        )

        contract_config = get_contract_config(self.signer.get_chain_id())
        ts = str(time.time_ns() // 1_000_000)

        if version == 1:
            if self.signature_type == SignatureTypeV2.POLY_1271:
                raise ValueError("signature type POLY_1271 is not supported for v1 orders")

            exchange_address = (
                contract_config.neg_risk_exchange
                if options.neg_risk
                else contract_config.exchange
            )
            resolved_fee_rate_bps = (
                fee_rate_bps if fee_rate_bps is not None
                else getattr(order_args, "fee_rate_bps", 0)
            )
            order_data = OrderDataV1(
                maker=self.funder,
                taker=getattr(order_args, "taker", ZERO_ADDRESS),
                tokenId=order_args.token_id,
                makerAmount=str(maker_amount),
                takerAmount=str(taker_amount),
                side=side,
                feeRateBps=str(resolved_fee_rate_bps),
                nonce=str(getattr(order_args, "nonce", 0)),
                signer=self.signer.address(),
                expiration=str(order_args.expiration),
                signatureType=SignatureTypeV1(int(self.signature_type)),
            )
            builder = ExchangeOrderBuilderV1(
                exchange_address, self.signer.get_chain_id(), self.signer
            )
            return builder.build_signed_order(order_data)

        elif version == 2:
            exchange_address = (
                contract_config.neg_risk_exchange_v2
                if options.neg_risk
                else contract_config.exchange_v2
            )
            order_data = OrderDataV2(
                maker=self.funder,
                tokenId=order_args.token_id,
                makerAmount=str(maker_amount),
                takerAmount=str(taker_amount),
                side=side,
                signer=self._v2_order_signer(),
                signatureType=self.signature_type,
                timestamp=ts,
                metadata=getattr(order_args, "metadata", BYTES32_ZERO),
                builder=order_args.builder_code,
                expiration=str(getattr(order_args, "expiration", 0)),
            )
            builder = ExchangeOrderBuilderV2(
                exchange_address, self.signer.get_chain_id(), self.signer
            )
            return builder.build_signed_order(order_data)

        else:
            raise ValueError(f"unsupported order version {version}")

    def build_market_order(
        self,
        order_args: Union[MarketOrderArgsV1, MarketOrderArgsV2],
        options: CreateOrderOptions,
        version: int = 2,
        fee_rate_bps: int = None,
    ) -> Union[SignedOrderV1, SignedOrderV2]:
        """
        Creates and signs a market order.
        version=2 (default) uses the V2 exchange contract.
        version=1 uses the V1 exchange contract (legacy).
        """
        round_config = ROUNDING_CONFIG[options.tick_size]
        side, maker_amount, taker_amount = self.get_market_order_amounts(
            order_args.side,
            order_args.amount,
            order_args.price,
            round_config,
        )

        contract_config = get_contract_config(self.signer.get_chain_id())
        ts = str(time.time_ns() // 1_000_000)

        if version == 1:
            if self.signature_type == SignatureTypeV2.POLY_1271:
                raise ValueError("signature type POLY_1271 is not supported for v1 orders")

            exchange_address = (
                contract_config.neg_risk_exchange
                if options.neg_risk
                else contract_config.exchange
            )
            resolved_fee_rate_bps = (
                fee_rate_bps if fee_rate_bps is not None
                else getattr(order_args, "fee_rate_bps", 0)
            )
            order_data = OrderDataV1(
                maker=self.funder,
                taker=getattr(order_args, "taker", ZERO_ADDRESS),
                tokenId=order_args.token_id,
                makerAmount=str(maker_amount),
                takerAmount=str(taker_amount),
                side=side,
                feeRateBps=str(resolved_fee_rate_bps),
                nonce=str(getattr(order_args, "nonce", 0)),
                signer=self.signer.address(),
                expiration="0",
                signatureType=SignatureTypeV1(int(self.signature_type)),
            )
            builder = ExchangeOrderBuilderV1(
                exchange_address, self.signer.get_chain_id(), self.signer
            )
            return builder.build_signed_order(order_data)

        elif version == 2:
            exchange_address = (
                contract_config.neg_risk_exchange_v2
                if options.neg_risk
                else contract_config.exchange_v2
            )
            order_data = OrderDataV2(
                maker=self.funder,
                tokenId=order_args.token_id,
                makerAmount=str(maker_amount),
                takerAmount=str(taker_amount),
                side=side,
                signer=self._v2_order_signer(),
                signatureType=self.signature_type,
                timestamp=ts,
                metadata=getattr(order_args, "metadata", BYTES32_ZERO),
                builder=order_args.builder_code,
            )
            builder = ExchangeOrderBuilderV2(
                exchange_address, self.signer.get_chain_id(), self.signer
            )
            return builder.build_signed_order(order_data)

        else:
            raise ValueError(f"unsupported order version {version}")

    def calculate_buy_market_price(
        self,
        positions: list,
        amount_to_match: float,
        order_type: OrderType,
    ) -> float:
        if not positions:
            raise Exception("no match")

        total = 0
        for p in reversed(positions):
            size = p["size"] if isinstance(p, dict) else p.size
            price = p["price"] if isinstance(p, dict) else p.price
            total += float(size) * float(price)
            if total >= amount_to_match:
                return float(price)

        if order_type == OrderType.FOK:
            raise Exception("no match")

        p0 = positions[0]
        return float(p0["price"] if isinstance(p0, dict) else p0.price)

    def calculate_sell_market_price(
        self,
        positions: list,
        amount_to_match: float,
        order_type: OrderType,
    ) -> float:
        if not positions:
            raise Exception("no match")

        total = 0
        for p in reversed(positions):
            size = p["size"] if isinstance(p, dict) else p.size
            price = p["price"] if isinstance(p, dict) else p.price
            total += float(size)
            if total >= amount_to_match:
                return float(price)

        if order_type == OrderType.FOK:
            raise Exception("no match")

        p0 = positions[0]
        return float(p0["price"] if isinstance(p0, dict) else p0.price)
