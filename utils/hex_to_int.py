# utils/hex_to_int.py

def hex_to_int(hex: str) -> int:
    hex = hex.replace("0x", "").replace("#", "")
    if not len(hex) == 6:
        return -1
    
    try:
        return int(hex, 16)
    except ValueError:
        return -2


def int_to_hex(number: int) -> str:
    if not number >= 0:
        pass