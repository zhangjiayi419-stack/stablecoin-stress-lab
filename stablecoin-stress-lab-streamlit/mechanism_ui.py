"""Mechanism research workspace with explicitly synthetic collateral books."""
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from mechanism_engine import Pool, default_config, default_positions, simulate, collateral_at_risk
from terminal_charts import show, lines


def render_mechanism_lab():
    st.markdown('<div class="eyebrow">05 / Connected mechanisms</div>',unsafe_allow_html=True)
    st.title('Mechanism Lab')
    st.write('Compare liquidity curves. Trace forced sales and capital-constrained recovery, one model block at a time.')
    st.info('Synthetic research sandbox. Two-token pools start balanced at USD 1. All depths, tick ranges, lending accounts and oracle behavior below are assumptions, not live protocol measurements.')
    curves,dynamics=st.tabs(['AMM curve comparison','Cascade & recovery'])
    with curves:
        a,b,c=st.columns(3)
        depth=a.number_input('Equal starting pool value (USD)',1e5,1e9,20e6,step=1e6)
        amp=b.slider('Curve amplification A',1,1000,100)
        ticks=c.slider('v3 inner range (± ticks)',10,1000,200,step=10)
        rows=[]
        for kind in ('Curve','Uniswap v2','Uniswap v3'):
            for fraction in [0,.001,.005,.01,.02,.05,.1,.2,.3,.4,.6]:
                pool=Pool(kind,depth,amp,narrow_ticks=ticks)
                output,filled=pool.trade(depth*fraction)
                rows.append(dict(AMM=kind,sell_pct=fraction*100,price=pool.price(),average_price=output/filled if filled else 1.,filled_tokens=filled,requested_tokens=depth*fraction,unfilled_tokens=depth*fraction-filled))
        df=pd.DataFrame(rows);fig=go.Figure()
        for kind,g in df.groupby('AMM',sort=False):
            fig.add_trace(go.Scatter(x=g.sell_pct,y=g.price,name=kind,mode='lines+markers',customdata=g[['unfilled_tokens']].values,hovertemplate='%{y:.6f} USD<br>Unfilled: %{customdata[0]:,.0f}<extra>%{fullData.name}</extra>'))
        fig.update_layout(xaxis_title='Requested sale / initial pool value (%)',yaxis_title='Post-sale marginal USD quote')
        show(fig,key='amm_compare')
        st.caption('Same initial marked value and 4 bps fee, different liquidity shapes. v3 allocates 80% of value to the selected ±tick range and 20% to ±2000 ticks. Orders stop at the outer boundary; a flat endpoint can indicate exhausted liquidity, not successful execution. USD-1 numeraire and unit token rates are assumed.')
        with st.expander('Execution fills, tick boundaries & invariant definitions'):
            st.dataframe(df,hide_index=True,width='stretch')
            st.write('Curve: two-token StableSwap numerical invariant with A × n convention. Uniswap v2: x × y = k on fee-adjusted input. Uniswap v3: integrate Δx = L × (1/√P₂ − 1/√P₁), Δy = L × (√P₂ − √P₁) across tick-aligned range boundaries, updating active L. Floating-point approximations; no contract integer rounding, tick-spacing validation or historical tick map is reproduced.')
            st.download_button('Download curve comparison',df.to_csv(index=False),'amm-comparison.csv','text/csv')
    with dynamics:
        c=default_config()
        with st.form('connected_mechanisms'):
            left,right=st.columns(2)
            c['kind']=left.selectbox('Pool mechanism',['Curve','Uniswap v2','Uniswap v3'])
            c['depth']=right.number_input('Starting pool value (USD)',1e5,1e9,20e6,step=1e6)
            c['amp']=amp;c['narrow_ticks']=ticks
            c['sell_tokens']=left.number_input('Holder sale wave (tokens)',0.,1e9,8e6,step=1e6)
            c['blocks']=right.slider('Simulation horizon (blocks)',20,240,80,step=10)
            c['arb_capital']=left.number_input('Arbitrage capital (USD)',0.,1e9,2e6,step=1e6)
            c['liquidator_capital']=right.number_input('Liquidator working capital (USD)',0.,1e9,1e6,step=1e6)
            with st.expander('Execution, LP and oracle assumptions'):
                a,b=st.columns(2)
                c['lp_max']=a.slider('Maximum LP withdrawal (%)',0,90,60)/100
                c['lp_speed']=b.slider('LP response to discount',0.,10.,2.,step=.5)
                c['lp_acceleration']=a.slider('LP withdrawal momentum',0.,.95,.5,step=.05)
                c['lp_trigger']=b.slider('LP trigger below peg (bps)',0,500,50,step=10)/10000
                c['redemption_delay']=a.slider('Redemption settlement delay (blocks)',1,120,15)
                c['funding_apr']=b.slider('Arbitrage funding APR (%)',0.,100.,10.)/100
                c['gas']=a.number_input('Gas per arbitrage / liquidation (USD)',0.,10000.,10.)
                c['oracle_lag']=b.slider('Synthetic oracle lag (blocks)',0,30,2)
                c['close_factor']=a.slider('Liquidation close factor (%)',1,100,50)/100
                c['bonus']=b.slider('Liquidation bonus (%)',0,20,5)/100
                c['redemption_value']=a.slider('Assumed redemption value (USD)',.8,1.,1.,step=.01)
                c['sell_blocks']=b.slider('Sale wave length (blocks)',1,20,10)
            st.caption('Block duration: 12 seconds. Recovery: within ±1% of USD 1 for five consecutive samples. Curve A and v3 ranges use the comparison settings above.')
            st.write('**Editable synthetic collateral book** — collateral is the stressed token; debt is USD-denominated and remains at par. Threshold is a fraction, e.g. 0.80. Add or remove assumed accounts.')
            book=st.data_editor(pd.DataFrame(default_positions()),num_rows='dynamic',hide_index=True,key='collateral_book',column_config={
                'collateral_tokens':st.column_config.NumberColumn(min_value=0.,max_value=1e10),
                'debt_usd':st.column_config.NumberColumn(min_value=0.,max_value=1e10),
                'threshold':st.column_config.NumberColumn(min_value=.01,max_value=1.,step=.01)})
            run=st.form_submit_button('Run connected stress test',type='primary')
        if run:
            try:
                if book.empty or len(book)>200 or book.isna().any().any():raise ValueError('Use 1–200 complete collateral accounts.')
                positions=book.to_dict('records')
                with st.status('Running connected stress test',expanded=True) as status:
                    st.write('1 / 3 · Initialize pool invariant and collateral health factors')
                    bar=st.progress(0)
                    def update(value):
                        if int(value*c['blocks'])%10==0:bar.progress(value,text=f"2 / 3 · Simulating block {round(value*c['blocks'])} / {c['blocks']}")
                    result=simulate(c,positions,update)
                    st.write('3 / 3 · Summarize liquidation flows and sustained recovery')
                    bar.progress(1.)
                    status.update(label='Stress test complete',state='complete',expanded=False)
                st.session_state['connected_result']=result
                from experiment_journal import record
                record('Connected mechanism test',dict(config=c,positions=positions),result)
            except (ValueError,TypeError) as exc:
                st.error(str(exc));st.session_state.pop('connected_result',None)
        result=st.session_state.get('connected_result')
        if result:
            if result['config']!=c or result['initial_positions']!=book.to_dict('records'):
                st.info('Assumptions changed. Submit again to update the displayed run.')
                return
            summary=result['summary'];df=pd.DataFrame(result['steps']);cols=st.columns(4)
            cols[0].metric('Lowest modeled quote',f"${df.price.min():.4f}")
            cols[1].metric('Peak eligible collateral',f"${df.at_risk_usd.max():,.0f}")
            cols[2].metric('Debt actually repaid',f"${summary['total_debt_repaid_usd']:,.0f}")
            cols[3].metric('Recovery after trough',str(summary['recovery_blocks_after_trough'])+' blocks' if summary['recovery_block'] is not None else 'Not in horizon')
            lines(df,'block',['price','oracle'],'USD per stressed token','Model block',key='cascade_price')
            a,b=st.columns(2)
            with a:lines(df,'block',['lp_removed_pct'],'Cumulative LP withdrawal (%)',key='cascade_lp')
            with b:lines(df,'block',['at_risk_usd','debt_repaid_usd'],'Synthetic lending exposure (USD)',key='cascade_risk')
            st.caption('Eligible collateral is marked at the lagged oracle before each block’s liquidations; it is a stock, not an amount to sum across blocks. Debt repaid is a per-block flow. Liquidators execute only when full-sale proceeds exceed debt plus gas; insufficient capital or liquidity can leave accounts eligible but unliquidated.')
            with st.expander('Collateral at risk across assumed oracle prices'):
                risk=pd.DataFrame([dict(oracle_price=p/100,eligible_collateral_usd=collateral_at_risk(result['initial_positions'],p/100)) for p in range(70,101)])
                lines(risk,'oracle_price',['eligible_collateral_usd'],'Eligible collateral (USD)',key='risk_ladder')
                st.caption('Static sensitivity of the original synthetic book. Health factor = collateral tokens × oracle price × liquidation threshold / USD debt. Eligibility begins below 1. This simplified model does not reproduce Aave eMode, close-factor rules, Morpho market parameters, multi-collateral portfolios or bad-debt resolution.')
            with st.expander('Capital flows, fills and reproducibility'):
                st.dataframe(df,hide_index=True,width='stretch');st.json(summary)
                st.write('Arbitrage buys discounted tokens, pays gas and funding upfront, and waits for redemption before recycling capital. Redemption at the configured value is assumed certain and has no issuer capacity limit. Liquidator capital is recycled immediately after a profitable collateral sale. LP withdrawals proportionally scale reserves or range liquidity; no LP deposits or random agents. Oracle follows the simulated DEX with a lag; actual oracle designs can differ substantially.')
                st.download_button('Download complete mechanism experiment',json.dumps(result,indent=2),'mechanism-experiment.json','application/json')
    with st.expander('Model references'):
        st.markdown('[Curve StableSwap](https://docs.curve.finance/developer/amm/legacy/stableswap-overview/) · [Uniswap v3 mathematics](https://app.uniswap.org/whitepaper-v3.pdf) · [Aave health factor and liquidation](https://aave.com/faq)')
