"""Deterministic cohort ABM. All reserves, supply and behavior are assumptions."""
from datetime import datetime, timedelta, timezone
import math
import random
from backend.app.data_sources.prices import load_prices
from backend.app.domain.schemas import AgentExperimentRequest
from backend.app.domain.stable_swap import quote_swap
from backend.app.services.replay import pool_snapshot_for_date
TOKEN_FIELDS = ('dai_pool', 'usdc_pool', 'usdt_pool')


def simulate_agents(request: AgentExperimentRequest) -> dict:
    source = pool_snapshot_for_date(request.date)
    if source is None:
        raise LookupError(f'No exact-date historical Curve snapshot for {request.date}.')
    prices = {r['asset'].upper(): float(r['close_usd']) for r in load_prices()
              if r['date_utc'] == request.date.isoformat() and r['asset'].upper() in {'USDC', 'USDT'}}
    if len(prices) != 2:
        raise LookupError('Independent USD references are missing.')
    actual_source = dict(source)
    actual_prices = dict(prices)
    if request.stress_asset == 'USDT':
        source = {**source, 'usdc_pool':source['usdt_pool'], 'usdt_pool':source['usdc_pool']}
        prices = {'USDC':actual_prices['USDT'], 'USDT':actual_prices['USDC']}
    # Internal input/output indices are normalized; actual token identity is returned explicitly.
    scale = request.pool_liquidity_multiplier * (1 + request.initial_liquidity_increase_pct / 100)
    pool = {k: float(source[k]) * scale for k in TOKEN_FIELDS}
    pool.update(amp=float(source['amp']), fee_rate=float(source['fee_rate']))
    def quote(i, j, amount):
        return quote_swap(pool, i, j, amount)
    def swap(i, j, amount):
        q = quote(i, j, amount)
        pool[TOKEN_FIELDS[i]] += amount
        pool[TOKEN_FIELDS[j]] -= q['net_output']
        return q
    def spot():
        return quote(1, 2, 1_000_000)['marginal_quote_output_per_input_gross'] * prices['USDT']
    start = datetime.fromisoformat(source['timestamp'].replace('Z', '+00:00'))
    def bank_open(hour):
        return not request.weekend_bank_friction or (start + timedelta(hours=hour)).weekday() < 5
    supply = request.circulating_supply_usdc
    pressure = supply * request.redemption_pressure_pct / 100
    # Retail sells to Curve; whales request fiat redemption; arbitrageurs supply capital.
    retail_left = pressure * request.retail_share_pct / 100
    whale_left = pressure * request.whale_share_pct / 100
    arb_cash = request.arbitrage_capital_usd * request.arbitrageur_share_pct / 100
    cash = supply * request.cash_reserve_ratio_pct / 100
    illiquid = supply - cash
    queue, settlements, steps = [], [], []
    # This extension is a hypothetical Treasury protocol using USDC pool reserves as a proxy.
    yield_left = (supply - pressure) * request.yield_chaser_share_pct / 100
    yield_total = 0.0
    frozen_cash = frozen_illiquid = frozen_balance = 0.0
    losses = 0.0
    previous_duration_loss = 0.0
    lp_removed = 0.0
    previous_price = None
    credit_happened = False
    rating_multiplier = {'AAA':1,'AA':2,'A':4,'BBB':8,'BB':16,'B':32}[request.credit_rating]
    annual_pd = min(1, request.credit_base_annual_pd_pct / 100 * rating_multiplier)
    event_probability = 1 - (1-annual_pd) ** (request.duration_hours / (365*24))
    # Common draw and event hour across every phase cell; not empirically calibrated.
    rng = random.Random(request.random_seed)
    credit_draw = rng.random()
    sampled_event_hour = rng.randint(1, request.duration_hours)
    credit_hour = request.shock_hour if request.credit_event_mode == 'forced' else sampled_event_hour
    credit_occurs = request.credit_event_mode == 'forced' or credit_draw < event_probability
    def available_asset_loss(amount):
        nonlocal cash, illiquid, frozen_cash, frozen_illiquid, frozen_balance, losses
        buckets = [cash, illiquid, frozen_cash, frozen_illiquid]
        total = sum(buckets) + sum(amount for _, amount in settlements)
        actual = min(max(0, amount), total)
        if total > 0:
            factor = 1-actual/total
            cash, illiquid, frozen_cash, frozen_illiquid = [b*factor for b in buckets]
            settlements[:] = [(due, amount*factor) for due, amount in settlements]
        frozen_balance = frozen_cash+frozen_illiquid
        losses += actual
        return actual
    payout = 1.0
    total_sold = total_arb = total_requested = total_redeemed = fallback_total = 0.0
    initial_price = spot()
    pending_sales = 0.0
    for hour in range(1, request.duration_hours + 1):
        bank = bank_open(hour)
        progress = min(1, max(0, hour-request.shock_hour+1) / request.rate_ramp_hours)
        risk_free = max(0, request.base_risk_free_rate_pct + request.rate_shock_bps/100*progress)
        if request.treasury_protocol_mode:
            # First-order duration mark-to-market, stressed once along a ramp; gains ignored conservatively.
            duration_loss = supply * request.treasury_asset_share_pct/100 * min(1, request.asset_duration_years * max(0, risk_free-request.base_risk_free_rate_pct)/100)
            available_asset_loss(max(0,duration_loss-previous_duration_loss))
            previous_duration_loss = duration_loss
            if hour == credit_hour and credit_occurs:
                severity = min(1, request.collateral_impairment_pct/100 * math.sqrt(rating_multiplier))
                available_asset_loss(supply * request.collateral_exposure_pct/100 * severity)
                credit_happened = request.collateral_exposure_pct > 0 and severity > 0
            if hour == request.shock_hour:
                fraction = request.frozen_reserve_pct / 100
                frozen_cash, frozen_illiquid = cash*fraction, illiquid*fraction
                cash -= frozen_cash; illiquid -= frozen_illiquid
                frozen_balance = frozen_cash+frozen_illiquid
            if hour >= request.shock_hour+request.freeze_release_hours and bank and frozen_balance > 0:
                cash += frozen_cash; illiquid += frozen_illiquid
                frozen_cash = frozen_illiquid = frozen_balance = 0.0
            payout = max(0.01,1-losses/supply)
        # Yield chasers compare net annualized returns over a chosen holding period.
        best_onchain = max(request.defi_yield_pct, request.stablecoin_yield_pct)
        net_yield_gap = max(0,risk_free-best_onchain-request.yield_switch_cost_bps/100*365/request.yield_holding_days)
        yield_request = 0.0
        if request.treasury_protocol_mode and net_yield_gap > 0:
            yield_request = min(yield_left, yield_left * request.yield_response_pct/100 * min(1, net_yield_gap/5))
            yield_left -= yield_request; yield_total += yield_request
            queue.append({'due':hour+request.issuer_delay_hours,'amount':yield_request,'arb':False,'created':hour})
            total_requested += yield_request
        # Strategic LPs proportionally withdraw all assets; removal reduces depth, not spot directly.
        current_price = spot()
        volatility = abs(current_price-(previous_price if previous_price is not None else current_price))
        risk_bps = (abs(1-current_price)+volatility)*10000
        withdrawal = 0.0
        if request.treasury_protocol_mode and risk_bps > request.lp_risk_threshold_bps:
            remaining_budget = request.lp_max_withdrawal_pct/100-lp_removed
            withdrawal = max(0,remaining_budget) * request.lp_response_pct/100 * min(1,(risk_bps-request.lp_risk_threshold_bps)/1000)
            if withdrawal > 0:
                fraction = withdrawal / (1-lp_removed)
                for k in TOKEN_FIELDS: pool[k] *= 1-fraction
                lp_removed += withdrawal
        previous_price = current_price
        if bank:
            for due, amount in list(settlements):
                if due <= hour:
                    cash += amount
                    settlements.remove((due, amount))
        # A bounded 12-hour cohort exit wave; panic speeds retail sales.
        retail = min(retail_left, pressure * request.retail_share_pct / 100 / 12 * (0.25 + request.holder_panic / 100 * 1.5 + max(0, 1-spot()) * 5))
        retail_left -= retail
        whale = min(whale_left, pressure * request.whale_share_pct / 100 / 12)
        whale_left -= whale
        queue.append({'due': hour + request.issuer_delay_hours, 'amount': whale, 'arb': False, 'created': hour})
        total_requested += whale
        # Request liquid reserve settlement once shortage appears; never fabricate cash.
        queued = sum(q['amount'] for q in queue)
        if queued*payout > cash + sum(a for _, a in settlements) and illiquid > 0:
            release = min(illiquid, queued*payout - cash - sum(a for _, a in settlements))
            illiquid -= release
            settlements.append((hour + request.reserve_settlement_hours, release))
        capacity = request.issuer_capacity_usdc_per_hour if bank else 0
        redeemed = fallback = 0.0
        for q in queue:
            if q['due'] <= hour:
                done = min(q['amount'], capacity, cash / payout)
                q['amount'] -= done; capacity -= done; cash -= done*payout; redeemed += done
                if q['arb']: arb_cash += done*payout
                elif q['amount'] > 0 and hour - q['due'] >= 24:
                    # Institutions wait for fiat; do not assume forced sales.
                    pass
        queue = [q for q in queue if q['amount'] > 1e-8]
        total_redeemed += redeemed
        pending_sales += retail
        sell = min(pending_sales, pool['usdc_pool'] * .2)
        pending_sales -= sell
        sale = swap(1, 2, sell) if sell > 1e-7 else None
        total_sold += sell
        before = spot(); arb_amount = 0.0; direction = 'none'
        # Buy discounted USDC with finite capital, then queue fiat redemption.
        response = request.arbitrage_response_pct / 100
        budget = min(arb_cash / prices['USDT'], pool['usdt_pool'] * .05 * response)
        if before < payout - request.arbitrage_threshold_bps / 10000 and budget > 1:
            arb_q = quote(2, 1, budget)
            profit = arb_q['net_output']*payout - budget * prices['USDT'] - request.gas_cost_usd
            if profit > 0 and arb_cash >= budget * prices['USDT'] + request.gas_cost_usd:
                swap(2, 1, budget)
                arb_cash -= budget * prices['USDT'] + request.gas_cost_usd
                acquired = arb_q['net_output']
                queue.append({'due': hour + request.issuer_delay_hours, 'amount': acquired, 'arb': True, 'created': hour})
                total_requested += acquired
                arb_amount = budget; total_arb += budget; direction = 'buy USDC → queued fiat redemption'
        price = spot()
        steps.append(dict(hour=hour, holder_usdc_demand=retail+whale, holder_usdc_sold_to_pool=sell,
            holder_trade_price_impact_pct=sale['price_impact_ex_fee_pct'] if sale else 0,
            issuer_redemption_requested=whale, issuer_redemption_processed=redeemed,
            issuer_redemption_pending=sum(q['amount'] for q in queue), issuer_redemption_fallback_to_pool=fallback,
            arbitrage_direction=direction, arbitrage_input_amount=arb_amount,
            arbitrage_price_gap_before_pct=(before-1)*100,
            pool_usdt_per_usdc_after_agents=price/prices['USDT'], pool_implied_usdc_usd_after_agents=price,
            depeg_depth_pct=max(0,1-price)*100, cash_buffer_usd=cash,
            risk_free_rate_pct=risk_free, defi_yield_pct=request.defi_yield_pct,
            stablecoin_yield_pct=request.stablecoin_yield_pct,
            yield_redemption_requested=yield_request, yield_inventory_remaining=yield_left,
            lp_cumulative_withdrawal_pct=lp_removed*100, lp_step_withdrawal_pct=withdrawal*100,
            frozen_reserve_usd=frozen_balance, collateral_loss_usd=losses,
            assumed_redemption_value_usd=payout,
            arbitrage_cash_usd=arb_cash, bank_open=bank, unexecuted_retail_usdc=pending_sales,
            **{k:pool[k] for k in TOKEN_FIELDS}))
    curve = [initial_price] + [s['pool_implied_usdc_usd_after_agents'] for s in steps]
    peak = min(range(len(curve)), key=lambda i: curve[i])
    recovery = next((i for i in range(peak,len(curve)-5) if all(abs(v-1)<=.01 for v in curve[i:i+6])), None)
    return dict(date=request.date, simulation_label='COUNTERFACTUAL COHORT ABM · NOT HISTORICAL OBSERVATION',
        stress_asset=request.stress_asset, historical_snapshot={**actual_source,'provenance_status':'onchain_source_metadata_present' if 'Ethereum JSON-RPC' in source['method'] else 'imported_snapshot_source_not_verified'},
        independent_usd_reference=actual_prices, modeled_asset_usd_reference=prices["USDC"], initial_pool_implied_usdc_usd=initial_price,
        assumptions=request.model_dump(mode='json'),
        agent_rules={'retail':'Finite panic-sensitive exit wave; excess sell demand waits for next step.',
          'whale':'Finite cohort requests 1:1 fiat redemption and waits in FIFO queue.',
          'arbitrageur':'Finite USD capital weighted by cohort share; positive net profit after pool fee and gas required; acquired USDC queues for redemption; capital returns only on settlement.',
          'issuer':'Hypothetical cash buffer and delayed liquid reserve settlement; FIFO hourly capacity; weekend UTC banking closure blocks settlement. No actual issuer reserves inferred.',
          'yield_chaser':'Finite additional holder inventory outside the initial exit wave; compare max(DeFi APY, token APY) with T-bill APY net of holding-period switching cost; issuer FIFO redemption, not DEX price arbitrage.',
          'strategic_lp':'Remove all three pool reserves proportionally under quote-deviation/volatility risk, bounded by configured total withdrawal fraction; no LP deposits modeled.',
          'macro':'Treasury proxy mode only: duration loss approximation D × positive rate change × Treasury exposure; credit impairment under forced or seeded hazard scenario; frozen reserves return after delay. User rating multipliers are illustrative and uncalibrated.',
          'recovery':'First hour after deepest discount within 1% of $1 for six consecutive samples; null means not recovered within horizon. $1 is an assumed future redemption anchor, not a forecast.'},
        summary=dict(total_holder_usdc_sold_to_pool=total_sold,total_arbitrage_input_volume=total_arb,
          total_issuer_redemptions_requested=total_requested,total_issuer_redemptions_processed=total_redeemed,
          total_issuer_redemptions_fallback_to_pool=fallback_total,issuer_redemptions_still_pending=sum(q['amount'] for q in queue),
          ending_pool_usdt_per_usdc=curve[-1]/prices['USDT'],ending_pool_implied_usdc_usd=curve[-1],
          ending_pool_balances={k:pool[k] for k in TOKEN_FIELDS},max_depeg_depth_pct=max(0,1-min(curve))*100,
          max_move_from_initial_pct=max(abs(v-initial_price) for v in curve)*100,
          max_premium_pct=max(0,max(curve)-1)*100,
          max_absolute_deviation_pct=max(abs(v-1) for v in curve)*100,
          initial_pool_implied_usdc_usd=initial_price,
          total_yield_redemptions_requested=yield_total,lp_cumulative_withdrawal_pct=lp_removed*100,
          collateral_loss_usd=losses, ending_frozen_reserve_usd=frozen_balance,
          ending_redemption_value_usd=payout,credit_event_occurred=credit_happened,
          assumed_credit_event_probability_pct=event_probability*100,
          stress_asset_label='Hypothetical Treasury token (USDC reserve proxy)' if request.treasury_protocol_mode else request.stress_asset,
          recovery_hour=recovery,recovery_hours_after_trough=None if recovery is None else recovery-peak,
          trough_hour=peak,unexecuted_retail_usdc=pending_sales,unactivated_retail_usdc=retail_left,
          unactivated_whale_usdc=whale_left),steps=steps)


def phase_diagram(request: AgentExperimentRequest) -> dict:
    cells = []
    for depth in [.25,.5,1,1.5,2,3]:
        for pressure in [0,1,3,5,10,20,30]:
            scenario = request.model_copy(update={'pool_liquidity_multiplier':depth,'redemption_pressure_pct':pressure})
            result = simulate_agents(scenario)
            cells.append(dict(liquidity_multiplier=depth,redemption_pressure_pct=pressure,**{k:result['summary'][k] for k in ['max_depeg_depth_pct','max_premium_pct','max_absolute_deviation_pct','max_move_from_initial_pct','recovery_hour','recovery_hours_after_trough']}))
    return {'simulation_label':'SIMULATED PHASE DIAGRAM · NOT HISTORY','cells':cells,'assumptions':request.model_dump(mode='json')}
