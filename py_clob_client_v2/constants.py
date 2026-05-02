import importlib.metadata

# Package version — resolved from installed metadata at import time;
# falls back to the setup.py literal when running from source without install.
try:
    __version__: str = importlib.metadata.version("py_clob_client_v2")
except importlib.metadata.PackageNotFoundError:
    __version__ = "1.0.1rc1"

# Default User-Agent sent with every outbound HTTP request.
# Cloudflare's bot-detection layer blocks the bare "python-httpx/X.Y" UA
# (and the previous unversioned "py_clob_client_v2" string — issues #38/#41).
# Override at runtime via the POLY_USER_AGENT environment variable.
DEFAULT_USER_AGENT: str = f"polymarket-clob-client-v2/{__version__}"

# Access levels
L0 = 0
L1 = 1
L2 = 2


CREDENTIAL_CREATION_WARNING = """🚨🚨🚨
Your credentials CANNOT be recovered after they've been created.
Be sure to store them safely!
🚨🚨🚨"""


L1_AUTH_UNAVAILABLE = "A private key is needed to interact with this endpoint!"

L2_AUTH_UNAVAILABLE = "API Credentials are needed to interact with this endpoint!"

BUILDER_AUTH_UNAVAILABLE = (
    "Builder API Credentials needed to interact with this endpoint!"
)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

BYTES32_ZERO = "0x0000000000000000000000000000000000000000000000000000000000000000"

AMOY = 80002
POLYGON = 137

INITIAL_CURSOR = "MA=="
END_CURSOR = "LTE="

ORDER_VERSION_MISMATCH_ERROR = "order_version_mismatch"

BUILDER_FEES_BPS = 10000

COLLATERAL_TOKEN_DECIMALS = 6
CONDITIONAL_TOKEN_DECIMALS = 6
