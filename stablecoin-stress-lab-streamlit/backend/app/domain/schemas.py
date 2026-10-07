from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PoolSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str
    dai_pool: float = Field(gt=0)
    usdc_pool: float = Field(gt=0)
    usdt_pool: float = Field(gt=0)
    amp: float = Field(gt=0, description="Curve 3pool A() value, used directly by the invariant")
    fee_rate: float = Field(ge=0, lt=1)
    source: str = Field(min_length=1)
    method: str = Field(min_length=1)

    @field_validator("timestamp")
    @classmethod
    def require_utc_timestamp(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("timestamp must be ISO 8601 with a timezone") from None
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    @field_validator("source", "method")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source and method are required")
        return value.strip()


class PoolSnapshotImport(BaseModel):
    snapshots: list[PoolSnapshot] = Field(min_length=1, max_length=10000)


class QuoteRequest(BaseModel):
    date: date
    sell_amount_usdc: float = Field(gt=0, le=1_000_000_000_000)
    liquidity_increase_pct: float = Field(default=30, ge=0, le=500)


class AgentExperimentRequest(BaseModel):
    date: date
    stress_asset: str = Field(default="USDC", pattern="^(USDC|USDT)$")
    duration_hours: int = Field(default=72, ge=1, le=168)
    redemption_pressure_pct: float = Field(default=5, ge=0, le=50)
    circulating_supply_usdc: float = Field(default=1_000_000_000, gt=0, le=1e13)
    pool_liquidity_multiplier: float = Field(default=1, ge=0.1, le=5)
    retail_share_pct: float = Field(default=60, ge=0, le=100)
    whale_share_pct: float = Field(default=30, ge=0, le=100)
    arbitrageur_share_pct: float = Field(default=10, ge=0, le=100)
    arbitrage_capital_usd: float = Field(default=5_000_000, ge=0, le=1e11)
    gas_cost_usd: float = Field(default=30, ge=0, le=10000)
    cash_reserve_ratio_pct: float = Field(default=10, ge=0, le=100)
    reserve_settlement_hours: int = Field(default=24, ge=1, le=168)
    weekend_bank_friction: bool = True
    treasury_protocol_mode: bool = False
    frozen_reserve_pct: float = Field(default=0, ge=0, le=100)
    freeze_release_hours: int = Field(default=48, ge=1, le=168)
    credit_rating: str = Field(default="AAA", pattern="^(AAA|AA|A|BBB|BB|B)$")
    collateral_exposure_pct: float = Field(default=0, ge=0, le=100)
    collateral_impairment_pct: float = Field(default=0, ge=0, le=100)
    credit_event_mode: str = Field(default="forced", pattern="^(forced|sampled)$")
    credit_base_annual_pd_pct: float = Field(default=1, ge=0, le=100)
    random_seed: int = Field(default=42, ge=0, le=2147483647)
    shock_hour: int = Field(default=1, ge=1, le=168)
    base_risk_free_rate_pct: float = Field(default=4, ge=0, le=30)
    rate_shock_bps: float = Field(default=0, ge=-2000, le=2000)
    rate_ramp_hours: int = Field(default=12, ge=1, le=168)
    asset_duration_years: float = Field(default=0.25, ge=0, le=20)
    treasury_asset_share_pct: float = Field(default=80, ge=0, le=100)
    defi_yield_pct: float = Field(default=3, ge=-10, le=50)
    stablecoin_yield_pct: float = Field(default=0, ge=-10, le=50)
    yield_chaser_share_pct: float = Field(default=0, ge=0, le=50)
    yield_response_pct: float = Field(default=50, ge=0, le=100)
    yield_switch_cost_bps: float = Field(default=10, ge=0, le=1000)
    yield_holding_days: int = Field(default=30, ge=1, le=365)
    lp_max_withdrawal_pct: float = Field(default=0, ge=0, le=90)
    lp_risk_threshold_bps: float = Field(default=100, ge=0, le=5000)
    lp_response_pct: float = Field(default=50, ge=0, le=100)
    initial_liquidity_increase_pct: float = Field(default=0, ge=0, le=500)
    holder_sell_amount_usdc_per_hour: float = Field(default=250_000, ge=0, le=100_000_000)
    holder_panic: float = Field(default=50, ge=0, le=100)
    redemption_cost_bps: float = Field(default=0, ge=0, le=1000)
    redemption_share_pct: float = Field(default=25, ge=0, le=100)
    arbitrage_response_pct: float = Field(default=50, ge=0, le=100)
    arbitrage_threshold_bps: float = Field(default=10, ge=0, le=1000)
    issuer_delay_hours: int = Field(default=6, ge=0, le=168)
    issuer_capacity_usdc_per_hour: float = Field(default=250_000, ge=0, le=100_000_000)


    @field_validator("arbitrageur_share_pct")
    @classmethod
    def valid_distribution(cls, value, info):
        if abs(info.data.get("retail_share_pct", 60) + info.data.get("whale_share_pct", 30) + value - 100) > 0.001:
            raise ValueError("Participant shares must sum to 100%")
        return value


class QuoteEstimate(BaseModel):
    marginal_quote_usdt_per_usdc_gross: float
    gross_usdt_out: float
    net_usdt_out: float
    average_execution_price_net: float
    price_impact_ex_fee_pct: float
    fee_usdt: float
    fee_rate: float
    amp_curve_A: float
    input_usd_at_daily_close_reference: float | None = None
    output_usd_at_daily_close_reference: float | None = None
    usd_proceeds_change_pct_vs_daily_close_references: float | None = None


class QuoteResponse(BaseModel):
    date: date
    snapshot: PoolSnapshot
    snapshot_status: str
    historical_model_estimate: QuoteEstimate
    counterfactual_model_estimate: QuoteEstimate
    sell_amount_usdc: float
    liquidity_increase_pct: float
    interpretation: str


class HistoryResponse(BaseModel):
    prices: list[dict[str, Any]]
    events: list[dict[str, Any]]
    sources: list[dict[str, Any]]


class PortfolioRequest(BaseModel):
    date: date
    usdc_amount: float = Field(default=1_000_000, ge=0, le=1e10)
    usdt_amount: float = Field(default=500_000, ge=0, le=1e10)
    scenario: str = Field(default="bank_freeze", pattern="^(bank_freeze|run_lp|rate_hike)$")
    duration_hours: int = Field(default=72, ge=6, le=168)
    panic_pct: float = Field(default=70, ge=0, le=100)
    cash_ratio_pct: float = Field(default=10, ge=0, le=100)
    issuer_delay_hours: int = Field(default=12, ge=0, le=168)
    frozen_reserve_pct: float = Field(default=20, ge=0, le=100)
    rate_shock_bps: float = Field(default=0, ge=-2000, le=2000)
    lp_withdrawal_pct: float = Field(default=0, ge=0, le=90)
    treasury_duration_years: float = Field(default=.25, ge=0, le=20)
    treasury_yield_pct: float = Field(default=4, ge=-10, le=50)
