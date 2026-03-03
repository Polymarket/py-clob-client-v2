TIME = "/time"
VERSION = "/version"

# API Key endpoints
CREATE_API_KEY = "/auth/api-key"
GET_API_KEYS = "/auth/api-keys"
DELETE_API_KEY = "/auth/api-key"
DERIVE_API_KEY = "/auth/derive-api-key"
CLOSED_ONLY = "/auth/ban-status/closed-only"

# Builder API Key endpoints
CREATE_BUILDER_API_KEY = "/auth/builder-api-key"
GET_BUILDER_API_KEYS = "/auth/builder-api-key"

# Markets
GET_SAMPLING_SIMPLIFIED_MARKETS = "/sampling-simplified-markets"
GET_SAMPLING_MARKETS = "/sampling-markets"
GET_SIMPLIFIED_MARKETS = "/simplified-markets"
GET_MARKETS = "/markets"
GET_MARKET = "/markets/"
GET_MARKET_BY_TOKEN = "/markets-by-token/"
GET_CLOB_MARKET = "/clob-markets/"

# Order Book
GET_ORDER_BOOK = "/book"
GET_ORDER_BOOKS = "/books"

# Pricing
GET_MIDPOINT = "/midpoint"
GET_MIDPOINTS = "/midpoints"
GET_PRICE = "/price"
GET_PRICES = "/prices"
GET_SPREAD = "/spread"
GET_SPREADS = "/spreads"
GET_LAST_TRADE_PRICE = "/last-trade-price"
GET_LAST_TRADES_PRICES = "/last-trades-prices"

# Market parameters
GET_TICK_SIZE = "/tick-size"
GET_NEG_RISK = "/neg-risk"
GET_FEE_RATE = "/fee-rate"

# Price history
GET_PRICES_HISTORY = "/prices-history"

# Order endpoints
POST_ORDER = "/order"
POST_ORDERS = "/orders"
CANCEL = "/order"
CANCEL_ORDERS = "/orders"
GET_ORDER = "/data/order/"
CANCEL_ALL = "/cancel-all"
CANCEL_MARKET_ORDERS = "/cancel-market-orders"
ORDERS = "/data/orders"
TRADES = "/data/trades"
IS_ORDER_SCORING = "/order-scoring"
ARE_ORDERS_SCORING = "/orders-scoring"

# Notifications
GET_NOTIFICATIONS = "/notifications"
DROP_NOTIFICATIONS = "/notifications"

# Balance & Allowance
GET_BALANCE_ALLOWANCE = "/balance-allowance"
UPDATE_BALANCE_ALLOWANCE = "/balance-allowance/update"

# Live activity
GET_MARKET_TRADES_EVENTS = "/live-activity/events/"

# Rewards
GET_EARNINGS_FOR_USER_FOR_DAY = "/rewards/user"
GET_TOTAL_EARNINGS_FOR_USER_FOR_DAY = "/rewards/user/total"
GET_LIQUIDITY_REWARD_PERCENTAGES = "/rewards/user/percentages"
GET_REWARDS_MARKETS_CURRENT = "/rewards/markets/current"
GET_REWARDS_MARKETS = "/rewards/markets/"
GET_REWARDS_EARNINGS_PERCENTAGES = "/rewards/user/markets"

# Builder endpoints
POST_HEARTBEAT = "/v1/heartbeats"
GET_BUILDER_TRADES = "/builder/trades"

# RFQ Endpoints
CREATE_RFQ_REQUEST = "/rfq/request"
CANCEL_RFQ_REQUEST = "/rfq/request"
GET_RFQ_REQUESTS = "/rfq/data/requests"
CREATE_RFQ_QUOTE = "/rfq/quote"
CANCEL_RFQ_QUOTE = "/rfq/quote"
GET_RFQ_REQUESTER_QUOTES = "/rfq/data/requester/quotes"
GET_RFQ_QUOTER_QUOTES = "/rfq/data/quoter/quotes"
GET_RFQ_BEST_QUOTE = "/rfq/data/best-quote"
RFQ_REQUESTS_ACCEPT = "/rfq/request/accept"
RFQ_QUOTE_APPROVE = "/rfq/quote/approve"
RFQ_CONFIG = "/rfq/config"
