from backend.app.data_sources.prices import load_prices
from backend.app.domain.schemas import QuoteRequest
from backend.app.domain.stable_swap import quote_usdc_to_usdt
from backend.app.services.replay import pool_snapshot_for_date


def calculate_experiment(request: QuoteRequest) -> dict:
    snapshot = pool_snapshot_for_date(request.date)
    if snapshot is None:
        raise LookupError(f"No Curve 3pool snapshot is loaded for {request.date}. Import sourced pool balances for this date to calculate a historical estimate.")

    historical = quote_usdc_to_usdt(snapshot, request.sell_amount_usdc)
    simulated = quote_usdc_to_usdt(snapshot, request.sell_amount_usdc, 1 + request.liquidity_increase_pct / 100)
    refs = {
        row["asset"].upper(): float(row["close_usd"])
        for row in load_prices()
        if row["date_utc"] == request.date.isoformat() and row["asset"].upper() in {"USDC", "USDT"}
    }
    if "USDC" in refs and "USDT" in refs:
        input_usd = request.sell_amount_usdc * refs["USDC"]
        for result in (historical, simulated):
            output_usd = result["net_usdt_out"] * refs["USDT"]
            result["input_usd_at_daily_close_reference"] = input_usd
            result["output_usd_at_daily_close_reference"] = output_usd
            result["usd_proceeds_change_pct_vs_daily_close_references"] = (output_usd / input_usd - 1) * 100

    return {
        "date": request.date,
        "snapshot": snapshot,
        "snapshot_status": "onchain_source_metadata_present" if "Ethereum JSON-RPC" in snapshot["method"] and "block " in snapshot["source"] else "imported_snapshot_source_not_verified",
        "historical_model_estimate": historical,
        "counterfactual_model_estimate": simulated,
        "sell_amount_usdc": request.sell_amount_usdc,
        "liquidity_increase_pct": request.liquidity_increase_pct,
        "interpretation": "Model estimate conditional on the supplied historical snapshot and assumptions; the counterfactual is hypothetical, not history.",
    }
