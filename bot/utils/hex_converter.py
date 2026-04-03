# utils/hex_to_int.py
import asyncio


def hex_to_int( hexcode: str) -> int:
    hexcode = hexcode.replace( "0x", "").replace( "#", "")
    if not len( hexcode) == 6:
        raise ValueError(f"{hexcode} must have 6 hexa-decimal values for hex color code.")
    
    return int( hexcode, 16)


def int_to_hex( number: int) -> str:
    if not ( 0 <= number < 16**6): # Range of Hexcode (0x000000 - 0xFFFFFF)
        raise ValueError(f"{number} outside range of hex color code")

    hexcode = hex( number).replace("0x", "")
    length = len(hexcode)

    for _i in range( length, 6):
        hexcode = "0" + hexcode

    return hexcode


print( int_to_hex( int( input( "Enter number: "))))
    