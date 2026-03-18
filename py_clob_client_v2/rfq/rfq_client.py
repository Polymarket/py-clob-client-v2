"""
RFQ (Request for Quote) client for the Polymarket CLOB API.

This module provides the RfqClient class which handles all RFQ operations
including creating requests, quotes, and executing trades.
"""

import logging
import json
from urllib.parse import urlencode
from typing import Optional, TYPE_CHECKING

from ..clob_types import (
    OrderArgsV1,
    CreateOrderOptions,
    PartialCreateOrderOptions,
    RequestArgs,
)
from ..headers.headers import create_level_2_headers
from ..http_helpers.helpers import get, post, delete
from ..order_builder.builder import ROUNDING_CONFIG
from ..order_builder.helpers import round_normal, round_down
from ..order_builder.constants import BUY, SELL
from ..endpoints import (
    CREATE_RFQ_REQUEST,
    CANCEL_RFQ_REQUEST,
    GET_RFQ_REQUESTS,
    CREATE_RFQ_QUOTE,
    CANCEL_RFQ_QUOTE,
    GET_RFQ_REQUESTER_QUOTES,
    GET_RFQ_QUOTER_QUOTES,
    GET_RFQ_BEST_QUOTE,
    RFQ_REQUESTS_ACCEPT,
    RFQ_QUOTE_APPROVE,
    RFQ_CONFIG,
)

from .rfq_types import (
    RfqUserRequest,
    RfqUserQuote,
    CancelRfqRequestParams,
    CancelRfqQuoteParams,
    AcceptQuoteParams,
    ApproveOrderParams,
    GetRfqRequestsParams,
    GetRfqQuotesParams,
    GetRfqBestQuoteParams,
    MatchType,
)
from .rfq_helpers import (
    parse_units,
    parse_rfq_requests_params,
    parse_rfq_quotes_params,
    COLLATERAL_TOKEN_DECIMALS,
)

if TYPE_CHECKING:
    from ..client import ClobClient


class RfqClient:
    """
    RFQ client for creating and managing RFQ requests and quotes.

    This client is typically accessed via the parent ClobClient's `rfq` attribute:

        client = ClobClient(host, chain_id, key, creds)
        response = client.rfq.create_rfq_request(user_request)
    """

    def __init__(self, parent: "ClobClient"):
        self._parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)

    def _ensure_l2_auth(self) -> None:
        self._parent.assert_level_2_auth()

    def _get_l2_headers(self, method: str, endpoint: str, body=None, serialized_body=None) -> dict:
        request_args = RequestArgs(method=method, request_path=endpoint, body=body)
        if serialized_body is not None:
            request_args.serialized_body = serialized_body
        return create_level_2_headers(
            self._parent.signer,
            self._parent.creds,
            request_args,
            timestamp=self._parent._get_timestamp(),
        )

    def _build_url(self, endpoint: str) -> str:
        return f"{self._parent.host}{endpoint}"

    # =========================================================================
    # Request-side methods
    # =========================================================================

    def create_rfq_request(
        self,
        user_request: RfqUserRequest,
        options: Optional[PartialCreateOrderOptions] = None,
    ) -> dict:
        """
        Create and post an RFQ request from a user request.
        """
        token_id = user_request.token_id
        price = user_request.price
        side = user_request.side
        size = user_request.size

        tick_size = self._parent._ClobClient__resolve_tick_size(
            token_id,
            options.tick_size if options else None,
        )

        tick_size_str = str(tick_size) if not isinstance(tick_size, str) else tick_size
        round_config = ROUNDING_CONFIG[tick_size_str]

        rounded_price = round_normal(price, round_config.price)
        rounded_size = round_down(size, round_config.size)

        price_decimals = int(round_config.price)
        size_decimals = int(round_config.size)
        amount_decimals = int(round_config.amount)

        rounded_price_str = f"{rounded_price:.{price_decimals}f}"
        rounded_size_str = f"{rounded_size:.{size_decimals}f}"

        size_num = float(rounded_size_str)
        price_num = float(rounded_price_str)

        # signature_type value (int) used as userType
        user_type = int(self._parent.builder.signature_type)

        if side == BUY:
            amount_in = parse_units(rounded_size_str, COLLATERAL_TOKEN_DECIMALS)
            usdc_amount_str = f"{size_num * price_num:.{amount_decimals}f}"
            amount_out = parse_units(usdc_amount_str, COLLATERAL_TOKEN_DECIMALS)
            asset_in = token_id
            asset_out = "0"  # USDC
        else:
            usdc_amount_str = f"{size_num * price_num:.{amount_decimals}f}"
            amount_in = parse_units(usdc_amount_str, COLLATERAL_TOKEN_DECIMALS)
            amount_out = parse_units(rounded_size_str, COLLATERAL_TOKEN_DECIMALS)
            asset_in = "0"  # USDC
            asset_out = token_id

        self._ensure_l2_auth()

        body = {
            "assetIn": asset_in,
            "assetOut": asset_out,
            "amountIn": str(amount_in),
            "amountOut": str(amount_out),
            "userType": user_type,
        }
        serialized_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        headers = self._get_l2_headers("POST", CREATE_RFQ_REQUEST, body, serialized_body)
        return post(self._build_url(CREATE_RFQ_REQUEST), headers=headers, data=serialized_body)

    def cancel_rfq_request(self, params: CancelRfqRequestParams) -> str:
        """
        Cancel an RFQ request.
        """
        self._ensure_l2_auth()

        body = {"requestId": params.request_id}
        serialized_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        headers = self._get_l2_headers("DELETE", CANCEL_RFQ_REQUEST, body, serialized_body)
        return delete(self._build_url(CANCEL_RFQ_REQUEST), headers=headers, data=serialized_body)

    def get_rfq_requests(self, params: Optional[GetRfqRequestsParams] = None) -> dict:
        """
        Get RFQ requests with optional filtering.
        """
        self._ensure_l2_auth()

        headers = self._get_l2_headers("GET", GET_RFQ_REQUESTS)
        query_params = parse_rfq_requests_params(params)

        url = self._build_url(GET_RFQ_REQUESTS)
        if query_params:
            url = f"{url}?{urlencode(query_params, doseq=True)}"

        return get(url, headers=headers)

    # =========================================================================
    # Quote-side methods
    # =========================================================================

    def create_rfq_quote(
        self,
        user_quote: RfqUserQuote,
        options: Optional[PartialCreateOrderOptions] = None,
    ) -> dict:
        """
        Create and post an RFQ quote in response to an RFQ request.
        """
        request_id = user_quote.request_id
        token_id = user_quote.token_id
        price = user_quote.price
        side = user_quote.side
        size = user_quote.size

        tick_size = self._parent._ClobClient__resolve_tick_size(
            token_id,
            options.tick_size if options else None,
        )

        tick_size_str = str(tick_size) if not isinstance(tick_size, str) else tick_size
        round_config = ROUNDING_CONFIG[tick_size_str]

        rounded_price = round_normal(price, round_config.price)
        rounded_size = round_down(size, round_config.size)

        price_decimals = int(round_config.price)
        size_decimals = int(round_config.size)
        amount_decimals = int(round_config.amount)

        rounded_price_str = f"{rounded_price:.{price_decimals}f}"
        rounded_size_str = f"{rounded_size:.{size_decimals}f}"

        size_num = float(rounded_size_str)
        price_num = float(rounded_price_str)

        user_type = int(self._parent.builder.signature_type)

        if side == BUY:
            amount_in = parse_units(rounded_size_str, COLLATERAL_TOKEN_DECIMALS)
            usdc_amount_str = f"{size_num * price_num:.{amount_decimals}f}"
            amount_out = parse_units(usdc_amount_str, COLLATERAL_TOKEN_DECIMALS)
            asset_in = token_id
            asset_out = "0"  # USDC
        else:
            usdc_amount_str = f"{size_num * price_num:.{amount_decimals}f}"
            amount_in = parse_units(usdc_amount_str, COLLATERAL_TOKEN_DECIMALS)
            amount_out = parse_units(rounded_size_str, COLLATERAL_TOKEN_DECIMALS)
            asset_in = "0"  # USDC
            asset_out = token_id

        self._ensure_l2_auth()

        body = {
            "requestId": request_id,
            "assetIn": asset_in,
            "assetOut": asset_out,
            "amountIn": str(amount_in),
            "amountOut": str(amount_out),
            "userType": user_type,
        }
        serialized_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        headers = self._get_l2_headers("POST", CREATE_RFQ_QUOTE, body, serialized_body)
        return post(self._build_url(CREATE_RFQ_QUOTE), headers=headers, data=serialized_body)

    def get_rfq_requester_quotes(self, params: Optional[GetRfqQuotesParams] = None) -> dict:
        """
        Get quotes on requests created by the authenticated user (requester view).
        """
        self._ensure_l2_auth()

        headers = self._get_l2_headers("GET", GET_RFQ_REQUESTER_QUOTES)
        query_params = parse_rfq_quotes_params(params)

        url = self._build_url(GET_RFQ_REQUESTER_QUOTES)
        if query_params:
            url = f"{url}?{urlencode(query_params, doseq=True)}"

        return get(url, headers=headers)

    def get_rfq_quoter_quotes(self, params: Optional[GetRfqQuotesParams] = None) -> dict:
        """
        Get quotes created by the authenticated user (quoter view).
        """
        self._ensure_l2_auth()

        headers = self._get_l2_headers("GET", GET_RFQ_QUOTER_QUOTES)
        query_params = parse_rfq_quotes_params(params)

        url = self._build_url(GET_RFQ_QUOTER_QUOTES)
        if query_params:
            url = f"{url}?{urlencode(query_params, doseq=True)}"

        return get(url, headers=headers)

    def get_rfq_best_quote(self, params: Optional[GetRfqBestQuoteParams] = None) -> dict:
        """
        Get the best quote for an RFQ request.
        """
        self._ensure_l2_auth()

        headers = self._get_l2_headers("GET", GET_RFQ_BEST_QUOTE)

        url = self._build_url(GET_RFQ_BEST_QUOTE)
        if params and params.request_id:
            url = f"{url}?{urlencode({'requestId': params.request_id})}"

        return get(url, headers=headers)

    def cancel_rfq_quote(self, params: CancelRfqQuoteParams) -> str:
        """
        Cancel an RFQ quote.
        """
        self._ensure_l2_auth()

        body = {"quoteId": params.quote_id}
        serialized_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        headers = self._get_l2_headers("DELETE", CANCEL_RFQ_QUOTE, body, serialized_body)
        return delete(self._build_url(CANCEL_RFQ_QUOTE), headers=headers, data=serialized_body)

    # =========================================================================
    # Trade execution methods
    # =========================================================================

    def accept_rfq_quote(self, params: AcceptQuoteParams) -> str:
        """
        Accept an RFQ quote (requester side).

        Creates a V1 signed order matching the quote and submits the acceptance.
        """
        self._ensure_l2_auth()

        resp = self.get_rfq_requester_quotes(
            GetRfqQuotesParams(quote_ids=[params.quote_id])
        )

        if not resp.get("data") or len(resp["data"]) == 0:
            raise Exception("RFQ quote not found")

        rfq_quote = resp["data"][0]
        order_creation_payload = self._get_request_order_creation_payload(rfq_quote)
        price = order_creation_payload.get("price")
        side = order_creation_payload["side"]
        size = float(order_creation_payload["size"])
        token = order_creation_payload["token"]

        order_args = OrderArgsV1(
            token_id=token,
            price=price,
            size=size,
            side=side,
            expiration=params.expiration,
        )

        order = self._build_v1_order(order_args)

        if not order:
            raise Exception("Error creating order")

        accept_payload = {
            "requestId": params.request_id,
            "quoteId": params.quote_id,
            "owner": self._parent.creds.api_key,
            "salt": int(order.salt),
            "maker": order.maker,
            "signer": order.signer,
            "taker": order.taker,
            "tokenId": order.tokenId,
            "makerAmount": order.makerAmount,
            "takerAmount": order.takerAmount,
            "expiration": int(order.expiration),
            "nonce": order.nonce,
            "feeRateBps": order.feeRateBps,
            "side": side,
            "signatureType": int(order.signatureType),
            "signature": order.signature,
        }

        serialized_body = json.dumps(accept_payload, separators=(",", ":"), ensure_ascii=False)
        headers = self._get_l2_headers("POST", RFQ_REQUESTS_ACCEPT, accept_payload, serialized_body)
        return post(
            self._build_url(RFQ_REQUESTS_ACCEPT),
            headers=headers,
            data=serialized_body,
        )

    def approve_rfq_order(self, params: ApproveOrderParams) -> str:
        """
        Approve an RFQ order (quoter side).

        Creates a V1 signed order based on quote parameters and submits the approval.
        """
        self._ensure_l2_auth()

        rfq_quotes = self.get_rfq_quoter_quotes(
            GetRfqQuotesParams(quote_ids=[params.quote_id])
        )

        if not rfq_quotes.get("data") or len(rfq_quotes["data"]) == 0:
            raise Exception("RFQ quote not found")

        rfq_quote = rfq_quotes["data"][0]

        side = rfq_quote.get("side", BUY)

        if side == BUY:
            size = rfq_quote.get("sizeIn")
        else:
            size = rfq_quote.get("sizeOut")

        token_id = rfq_quote.get("token")
        price = rfq_quote.get("price")

        order_args = OrderArgsV1(
            token_id=token_id,
            price=float(price),
            size=float(size),
            side=side,
            expiration=params.expiration,
        )

        order = self._build_v1_order(order_args)

        if not order:
            raise Exception("Error creating order")

        approve_payload = {
            "requestId": params.request_id,
            "quoteId": params.quote_id,
            "owner": self._parent.creds.api_key,
            "salt": int(order.salt),
            "maker": order.maker,
            "signer": order.signer,
            "taker": order.taker,
            "tokenId": order.tokenId,
            "makerAmount": order.makerAmount,
            "takerAmount": order.takerAmount,
            "expiration": int(order.expiration),
            "nonce": order.nonce,
            "feeRateBps": order.feeRateBps,
            "side": side,
            "signatureType": int(order.signatureType),
            "signature": order.signature,
        }
        serialized_body = json.dumps(approve_payload, separators=(",", ":"), ensure_ascii=False)
        headers = self._get_l2_headers("POST", RFQ_QUOTE_APPROVE, approve_payload, serialized_body)
        return post(
            self._build_url(RFQ_QUOTE_APPROVE),
            headers=headers,
            data=serialized_body,
        )

    # =========================================================================
    # Configuration
    # =========================================================================

    def rfq_config(self) -> dict:
        """
        Get RFQ configuration from the server.
        """
        self._ensure_l2_auth()

        headers = self._get_l2_headers("GET", RFQ_CONFIG)
        return get(self._build_url(RFQ_CONFIG), headers=headers)

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _build_v1_order(self, order_args: OrderArgsV1):
        """
        Build a signed V1 order via the parent's order builder.

        RFQ accept/approve always use V1 orders since the RFQ protocol
        requires the V1 order fields (taker, nonce, feeRateBps).
        """
        tick_size = self._parent._ClobClient__resolve_tick_size(order_args.token_id)
        neg_risk = self._parent.get_neg_risk(order_args.token_id)
        return self._parent.builder.build_order(
            order_args,
            CreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk),
            version=1,
        )

    def _get_request_order_creation_payload(self, quote: dict) -> dict:
        """
        Build the order creation payload for an RFQ request based on quote details.
        """
        raw_match_type = quote.get("matchType", MatchType.COMPLEMENTARY)
        match_type = (
            raw_match_type
            if isinstance(raw_match_type, MatchType)
            else MatchType(str(raw_match_type))
        )

        side = quote.get("side", BUY)

        if match_type == MatchType.COMPLEMENTARY:
            token = quote.get("token")
            if not token:
                raise Exception("missing token for COMPLEMENTARY match")
            side = SELL if side == BUY else BUY
            size = quote.get("sizeOut") if side == BUY else quote.get("sizeIn")
            if size is None:
                raise Exception("missing sizeIn/sizeOut for COMPLEMENTARY match")
            price = quote.get("price")
            if price is None:
                raise Exception("missing price for COMPLEMENTARY match")
            return {
                "token": token,
                "side": side,
                "size": size,
                "price": float(price),
            }
        elif match_type in (MatchType.MINT, MatchType.MERGE):
            token = quote.get("complement")
            if not token:
                raise Exception("missing complement token for MINT/MERGE match")
            size = quote.get("sizeIn") if side == BUY else quote.get("sizeOut")
            if size is None:
                raise Exception("missing sizeIn/sizeOut for MINT/MERGE match")
            price = quote.get("price")
            if price is None:
                raise Exception("missing price for MINT/MERGE match")
            # For MINT/MERGE, the requester price is the inverse of the quote price
            return {
                "token": token,
                "side": side,
                "size": size,
                "price": 1 - float(price),
            }
        else:
            raise Exception(f"invalid match type: {raw_match_type}")
