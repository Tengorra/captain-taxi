"""Simple discount code generator for minor complaint resolutions."""

import random
import string


def generate_discount_code(prefix: str = "SORRY", length: int = 4) -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{suffix}"
