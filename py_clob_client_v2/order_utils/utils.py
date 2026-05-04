import secrets


def generate_order_salt() -> str:
    # 64 bits of entropy from a cryptographically strong RNG. The previous
    # implementation used `random.random() * current_ms_time`, which:
    #   - is not cryptographically secure
    #   - always yields a value strictly less than `current_ms_time`
    #   - has a realistic collision rate under concurrent order creation
    return str(secrets.randbits(64))
