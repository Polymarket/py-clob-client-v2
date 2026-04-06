import json
import logging
from typing import Optional

from .clob_types import (
    ApiCreds,
    BalanceAllowanceParams,
    BookParams,
    BuilderConfig,
    BuilderFeeRate,
    BuilderTradeParams,
    CreateOrderOptions,
    DropNotificationParams,
    EarningsParams,
    FeeInfo,
    MarketOrderArgsV2,
    OpenOrderParams,
    OrderArgsV2,
    OrderBookSummary,
    OrderMarketCancelParams,
    OrderPayload,
    OrderScoringParams,
    OrdersScoringParams,
    OrderType,
    PartialCreateOrderOptions,
    PostOrdersArgs,
    PricesHistoryParams,
    RewardsMarketsParams,
    TickSize,
    TradeParams,
)
from .constants import (
    BUILDER_FEES_BPS,
    BYTES32_ZERO,
    END_CURSOR,
    INITIAL_CURSOR,
    L1_AUTH_UNAVAILABLE,
    L2_AUTH_UNAVAILABLE,
    ORDER_VERSION_MISMATCH_ERROR,
    L0,
    L1,
    L2,
)
from .endpoints import (
    ARE_ORDERS_SCORING,
    OK,
    CANCEL,
    CANCEL_ALL,
    CANCEL_MARKET_ORDERS,
    CANCEL_ORDERS,
    CLOSED_ONLY,
    CREATE_API_KEY,
    CREATE_BUILDER_API_KEY,
    DELETE_API_KEY,
    DERIVE_API_KEY,
    GET_API_KEYS,
    GET_BALANCE_ALLOWANCE,
    GET_BUILDER_API_KEYS,
    GET_BUILDER_FEE_RATE,
    GET_BUILDER_TRADES,
    GET_CLOB_MARKET,
    GET_EARNINGS_FOR_USER_FOR_DAY,
    GET_FEE_RATE,
    GET_LAST_TRADE_PRICE,
    GET_LAST_TRADES_PRICES,
    GET_LIQUIDITY_REWARD_PERCENTAGES,
    GET_MARKET,
    GET_MARKET_BY_TOKEN,
    GET_MARKETS,
    GET_MIDPOINT,
    GET_MIDPOINTS,
    GET_NEG_RISK,
    GET_NOTIFICATIONS,
    GET_ORDER,
    GET_ORDER_BOOK,
    GET_ORDER_BOOKS,
    GET_PRICE,
    GET_PRICES,
    GET_PRICES_HISTORY,
    GET_REWARDS_EARNINGS_PERCENTAGES,
    GET_REWARDS_MARKETS,
    GET_REWARDS_MARKETS_CURRENT,
    GET_SAMPLING_MARKETS,
    GET_SAMPLING_SIMPLIFIED_MARKETS,
    GET_SIMPLIFIED_MARKETS,
    GET_SPREAD,
    GET_SPREADS,
    GET_TICK_SIZE,
    GET_TOTAL_EARNINGS_FOR_USER_FOR_DAY,
    IS_ORDER_SCORING,
    ORDERS,
    POST_ORDER,
    POST_ORDERS,
    TIME,
    TRADES,
    UPDATE_BALANCE_ALLOWANCE,
    VERSION,
)
from .exceptions import PolyException
from .headers.headers import create_level_1_headers, create_level_2_headers
from .http_helpers.helpers import (
    delete,
    get,
    parse_drop_notification_params,
    post,
)
from .order_builder.builder import OrderBuilder
from .clob_types import RequestArgs
from .rfq import RfqClient
from .signer import Signer
from .utilities import (
    adjust_market_buy_amount,
    generate_orderbook_summary_hash,
    is_tick_size_smaller,
    price_valid,
)
from .order_utils.model.order_data_v1 import order_to_json_v1
from .order_utils.model.order_data_v2 import order_to_json_v2
from .order_utils.model.side import Side

logger = logging.getLogger(__name__)

def _is_v2_order(order) -> bool:
    """Returns True if order is a V2 signed order (has timestamp field)."""
    return hasattr(order, "timestamp")

class ClobClient:
    def __init__(
        self,
        host: str,
        chain_id: int,
        key: str = None,
        creds: ApiCreds = None,
        signature_type: int = None,
        funder: str = None,
        builder_config: BuilderConfig = None,
        use_server_time: bool = False,
        retry_on_error: bool = False,
    ):
        self.host = host.rstrip("/")
        self.chain_id = chain_id
        self.use_server_time = use_server_time
        self.retry_on_error = retry_on_error
        self.builder_config = builder_config

        self.signer = Signer(key, chain_id) if key else None
        self.creds = creds
        self.mode = self._get_client_mode()

        self.builder = OrderBuilder(
            signer=self.signer,
            signature_type=signature_type,
            funder=funder,
        )

        # Caches
        self.__tick_sizes: dict = {}
        self.__neg_risk: dict = {}
        self.__fee_infos: dict = {}
        self.__builder_fee_rates: dict = {}
        self.__token_condition_map: dict = {}
        self.__cached_version: Optional[int] = None

        self.rfq = RfqClient(self)

    def _get_client_mode(self) -> int:
        if self.signer is None:
            return L0
        if self.creds is None:
            return L1
        return L2

    def assert_level_1_auth(self):
        if self.signer is None:
            raise PolyException(L1_AUTH_UNAVAILABLE)

    def assert_level_2_auth(self):
        if self.signer is None:
            raise PolyException(L1_AUTH_UNAVAILABLE)
        if self.creds is None:
            raise PolyException(L2_AUTH_UNAVAILABLE)

    def get_address(self) -> str:
        self.assert_level_1_auth()
        return self.signer.address()

    def set_api_creds(self, creds: ApiCreds):
        self.creds = creds
        self.mode = self._get_client_mode()

    def _get(self, endpoint: str, headers=None, params: dict = None):
        return get(endpoint, headers=headers, params=params)

    def _post(self, endpoint: str, headers=None, data=None, params: dict = None):
        return post(
            endpoint,
            headers=headers,
            data=data,
            params=params,
            retry_on_error=self.retry_on_error,
        )

    def _delete(self, endpoint: str, headers=None, data=None, params: dict = None):
        return delete(endpoint, headers=headers, data=data, params=params)

    def _get_timestamp(self) -> Optional[int]:
        if not self.use_server_time:
            return None
        result = get(f"{self.host}{TIME}")
        if isinstance(result, dict):
            return result.get("time") or result.get("timestamp")
        return int(result)

    def _l1_headers(self, nonce: int = None) -> dict:
        self.assert_level_1_auth()
        return create_level_1_headers(
            self.signer, nonce=nonce, timestamp=self._get_timestamp()
        )

    def _l2_headers(
        self, method: str, endpoint: str, body=None, serialized_body: str = None
    ) -> dict:
        self.assert_level_2_auth()
        request_args = RequestArgs(
            method=method,
            request_path=endpoint,
            body=body,
            serialized_body=serialized_body,
        )
        return create_level_2_headers(
            self.signer, self.creds, request_args, timestamp=self._get_timestamp()
        )

    def get_ok(self):
        return self._get(f"{self.host}{OK}")

    def get_version(self) -> int:
        try:
            result = self._get(f"{self.host}{VERSION}")
            return result.get("version", 2) if isinstance(result, dict) else 2
        except Exception:
            return 2

    def get_server_time(self):
        return self._get(f"{self.host}{TIME}")

    def get_sampling_simplified_markets(self, next_cursor: str = INITIAL_CURSOR):
        return self._get(
            f"{self.host}{GET_SAMPLING_SIMPLIFIED_MARKETS}",
            params={"next_cursor": next_cursor},
        )

    def get_sampling_markets(self, next_cursor: str = INITIAL_CURSOR):
        return self._get(
            f"{self.host}{GET_SAMPLING_MARKETS}",
            params={"next_cursor": next_cursor},
        )

    def get_simplified_markets(self, next_cursor: str = INITIAL_CURSOR):
        return self._get(
            f"{self.host}{GET_SIMPLIFIED_MARKETS}",
            params={"next_cursor": next_cursor},
        )

    def get_markets(self, next_cursor: str = INITIAL_CURSOR):
        return self._get(
            f"{self.host}{GET_MARKETS}",
            params={"next_cursor": next_cursor},
        )

    def get_market(self, condition_id: str):
        return self._get(f"{self.host}{GET_MARKET}{condition_id}")

    def get_clob_market_info(self, condition_id: str) -> dict:
        result = self._get(f"{self.host}{GET_CLOB_MARKET}{condition_id}")

        if not result or not result.get("t"):
            raise PolyException(f"failed to fetch market info for condition id {condition_id}")

        for token in result["t"]:
            if not token:
                continue
            token_id = token["t"]
            self.__token_condition_map[token_id] = condition_id
            self.__tick_sizes[token_id] = str(result["mts"])
            self.__neg_risk[token_id] = result.get("nr", False)

            fd = result.get("fd") or {}
            self.__fee_infos[token_id] = FeeInfo(
                rate=fd.get("r", 0.0),
                exponent=fd.get("e", 0.0),
            )

        return result

    def get_order_book(self, token_id: str):
        return self._get(
            f"{self.host}{GET_ORDER_BOOK}", params={"token_id": token_id}
        )

    def get_order_books(self, params: list):
        return self._post(f"{self.host}{GET_ORDER_BOOKS}", data=params)

    def get_order_book_hash(self, orderbook: OrderBookSummary) -> str:
        return generate_orderbook_summary_hash(orderbook)

    def get_tick_size(self, token_id: str) -> TickSize:
        if token_id in self.__tick_sizes:
            return self.__tick_sizes[token_id]

        if token_id in self.__token_condition_map:
            self.get_clob_market_info(self.__token_condition_map[token_id])
            return self.__tick_sizes[token_id]

        result = self._get(
            f"{self.host}{GET_TICK_SIZE}", params={"token_id": token_id}
        )
        self.__tick_sizes[token_id] = str(result["minimum_tick_size"])
        return self.__tick_sizes[token_id]

    def get_neg_risk(self, token_id: str) -> bool:
        if token_id in self.__neg_risk:
            return self.__neg_risk[token_id]

        if token_id in self.__token_condition_map:
            self.get_clob_market_info(self.__token_condition_map[token_id])
            return self.__neg_risk[token_id]

        result = self._get(
            f"{self.host}{GET_NEG_RISK}", params={"token_id": token_id}
        )
        self.__neg_risk[token_id] = result["neg_risk"]
        return self.__neg_risk[token_id]

    def get_fee_rate_bps(self, token_id: str) -> float:
        if token_id in self.__fee_infos:
            return self.__fee_infos[token_id].rate

        if token_id in self.__token_condition_map:
            self.get_clob_market_info(self.__token_condition_map[token_id])
            return self.__fee_infos[token_id].rate

        result = self._get(
            f"{self.host}{GET_FEE_RATE}", params={"token_id": token_id}
        )
        self.__fee_infos[token_id] = FeeInfo(rate=result["base_fee"], exponent=0.0)
        return self.__fee_infos[token_id].rate

    def get_fee_exponent(self, token_id: str) -> float:
        if token_id in self.__fee_infos:
            return self.__fee_infos[token_id].exponent
        self.__ensure_market_info_cached(token_id)
        return self.__fee_infos[token_id].exponent

    def get_midpoint(self, token_id: str):
        return self._get(f"{self.host}{GET_MIDPOINT}", params={"token_id": token_id})

    def get_midpoints(self, params: list):
        return self._post(f"{self.host}{GET_MIDPOINTS}", data=params)

    def get_price(self, token_id: str, side):
        if isinstance(side, int):
            side = "BUY" if side == Side.BUY else "SELL"
        return self._get(
            f"{self.host}{GET_PRICE}", params={"token_id": token_id, "side": side}
        )

    def get_prices(self, params: list):
        return self._post(f"{self.host}{GET_PRICES}", data=params)

    def get_spread(self, token_id: str):
        return self._get(f"{self.host}{GET_SPREAD}", params={"token_id": token_id})

    def get_spreads(self, params: list):
        return self._post(f"{self.host}{GET_SPREADS}", data=params)

    def get_last_trade_price(self, token_id: str):
        return self._get(
            f"{self.host}{GET_LAST_TRADE_PRICE}", params={"token_id": token_id}
        )

    def get_last_trades_prices(self, params: list):
        return self._post(f"{self.host}{GET_LAST_TRADES_PRICES}", data=params)

    def get_prices_history(self, params: PricesHistoryParams):
        if params.interval is None and (params.start_ts is None or params.end_ts is None):
            raise ValueError("get_prices_history requires either interval or both start_ts and end_ts")
        p = {}
        if params.market:
            p["market"] = params.market
        if params.start_ts is not None:
            p["startTs"] = params.start_ts
        if params.end_ts is not None:
            p["endTs"] = params.end_ts
        if params.fidelity is not None:
            p["fidelity"] = params.fidelity
        if params.interval is not None:
            p["interval"] = params.interval
        return self._get(f"{self.host}{GET_PRICES_HISTORY}", params=p)

    def calculate_market_price(
        self,
        token_id: str,
        side: str,
        amount: float,
        order_type: OrderType = OrderType.FOK,
    ) -> float:
        book = self.get_order_book(token_id)
        if not book:
            raise PolyException("no orderbook")
        if side == "BUY" or side == Side.BUY:
            asks = book.get("asks") if isinstance(book, dict) else book.asks
            if not asks:
                raise PolyException("no match")
            return self.builder.calculate_buy_market_price(asks, amount, order_type)
        else:
            bids = book.get("bids") if isinstance(book, dict) else book.bids
            if not bids:
                raise PolyException("no match")
            return self.builder.calculate_sell_market_price(bids, amount, order_type)

    def get_current_rewards(self) -> list:
        results = []
        next_cursor = INITIAL_CURSOR
        while next_cursor != END_CURSOR:
            response = self._get(
                f"{self.host}{GET_REWARDS_MARKETS_CURRENT}",
                params={"next_cursor": next_cursor},
            )
            next_cursor = response["next_cursor"]
            results.extend(response["data"])
        return results

    def get_raw_rewards_for_market(self, condition_id: str) -> list:
        results = []
        next_cursor = INITIAL_CURSOR
        while next_cursor != END_CURSOR:
            response = self._get(
                f"{self.host}{GET_REWARDS_MARKETS}{condition_id}",
                params={"next_cursor": next_cursor},
            )
            next_cursor = response["next_cursor"]
            results.extend(response["data"])
        return results

    def create_api_key(self, nonce: int = None) -> ApiCreds:
        headers = self._l1_headers(nonce=nonce)
        resp = self._post(f"{self.host}{CREATE_API_KEY}", headers=headers)
        return ApiCreds(
            api_key=resp["apiKey"],
            api_secret=resp["secret"],
            api_passphrase=resp["passphrase"],
        )

    def derive_api_key(self, nonce: int = None) -> ApiCreds:
        headers = self._l1_headers(nonce=nonce)
        resp = self._get(f"{self.host}{DERIVE_API_KEY}", headers=headers)
        return ApiCreds(
            api_key=resp["apiKey"],
            api_secret=resp["secret"],
            api_passphrase=resp["passphrase"],
        )

    def create_or_derive_api_key(self, nonce: int = None) -> ApiCreds:
        try:
            resp = self.create_api_key(nonce=nonce)
            if resp.api_key:
                return resp
        except Exception:
            pass
        return self.derive_api_key(nonce=nonce)

    def get_api_keys(self):
        headers = self._l2_headers("GET", GET_API_KEYS)
        return self._get(f"{self.host}{GET_API_KEYS}", headers=headers)

    def get_closed_only_mode(self):
        headers = self._l2_headers("GET", CLOSED_ONLY)
        return self._get(f"{self.host}{CLOSED_ONLY}", headers=headers)

    def delete_api_key(self):
        headers = self._l2_headers("DELETE", DELETE_API_KEY)
        return self._delete(f"{self.host}{DELETE_API_KEY}", headers=headers)

    def get_order(self, order_id: str):
        endpoint = f"{GET_ORDER}{order_id}"
        headers = self._l2_headers("GET", endpoint)
        return self._get(f"{self.host}{endpoint}", headers=headers)

    def get_open_orders(
        self,
        params: OpenOrderParams = None,
        only_first_page: bool = False,
        next_cursor: str = None,
    ) -> list:
        headers = self._l2_headers("GET", ORDERS)
        results = []
        cursor = next_cursor or INITIAL_CURSOR
        first = True
        while cursor != END_CURSOR and (first or not only_first_page):
            first = False
            p = {}
            if params:
                if params.market:
                    p["market"] = params.market
                if params.asset_id:
                    p["asset_id"] = params.asset_id
                if params.id:
                    p["id"] = params.id
            p["next_cursor"] = cursor
            response = self._get(f"{self.host}{ORDERS}", headers=headers, params=p)
            cursor = response["next_cursor"]
            results.extend(response["data"])
        return results

    def get_trades(
        self,
        params: TradeParams = None,
        only_first_page: bool = False,
        next_cursor: str = None,
    ) -> list:
        headers = self._l2_headers("GET", TRADES)
        results = []
        cursor = next_cursor or INITIAL_CURSOR
        first = True
        while cursor != END_CURSOR and (first or not only_first_page):
            first = False
            p = {}
            if params:
                if params.market:
                    p["market"] = params.market
                if params.asset_id:
                    p["asset_id"] = params.asset_id
                if params.after:
                    p["after"] = params.after
                if params.before:
                    p["before"] = params.before
                if params.maker_address:
                    p["maker_address"] = params.maker_address
                if params.id:
                    p["id"] = params.id
            p["next_cursor"] = cursor
            response = self._get(f"{self.host}{TRADES}", headers=headers, params=p)
            cursor = response["next_cursor"]
            results.extend(response["data"])
        return results

    def get_trades_paginated(
        self,
        params: TradeParams = None,
        next_cursor: str = None,
    ) -> dict:
        headers = self._l2_headers("GET", TRADES)
        cursor = next_cursor or INITIAL_CURSOR
        p = {}
        if params:
            if params.market:
                p["market"] = params.market
            if params.asset_id:
                p["asset_id"] = params.asset_id
            if params.after:
                p["after"] = params.after
            if params.before:
                p["before"] = params.before
            if params.maker_address:
                p["maker_address"] = params.maker_address
            if params.id:
                p["id"] = params.id
        p["next_cursor"] = cursor
        response = self._get(f"{self.host}{TRADES}", headers=headers, params=p)
        data = response.get("data", [])
        return {
            "trades": list(data) if data else [],
            "next_cursor": response.get("next_cursor"),
            "limit": response.get("limit"),
            "count": response.get("count"),
        }

    def get_builder_trades(
        self,
        params: BuilderTradeParams,
        next_cursor: str = None,
    ) -> dict:
        if not params.builder_code or params.builder_code == BYTES32_ZERO:
            raise PolyException("builder_code is required and cannot be zero")
        headers = self._l2_headers("GET", GET_BUILDER_TRADES)
        cursor = next_cursor or INITIAL_CURSOR
        p = {"builder_code": params.builder_code}
        if params.id:
            p["id"] = params.id
        if params.maker_address:
            p["maker_address"] = params.maker_address
        if params.market:
            p["market"] = params.market
        if params.asset_id:
            p["asset_id"] = params.asset_id
        if params.before:
            p["before"] = params.before
        if params.after:
            p["after"] = params.after
        p["next_cursor"] = cursor
        response = self._get(f"{self.host}{GET_BUILDER_TRADES}", headers=headers, params=p)
        data = response.get("data", [])
        return {
            "trades": list(data) if data else [],
            "next_cursor": response.get("next_cursor"),
            "limit": response.get("limit"),
            "count": response.get("count"),
        }

    def get_notifications(self):
        headers = self._l2_headers("GET", GET_NOTIFICATIONS)
        return self._get(
            f"{self.host}{GET_NOTIFICATIONS}",
            headers=headers,
            params={"signature_type": int(self.builder.signature_type)},
        )

    def drop_notifications(self, params: DropNotificationParams = None):
        headers = self._l2_headers("DELETE", GET_NOTIFICATIONS)
        return self._delete(
            f"{self.host}{GET_NOTIFICATIONS}",
            headers=headers,
            params=parse_drop_notification_params(params),
        )

    def get_balance_allowance(self, params: BalanceAllowanceParams = None):
        headers = self._l2_headers("GET", GET_BALANCE_ALLOWANCE)
        p = {"signature_type": int(self.builder.signature_type)}
        if params:
            if params.asset_type:
                p["asset_type"] = str(params.asset_type)
            if params.token_id:
                p["token_id"] = params.token_id
        return self._get(f"{self.host}{GET_BALANCE_ALLOWANCE}", headers=headers, params=p)

    def update_balance_allowance(self, params: BalanceAllowanceParams = None):
        headers = self._l2_headers("GET", UPDATE_BALANCE_ALLOWANCE)
        p = {"signature_type": int(self.builder.signature_type)}
        if params:
            if params.asset_type:
                p["asset_type"] = str(params.asset_type)
            if params.token_id:
                p["token_id"] = params.token_id
        return self._get(f"{self.host}{UPDATE_BALANCE_ALLOWANCE}", headers=headers, params=p)

    def create_order(
        self,
        order_args: OrderArgsV2,
        options: PartialCreateOrderOptions = None,
    ):
        self.assert_level_1_auth()

        if self.builder_config and self.builder_config.builder_code:
            if not getattr(order_args, "builder_code", None) or order_args.builder_code == BYTES32_ZERO:
                order_args.builder_code = self.builder_config.builder_code

        token_id = order_args.token_id

        if not options or not options.tick_size:
            raise PolyException("tick_size is required in options")

        tick_size = options.tick_size

        if not price_valid(order_args.price, tick_size):
            ts = float(tick_size)
            raise PolyException(
                f"invalid price ({order_args.price}), min: {ts} - max: {1 - ts}"
            )

        neg_risk = (
            options.neg_risk
            if (options and options.neg_risk is not None)
            else self.get_neg_risk(token_id)
        )
        version = self.__resolve_version()

        return self.builder.build_order(
            order_args,
            CreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk),
            version=version,
        )

    def create_market_order(
        self,
        order_args: MarketOrderArgsV2,
        options: PartialCreateOrderOptions = None,
    ):
        self.assert_level_1_auth()

        token_id = order_args.token_id
        self.__ensure_market_info_cached(token_id)

        tick_size = self.__resolve_tick_size(
            token_id, options.tick_size if options else None
        )

        if not order_args.price:
            order_args.price = self.calculate_market_price(
                token_id,
                order_args.side,
                order_args.amount,
                order_args.order_type,
            )

        if not price_valid(order_args.price, tick_size):
            ts = float(tick_size)
            raise PolyException(
                f"invalid price ({order_args.price}), min: {ts} - max: {1 - ts}"
            )

        if self.builder_config and self.builder_config.builder_code:
            if not getattr(order_args, "builder_code", None) or order_args.builder_code == BYTES32_ZERO:
                order_args.builder_code = self.builder_config.builder_code

        builder_code = getattr(order_args, "builder_code", BYTES32_ZERO)

        if (order_args.side == "BUY" or order_args.side == Side.BUY) and order_args.user_usdc_balance:
            self.__ensure_builder_fee_rate_cached(builder_code)
            builder_taker_fee_rate = (
                self.__builder_fee_rates[builder_code].taker
                if builder_code and builder_code != BYTES32_ZERO and builder_code in self.__builder_fee_rates
                else 0
            )
            fi = self.__fee_infos.get(token_id) or FeeInfo()
            order_args.amount = adjust_market_buy_amount(
                order_args.amount,
                order_args.user_usdc_balance,
                order_args.price,
                fi.rate or 0.0,
                fi.exponent or 0.0,
                builder_taker_fee_rate,
            )

        neg_risk = (
            options.neg_risk
            if (options and options.neg_risk is not None)
            else self.get_neg_risk(token_id)
        )
        version = self.__resolve_version()

        return self.builder.build_market_order(
            order_args,
            CreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk),
            version=version,
        )

    def create_and_post_order(
        self,
        order_args: OrderArgsV2,
        options: PartialCreateOrderOptions = None,
        order_type: OrderType = OrderType.GTC,
        defer_exec: bool = False,
    ):
        return self._retry_on_version_update(
            lambda: self.post_order(
                self.create_order(order_args, options), order_type, defer_exec
            )
        )

    def create_and_post_market_order(
        self,
        order_args: MarketOrderArgsV2,
        options: PartialCreateOrderOptions = None,
        order_type: OrderType = OrderType.FOK,
        defer_exec: bool = False,
    ):
        return self._retry_on_version_update(
            lambda: self.post_order(
                self.create_market_order(order_args, options), order_type, defer_exec
            )
        )

    def post_order(
        self,
        order,
        order_type: OrderType = OrderType.GTC,
        defer_exec: bool = False,
    ):
        self.assert_level_2_auth()

        owner = self.creds.api_key or ""
        order_payload = (
            order_to_json_v2(order, owner, order_type, defer_exec)
            if _is_v2_order(order)
            else order_to_json_v1(order, owner, order_type, defer_exec)
        )
        serialized = json.dumps(order_payload, separators=(",", ":"))
        headers = self._l2_headers(
            "POST", POST_ORDER, body=order_payload, serialized_body=serialized
        )

        res = self._post(f"{self.host}{POST_ORDER}", headers=headers, data=serialized)

        if self._is_order_version_mismatch(res):
            self.__resolve_version(force_update=True)

        return res

    def post_orders(self, args: list, defer_exec: bool = False):
        self.assert_level_2_auth()

        owner = self.creds.api_key or ""
        orders_payload = []
        for arg in args:
            order = arg.order
            order_type = arg.orderType
            payload = (
                order_to_json_v2(order, owner, order_type, defer_exec)
                if _is_v2_order(order)
                else order_to_json_v1(order, owner, order_type, defer_exec)
            )
            orders_payload.append(payload)

        serialized = json.dumps(orders_payload, separators=(",", ":"))
        headers = self._l2_headers(
            "POST", POST_ORDERS, body=orders_payload, serialized_body=serialized
        )

        res = self._post(f"{self.host}{POST_ORDERS}", headers=headers, data=serialized)

        if self._is_order_version_mismatch(res):
            self.__resolve_version(force_update=True)

        return res

    def cancel_order(self, payload: OrderPayload):
        self.assert_level_2_auth()
        body = {"orderID": payload.orderID}
        serialized = json.dumps(body, separators=(",", ":"))
        headers = self._l2_headers("DELETE", CANCEL, body=body, serialized_body=serialized)
        return self._delete(f"{self.host}{CANCEL}", headers=headers, data=serialized)

    def cancel_orders(self, order_hashes: list):
        self.assert_level_2_auth()
        serialized = json.dumps(order_hashes, separators=(",", ":"))
        headers = self._l2_headers(
            "DELETE", CANCEL_ORDERS, body=order_hashes, serialized_body=serialized
        )
        return self._delete(f"{self.host}{CANCEL_ORDERS}", headers=headers, data=serialized)

    def cancel_all(self):
        self.assert_level_2_auth()
        headers = self._l2_headers("DELETE", CANCEL_ALL)
        return self._delete(f"{self.host}{CANCEL_ALL}", headers=headers)

    def cancel_market_orders(self, payload: OrderMarketCancelParams):
        self.assert_level_2_auth()
        body = {}
        if payload.market:
            body["market"] = payload.market
        if payload.asset_id:
            body["asset_id"] = payload.asset_id
        serialized = json.dumps(body, separators=(",", ":"))
        headers = self._l2_headers(
            "DELETE", CANCEL_MARKET_ORDERS, body=body, serialized_body=serialized
        )
        return self._delete(f"{self.host}{CANCEL_MARKET_ORDERS}", headers=headers, data=serialized)

    def is_order_scoring(self, params: OrderScoringParams = None):
        self.assert_level_2_auth()
        headers = self._l2_headers("GET", IS_ORDER_SCORING)
        p = {}
        if params and params.orderId:
            p["order_id"] = params.orderId
        return self._get(f"{self.host}{IS_ORDER_SCORING}", headers=headers, params=p or None)

    def are_orders_scoring(self, params: OrdersScoringParams = None):
        self.assert_level_2_auth()
        order_ids = params.orderIds if params else []
        serialized = json.dumps(order_ids, separators=(",", ":"))
        headers = self._l2_headers(
            "POST", ARE_ORDERS_SCORING, body=order_ids, serialized_body=serialized
        )
        return self._post(f"{self.host}{ARE_ORDERS_SCORING}", headers=headers, data=serialized)

    def get_earnings_for_user_for_day(self, date: str) -> list:
        self.assert_level_2_auth()
        headers = self._l2_headers("GET", GET_EARNINGS_FOR_USER_FOR_DAY)
        results = []
        next_cursor = INITIAL_CURSOR
        while next_cursor != END_CURSOR:
            p = {
                "date": date,
                "signature_type": int(self.builder.signature_type),
                "next_cursor": next_cursor,
            }
            response = self._get(
                f"{self.host}{GET_EARNINGS_FOR_USER_FOR_DAY}", headers=headers, params=p
            )
            next_cursor = response["next_cursor"]
            results.extend(response["data"])
        return results

    def get_total_earnings_for_user_for_day(self, date: str):
        self.assert_level_2_auth()
        headers = self._l2_headers("GET", GET_TOTAL_EARNINGS_FOR_USER_FOR_DAY)
        p = {
            "date": date,
            "signature_type": int(self.builder.signature_type),
        }
        return self._get(
            f"{self.host}{GET_TOTAL_EARNINGS_FOR_USER_FOR_DAY}", headers=headers, params=p
        )

    def get_user_earnings_and_markets_config(
        self,
        date: str,
        order_by: str = "",
        position: str = "",
        no_competition: bool = False,
    ) -> list:
        self.assert_level_2_auth()
        headers = self._l2_headers("GET", GET_REWARDS_EARNINGS_PERCENTAGES)
        results = []
        next_cursor = INITIAL_CURSOR
        while next_cursor != END_CURSOR:
            p = {
                "date": date,
                "signature_type": int(self.builder.signature_type),
                "next_cursor": next_cursor,
                "order_by": order_by,
                "position": position,
                "no_competition": no_competition,
            }
            response = self._get(
                f"{self.host}{GET_REWARDS_EARNINGS_PERCENTAGES}", headers=headers, params=p
            )
            next_cursor = response["next_cursor"]
            results.extend(response["data"])
        return results

    def get_reward_percentages(self):
        self.assert_level_2_auth()
        headers = self._l2_headers("GET", GET_LIQUIDITY_REWARD_PERCENTAGES)
        p = {"signature_type": int(self.builder.signature_type)}
        return self._get(
            f"{self.host}{GET_LIQUIDITY_REWARD_PERCENTAGES}", headers=headers, params=p
        )

    def create_builder_api_key(self):
        self.assert_level_2_auth()
        headers = self._l2_headers("POST", CREATE_BUILDER_API_KEY)
        return self._post(f"{self.host}{CREATE_BUILDER_API_KEY}", headers=headers)

    def get_builder_api_keys(self):
        self.assert_level_2_auth()
        headers = self._l2_headers("GET", GET_BUILDER_API_KEYS)
        return self._get(f"{self.host}{GET_BUILDER_API_KEYS}", headers=headers)

    def __resolve_tick_size(self, token_id: str, tick_size: TickSize = None) -> TickSize:
        min_tick_size = self.get_tick_size(token_id)
        if tick_size:
            if is_tick_size_smaller(tick_size, min_tick_size):
                raise PolyException(
                    f"invalid tick size ({tick_size}), minimum for the market is {min_tick_size}"
                )
            return tick_size
        return min_tick_size

    def __resolve_version(self, force_update: bool = False) -> int:
        if not force_update and self.__cached_version is not None:
            return self.__cached_version
        self.__cached_version = self.get_version()
        return self.__cached_version

    def __ensure_builder_fee_rate_cached(self, builder_code: str):
        if not builder_code or builder_code == BYTES32_ZERO:
            return
        if builder_code in self.__builder_fee_rates:
            return
        try:
            result = self._get(f"{self.host}{GET_BUILDER_FEE_RATE}{builder_code}")
            self.__builder_fee_rates[builder_code] = BuilderFeeRate(
                maker=result.get("builder_maker_fee_rate_bps", 0) / BUILDER_FEES_BPS,
                taker=result.get("builder_taker_fee_rate_bps", 0) / BUILDER_FEES_BPS,
            )
        except Exception:
            logging.warning("failed to fetch builder fee rate for %s, will retry on next order", builder_code)

    def __ensure_market_info_cached(self, token_id: str):
        if token_id in self.__fee_infos:
            return

        if token_id not in self.__token_condition_map:
            result = self._get(f"{self.host}{GET_MARKET_BY_TOKEN}{token_id}")
            if not result or not result.get("condition_id"):
                raise PolyException(f"failed to resolve condition id for token {token_id}")
            self.__token_condition_map[token_id] = result["condition_id"]

        self.get_clob_market_info(self.__token_condition_map[token_id])

    def _is_order_version_mismatch(self, resp) -> bool:
        if not isinstance(resp, dict):
            return False
        error = resp.get("error")
        if not error:
            return False
        message = error if isinstance(error, str) else json.dumps(error)
        return ORDER_VERSION_MISMATCH_ERROR in message

    def _retry_on_version_update(self, func):
        version = self.__resolve_version()
        result = None
        for _ in range(2):
            result = func()
            if version == self.__resolve_version():
                break
        return result
