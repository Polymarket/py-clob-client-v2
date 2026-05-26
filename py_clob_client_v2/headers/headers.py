from datetime import datetime
from typing import Optional

from ..clob_types import ApiCreds, RequestArgs
from ..signing.hmac import build_hmac_signature
from ..signing.eip712 import sign_clob_auth_message
from ..signer import Signer

POLY_ADDRESS = "POLY_ADDRESS"
POLY_SIGNATURE = "POLY_SIGNATURE"
POLY_TIMESTAMP = "POLY_TIMESTAMP"
POLY_NONCE = "POLY_NONCE"
POLY_API_KEY = "POLY_API_KEY"
POLY_PASSPHRASE = "POLY_PASSPHRASE"


def create_level_1_headers(
    signer: Signer, nonce: Optional[int] = None, timestamp: Optional[int] = None
):
    """
    Creates Level 1 Poly headers for a request.
    Pass timestamp to override local clock (e.g. when use_server_time=True).
    """
    ts = timestamp if timestamp is not None else int(datetime.now().timestamp())
    n = nonce if nonce is not None else 0

    signature = sign_clob_auth_message(signer, ts, n)
    return {
        POLY_ADDRESS: signer.address(),
        POLY_SIGNATURE: signature,
        POLY_TIMESTAMP: str(ts),
        POLY_NONCE: str(n),
    }


def create_level_2_headers(
    signer: Signer,
    creds: ApiCreds,
    request_args: RequestArgs,
    timestamp: Optional[int] = None,
):
    """
    Creates Level 2 Poly headers for a request.
    Pass timestamp to override local clock (e.g. when use_server_time=True).
    Uses pre-serialized body if available for deterministic HMAC signing.
    """
    ts = timestamp if timestamp is not None else int(datetime.now().timestamp())

    body_for_sig = (
        request_args.serialized_body
        if request_args.serialized_body is not None
        else request_args.body
    )

    hmac_sig = build_hmac_signature(
        creds.api_secret,
        ts,
        request_args.method,
        request_args.request_path,
        body_for_sig,
    )

    return {
        POLY_ADDRESS: signer.address(),
        POLY_SIGNATURE: hmac_sig,
        POLY_TIMESTAMP: str(ts),
        POLY_API_KEY: creds.api_key,
        POLY_PASSPHRASE: creds.api_passphrase,
    }
