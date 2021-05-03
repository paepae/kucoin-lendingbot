from decimal import Decimal


def round_down_to_decimal_places(value: Decimal, decimal_places: int) -> Decimal:
    return Decimal(round_down_to_decimal_places_string(value, decimal_places))


def round_down_to_decimal_places_string(value: Decimal, decimal_places: int) -> str:
    value_str = str(value)

    separator_index = value_str.rfind(".")
    if separator_index == -1:
        if decimal_places == 0:
            return value_str
        return value_str + "." + ("0" * decimal_places)

    if decimal_places == 0:
        return value_str[:separator_index]

    current_precision = len(value_str) - separator_index - 1
    if current_precision < decimal_places:
        return value_str + ("0" * (decimal_places - current_precision))

    return value_str[:separator_index + decimal_places + 1]
