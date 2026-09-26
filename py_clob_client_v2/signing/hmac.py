import hmac
import hashlib
import base64
import json


def build_hmac_signature(
    secret: str, timestamp: str, method: str, requestPath: str, body=None
):
    """
    Creates an HMAC signature by signing a payload with the secret.
    Produces a URL-safe base64-encoded HMAC-SHA256 digest.
    """
    base64_secret = base64.urlsafe_b64decode(secret)
    message = str(timestamp) + str(method) + str(requestPath)
    if body:
        # A pre-serialized string body is signed verbatim so it matches the exact
        # bytes sent on the wire. Structured bodies are serialized with json.dumps
        # so Python values like False/None become JSON false/null (str() would emit
        # "False"/"None", producing a signature that mismatches the sent payload).
        if isinstance(body, str):
            message += body
        else:
            message += json.dumps(body, ensure_ascii=False)

    # nosec: SHA256 is used here for API request signing (HMAC-SHA256), not password hashing
    h = hmac.new(base64_secret, bytes(message, "utf-8"), hashlib.sha256)

    # ensure base64 encoded
    return (base64.urlsafe_b64encode(h.digest())).decode("utf-8")
