import random
import time


def generate_order_salt() -> str:
    return str(int(random.random() * (time.time_ns() // 1_000_000)))
