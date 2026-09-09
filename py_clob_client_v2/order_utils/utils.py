import secrets

# Number of random bits used for an order salt.
#
# Capped at 53 because the CLOB wire contract carries `salt` as a JSON number.
# JSON numbers are IEEE-754 doubles for many consumers and represent integers
# exactly only up to 2**53 - 1, so a wider salt could be rounded during transport
# while the EIP-712 signature was produced over the original value. The server
# would then reconstruct a different digest and reject the order as having an
# invalid signature. 53 bits still gives roughly 9.0e15 of collision space.
SALT_BITS = 53


def generate_order_salt() -> str:
    """
    Generate a cryptographically random order salt.

    The salt is the only entropy that distinguishes two otherwise identical
    orders in the EIP-712 digest, so it is a security-relevant value: a
    predictable salt lets a third party precompute an order hash before it is
    broadcast, and a colliding salt produces a duplicate order hash.

    This previously returned ``int(random.random() * time.time_ns() // 1_000_000)``.
    ``random.random()`` is the Mersenne Twister, which is not a cryptographically
    secure generator -- its entire 19937-bit state can be recovered from 624
    consecutive outputs, after which every future salt is predictable -- and the
    millisecond clock it was multiplied by is close to public knowledge.
    ``secrets`` draws from the operating system CSPRNG and needs no clock input.
    """
    return str(secrets.randbits(SALT_BITS))
