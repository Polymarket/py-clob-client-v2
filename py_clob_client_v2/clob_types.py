from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from json import dumps
from typing import Literal

from .constants import ZERO_ADDRESS, BYTES32_ZERO


class OrderType:
    GTC = "GTC"
    FOK = "FOK"
    GTD = "GTD"
    FAK = "FAK"


@dataclass
class ApiCreds:
    api_key: str
    api_secret: str
    api_passphrase: str


@dataclass
class RequestArgs:
    method: str
    request_path: str
    body: Any = None
    serialized_body: Optional[str] = None


@dataclass
class BookParams:
    token_id: str
    side: str = ""

    def __post_init__(self):
        # Accept Side IntEnum (BUY=0, SELL=1) as well as plain strings
        if isinstance(self.side, int):
            self.side = "BUY" if self.side == 0 else "SELL"


@dataclass
class OrderArgsV1:
    """Input for creating a V1 (legacy) limit order."""

    token_id: str
    """TokenID of the Conditional token asset being traded"""

    price: float
    """Price used to create the order"""

    size: float
    """Size in terms of the ConditionalToken"""

    side: str
    """Side of the order"""

    expiration: int = 0
    """Timestamp after which the order is expired"""

    fee_rate_bps: int = 0
    """Fee rate in basis points charged to the order maker"""

    nonce: int = 0
    """Nonce used for onchain cancellations"""

    taker: str = ZERO_ADDRESS
    """Address of the order taker. Zero address = public order"""

    builder_code: str = BYTES32_ZERO
    """Builder code (bytes32) for builder fee attribution"""


@dataclass
class OrderArgsV2:
    """Input for creating a V2 limit order."""

    token_id: str
    """TokenID of the Conditional token asset being traded"""

    price: float
    """Price used to create the order"""

    size: float
    """Size in terms of the ConditionalToken"""

    side: str
    """Side of the order"""

    expiration: int = 0
    """Timestamp after which the order is expired (0 = no expiration)"""

    builder_code: str = BYTES32_ZERO
    """Builder code (bytes32) for builder fee attribution"""

    metadata: str = BYTES32_ZERO
    """Optional metadata (bytes32) attached to the order"""


# Alias: default to V2
OrderArgs = OrderArgsV2


@dataclass
class MarketOrderArgsV1:
    """Input for creating a V1 (legacy) market order."""

    token_id: str
    """TokenID of the Conditional token asset being traded"""

    amount: float
    """BUY orders: $$$ Amount to buy. SELL orders: Shares to sell"""

    side: str
    """Side of the order"""

    price: float = 0
    """Price used to create the order (auto-calculated if not provided)"""

    order_type: OrderType = OrderType.FOK

    fee_rate_bps: int = 0
    """Fee rate in basis points charged to the order maker"""

    nonce: int = 0
    """Nonce used for onchain cancellations"""

    taker: str = ZERO_ADDRESS
    """Address of the order taker. Zero address = public order"""

    builder_code: str = BYTES32_ZERO
    """Builder code (bytes32) for builder fee attribution"""


@dataclass
class MarketOrderArgsV2:
    """Input for creating a V2 market order."""

    token_id: str
    """TokenID of the Conditional token asset being traded"""

    amount: float
    """BUY orders: $$$ Amount to buy. SELL orders: Shares to sell"""

    side: str
    """Side of the order"""

    price: float = 0
    """Price used to create the order (auto-calculated if not provided)"""

    order_type: OrderType = OrderType.FOK

    user_usdc_balance: float = 0
    """User USDC balance, used to adjust fees on market buy orders"""

    builder_code: str = BYTES32_ZERO
    """Builder code (bytes32) for builder fee attribution"""

    metadata: str = BYTES32_ZERO
    """Optional metadata (bytes32) attached to the order"""


# Alias: default to V2
MarketOrderArgs = MarketOrderArgsV2


@dataclass
class TradeParams:
    id: str = None
    maker_address: str = None
    market: str = None
    asset_id: str = None
    before: int = None
    after: int = None


@dataclass
class OpenOrderParams:
    id: str = None
    market: str = None
    asset_id: str = None


@dataclass
class DropNotificationParams:
    ids: list = None


@dataclass
class OrderSummary:
    price: str = None
    size: str = None

    @property
    def __dict__(self):
        return asdict(self)

    @property
    def json(self):
        return dumps(self.__dict__)


@dataclass
class OrderBookSummary:
    market: str = None
    asset_id: str = None
    timestamp: str = None
    bids: list = None
    asks: list = None
    min_order_size: str = None
    neg_risk: bool = None
    tick_size: str = None
    last_trade_price: str = None
    hash: str = None

    @property
    def __dict__(self):
        return asdict(self)

    @property
    def json(self):
        return dumps(self.__dict__, separators=(",", ":"))


class AssetType:
    COLLATERAL = "COLLATERAL"
    CONDITIONAL = "CONDITIONAL"


@dataclass
class BalanceAllowanceParams:
    asset_type: AssetType = None
    token_id: str = None
    signature_type: int = -1


@dataclass
class OrderScoringParams:
    orderId: str


@dataclass
class OrdersScoringParams:
    orderIds: list


@dataclass
class OrderPayload:
    orderID: str


TickSize = Literal["0.1", "0.01", "0.001", "0.0001"]


@dataclass
class CreateOrderOptions:
    tick_size: TickSize
    neg_risk: bool


@dataclass
class PartialCreateOrderOptions:
    tick_size: Optional[TickSize] = None
    neg_risk: Optional[bool] = None


@dataclass
class RoundConfig:
    price: float
    size: float
    amount: float


@dataclass
class ContractConfig:
    """Contract Configuration"""

    exchange: str
    """The V1 exchange contract"""

    neg_risk_adapter: str
    """The neg risk adapter contract"""

    neg_risk_exchange: str
    """The V1 neg risk exchange contract"""

    collateral: str
    """The ERC20 collateral token"""

    conditional_tokens: str
    """The ERC1155 conditional tokens contract"""

    exchange_v2: str
    """The V2 exchange contract"""

    neg_risk_exchange_v2: str
    """The V2 neg risk exchange contract"""


@dataclass
class BuilderConfig:
    """Builder configuration for fee attribution"""

    builder_address: str = ""
    """Builder's Ethereum address"""

    builder_code: str = BYTES32_ZERO
    """Builder code (bytes32) appended to orders"""


@dataclass
class FeeDetails:
    """Platform fee details for a market"""

    fee_rate: int = 0
    """Fee rate in basis points"""

    exponent: int = 0
    """Fee exponent for the platform fee formula"""


@dataclass
class FeeInfo:
    rate: float = 0.0
    exponent: float = 0.0


@dataclass
class BuilderFeeRate:
    maker: float = 0.0
    taker: float = 0.0


@dataclass
class ClobToken:
    """A YES or NO token in a CLOB market"""

    token_id: str
    outcome: str


@dataclass
class MarketDetails:
    """Cached market details including tick size, neg risk, and fee info"""

    condition_id: str
    """Condition ID of the market"""

    tokens: Tuple = None
    """(YES token, NO token)"""

    min_tick_size: float = None
    """Minimum tick size"""

    neg_risk: bool = False
    """Whether the market uses negative risk"""

    fee_details: Optional[FeeDetails] = None
    """Platform fee details"""

    maker_base_fee: Optional[float] = None
    """V1 maker base fee rate (from mbf field)"""

    taker_base_fee: Optional[float] = None
    """V1 taker base fee rate (from tbf field)"""


@dataclass
class PostOrdersV1Args:
    order: Any  # SignedOrderV1
    orderType: OrderType = OrderType.GTC
    deferExec: bool = False


@dataclass
class PostOrdersV2Args:
    order: Any  # SignedOrderV2
    orderType: OrderType = OrderType.GTC
    deferExec: bool = False


# Union alias
PostOrdersArgs = Union[PostOrdersV1Args, PostOrdersV2Args]


@dataclass
class BanStatus:
    closed_only: bool = False


@dataclass
class OrderScoring:
    scoring: bool = False


@dataclass
class BuilderTradeParams:
    builder_code: str
    id: str = None
    maker_address: str = None
    market: str = None
    asset_id: str = None
    before: str = None
    after: str = None


@dataclass
class OrderMarketCancelParams:
    market: str = None
    asset_id: str = None


@dataclass
class BuilderApiKey:
    key: str
    secret: str
    passphrase: str


@dataclass
class BuilderApiKeyResponse:
    key: str
    created_at: Optional[str] = None
    revoked_at: Optional[str] = None


class PriceHistoryInterval:
    MAX = "max"
    ONE_WEEK = "1w"
    ONE_DAY = "1d"
    SIX_HOURS = "6h"
    ONE_HOUR = "1h"


@dataclass
class PricesHistoryParams:
    market: str = None
    start_ts: int = None
    end_ts: int = None
    fidelity: int = None
    interval: str = None


@dataclass
class EarningsParams:
    date: str = None
    """Date in YYYY-MM-DD format"""

    market: str = None


@dataclass
class RewardsMarketsParams:
    condition_id: str = None
    next_cursor: str = None
