"""Pure-Python Curve StableSwap invariant and exact-input quote estimates."""

from __future__ import annotations

import math


def get_D(balances: list[float], amp: float) -> float:
    n = len(balances)
    total = sum(balances)
    if n < 2 or total <= 0 or amp <= 0 or any(x <= 0 for x in balances):
        raise ValueError("Pool balances and Curve A must be positive")
    d = total
    ann = amp * n
    for _ in range(255):
        d_product = d
        for balance in balances:
            d_product = d_product * d / (balance * n)
        previous = d
        d = (ann * total + d_product * n) * d / ((ann - 1) * d + (n + 1) * d_product)
        if not math.isfinite(d):
            raise ValueError("StableSwap invariant did not converge")
        if abs(d - previous) <= 1e-12 * max(1.0, d):
            return d
    return d


def get_y(i: int, j: int, x: float, balances: list[float], amp: float) -> float:
    n = len(balances)
    d = get_D(balances, amp)
    ann = amp * n
    c, subtotal = d, 0.0
    for k, balance in enumerate(balances):
        if k == j:
            continue
        value = x if k == i else balance
        subtotal += value
        c = c * d / (value * n)
    c = c * d / (ann * n)
    b = subtotal + d / ann
    y = d
    for _ in range(255):
        previous = y
        y = (y * y + c) / (2 * y + b - d)
        if not math.isfinite(y):
            raise ValueError("StableSwap quote did not converge")
        if abs(y - previous) <= 1e-12 * max(1.0, y):
            return y
    return y


def quote_swap(snapshot: dict, input_index: int, output_index: int, amount: float,
               liquidity_scale: float = 1.0) -> dict:
    amp, fee = float(snapshot["amp"]), float(snapshot["fee_rate"])
    balances = [float(snapshot[key]) * liquidity_scale for key in ("dai_pool", "usdc_pool", "usdt_pool")]
    if input_index == output_index or input_index not in range(3) or output_index not in range(3):
        raise ValueError("Input and output pool tokens must be different valid indices")
    if amount <= 0 or amount > balances[input_index] * 1_000_000:
        raise ValueError("Sell amount is outside the supported quote range")
    epsilon = max(1e-7, min(1.0, amount * 1e-6))
    spot_y = get_y(input_index, output_index, balances[input_index] + epsilon, balances, amp)
    marginal = (balances[output_index] - spot_y) / epsilon
    final_y = get_y(input_index, output_index, balances[input_index] + amount, balances, amp)
    gross_out = max(0.0, balances[output_index] - final_y)
    net_out = gross_out * (1 - fee)
    if marginal <= 0:
        raise ValueError("The marginal pool quote is not positive")
    return {
        "marginal_quote_output_per_input_gross": marginal,
        "gross_output": gross_out,
        "net_output": net_out,
        "average_execution_price_net": net_out / amount,
        "price_impact_ex_fee_pct": max(0.0, (marginal - gross_out / amount) / marginal * 100),
        "fee_amount": gross_out - net_out,
        "fee_rate": fee,
        "amp_curve_A": amp,
    }


def quote_usdc_to_usdt(snapshot: dict, amount: float, liquidity_scale: float = 1.0) -> dict:
    result = quote_swap(snapshot, 1, 2, amount, liquidity_scale)
    result["marginal_quote_usdt_per_usdc_gross"] = result.pop("marginal_quote_output_per_input_gross")
    result["gross_usdt_out"] = result.pop("gross_output")
    result["net_usdt_out"] = result.pop("net_output")
    result["fee_usdt"] = result.pop("fee_amount")
    return result
