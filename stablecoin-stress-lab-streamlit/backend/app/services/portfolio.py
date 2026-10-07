"""Retail scenario estimates: not VaR, calibrated forecasts or executable prices."""
from backend.app.domain.schemas import AgentExperimentRequest, PortfolioRequest
from backend.app.services.agents import simulate_agents
from backend.app.services.replay import pool_snapshot_for_date
from backend.app.data_sources.prices import load_prices
from backend.app.domain.stable_swap import quote_swap


def portfolio_stress(req: PortfolioRequest):
    snapshot = pool_snapshot_for_date(req.date)
    if snapshot is None:
        raise LookupError('Choose a date with an exact historical pool snapshot.')
    prices={r['asset']:float(r['close_usd']) for r in load_prices() if r['date_utc']==req.date.isoformat()}
    if not {'USDC','USDT'}.issubset(prices): raise LookupError('Both independent USD prices are required.')
    if req.usdc_amount+req.usdt_amount<=0: raise ValueError('Enter a positive holding in at least one asset.')
    base=dict(date=req.date,duration_hours=req.duration_hours,treasury_protocol_mode=True,
      holder_panic=req.panic_pct,cash_reserve_ratio_pct=req.cash_ratio_pct,
      issuer_delay_hours=req.issuer_delay_hours,frozen_reserve_pct=req.frozen_reserve_pct,
      rate_shock_bps=req.rate_shock_bps,lp_max_withdrawal_pct=req.lp_withdrawal_pct,
      treasury_asset_share_pct=0,asset_duration_years=0,stablecoin_yield_pct=0,
      yield_chaser_share_pct=10,yield_response_pct=50,base_risk_free_rate_pct=4,defi_yield_pct=3,
      redemption_pressure_pct=10 if req.scenario=='run_lp' else 5)
    models={asset:simulate_agents(AgentExperimentRequest(**base,stress_asset=asset)) for asset in ['USDC','USDT']}
    treasury=simulate_agents(AgentExperimentRequest(**{**base,'treasury_asset_share_pct':80,
      'asset_duration_years':req.treasury_duration_years,'stablecoin_yield_pct':req.treasury_yield_pct},stress_asset='USDC'))
    amounts={'USDC':req.usdc_amount,'USDT':req.usdt_amount}
    marks=[]
    start=sum(amounts[a]*prices[a] for a in amounts)
    for i in range(req.duration_hours):
        mark=sum(amounts[a]*models[a]['steps'][i]['pool_implied_usdc_usd_after_agents'] for a in amounts)
        marks.append({'hour':i+1,'modeled_portfolio_usd':mark,'change_vs_historical_reference_usd':mark-start})
    # Independent token stress runs: no joint price dynamics or covariance are inferred.
    marks.insert(0,{'hour':0,'modeled_portfolio_usd':sum(amounts[a]*models[a]['initial_pool_implied_usdc_usd'] for a in amounts)})
    peak=start; max_drawdown=0
    for row in marks:
        peak=max(peak,row['modeled_portfolio_usd']);max_drawdown=max(max_drawdown,peak-row['modeled_portfolio_usd'])
    sales=[]
    for asset,amount in amounts.items():
        if amount==0:continue
        output='USDT' if asset=='USDC' else 'USDC'
        q=quote_swap(snapshot,1 if asset=='USDC' else 2,2 if asset=='USDC' else 1,amount)
        sales.append({'asset':asset,'input_tokens':amount,'output_asset':output,
          'output_tokens_net':q['net_output'],'output_usd_daily_reference':q['net_output']*prices[output],
          'price_impact_ex_fee_pct':q['price_impact_ex_fee_pct'],'pool_fee_output_tokens':q['fee_amount'],
          'reference_value_difference_usd':amount*prices[asset]-q['net_output']*prices[output]})
    return dict(label='HYPOTHETICAL PORTFOLIO STRESS · NOT VaR OR A FORECAST',request=req.model_dump(mode='json'),
      snapshot=snapshot,independent_daily_usd_prices=prices,reference_portfolio_usd=start,
      maximum_mark_loss_vs_reference_usd=max(0,start-min(r['modeled_portfolio_usd'] for r in marks)),
      maximum_path_drawdown_usd=max_drawdown,portfolio_path=marks,independent_sale_estimates=sales,
      asset_scenarios={a:{'summary':r['summary'],'steps':r['steps'],'initial_price':r['initial_pool_implied_usdc_usd'],
        'assumptions':r['assumptions']} for a,r in models.items()},
      comparison={'conventional_usdc':{'summary':models['USDC']['summary'],'steps':models['USDC']['steps'],'assumptions':models['USDC']['assumptions']},
                  'hypothetical_treasury_token':{'summary':treasury['summary'],'steps':treasury['steps'],'assumptions':treasury['assumptions']}},
      interpretation='USDC and USDT are stressed independently on mirrored historical pool templates and combined as a synthetic portfolio path; this is not a jointly consistent market model. Daily historical USD references differ in time from the pool block. Losses are mark estimates, not realized losses. Sale quotes are separate what-if trades on the original snapshot; do not add their differences to mark loss. Issuer queue metrics describe the modeled protocol cohort, not your personal queue position. Treasury comparison is hypothetical, uncalibrated and not evidence of product superiority.')


def risk_workflow(req: PortfolioRequest):
    """Tool-backed orchestration inspired by FinAgent; no LLM or trained predictor."""
    import uuid
    from datetime import datetime, timezone
    run_id=str(uuid.uuid4())
    stages=[]
    def record(role, status, message):
        stages.append(dict(role=role,status=status,message=message,time_utc=datetime.now(timezone.utc).isoformat()))
    record('Planner','complete','Use the user-selected scenario and explicit parameters; no autonomous trading decision.')
    record('Data checker','running','Require exact-date pool snapshot and both independent USD references.')
    result=portfolio_stress(req)
    record('Data checker','complete',f"Snapshot {result['snapshot']['timestamp']}; daily references can differ in time from the pool block.")
    record('Scenario runner','complete','Python ran independent USDC/USDT scenarios, historical sale estimates and hypothetical Treasury comparison.')
    warnings=[result['interpretation'], 'Model is deterministic and uncalibrated; no VaR confidence level or probability of safety is estimated.']
    if result['maximum_mark_loss_vs_reference_usd']>result['reference_portfolio_usd']:
        warnings.append('Reported loss exceeds reference value: inspect model output before use.')
    pending={a:v['summary']['issuer_redemptions_still_pending'] for a,v in result['asset_scenarios'].items()}
    record('Audit checker','complete','Separated marks, original-pool sale quotes and protocol cohort queues; no personal settlement ETA inferred.')
    report=[
        f"Under your {req.scenario.replace('_',' ')} assumptions, maximum modeled mark loss against historical daily reference value is ${result['maximum_mark_loss_vs_reference_usd']:,.2f}.",
        'This is a hypothetical mark change, not a realized loss or a prediction.',
        'Sale estimates use the original historical snapshot, not the stressed trough. Do not add sale differences to the mark loss.',
        f"At hour {req.duration_hours}, modeled cohort requests still pending: USDC {pending['USDC']:,.0f} tokens; USDT {pending['USDT']:,.0f} tokens. These are not your personal pending redemptions.",
        'Explore sensitivity by changing one assumption at a time, especially cash availability, delay and LP withdrawal.']
    record('Report writer','complete','Generated a fixed-template explanation from numerical results; no LLM-generated investment advice.')
    return dict(run_id=run_id,label='AUDITABLE RISK WORKFLOW · PAPER-INSPIRED ADAPTATION',
        engine='Deterministic Python workflow; no LLM connected',stages=stages,report=report,
        limitations=warnings,result=result)
