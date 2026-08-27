from decimal import Decimal


_CURRENCY_EXPONENT = {"CNY": 2}


def decimal_to_minor(amount: Decimal, currency: str) -> int:
    """Convert an exact decimal amount to the currency's smallest unit."""

    normalized_currency = currency.strip().upper()
    exponent = _CURRENCY_EXPONENT.get(normalized_currency)
    if exponent is None:
        raise ValueError(f"不支持的币种: {normalized_currency}")

    quantum = Decimal(1).scaleb(-exponent)
    normalized_amount = Decimal(amount)
    quantized = normalized_amount.quantize(quantum)
    if quantized != normalized_amount:
        raise ValueError(f"{normalized_currency} 金额最多支持 {exponent} 位小数")
    if quantized < 0:
        raise ValueError("金额不能为负数")

    minor = quantized * (10**exponent)
    integral = minor.to_integral_value()
    if minor != integral:
        raise ValueError("金额无法转换为最小货币单位")
    return int(integral)
