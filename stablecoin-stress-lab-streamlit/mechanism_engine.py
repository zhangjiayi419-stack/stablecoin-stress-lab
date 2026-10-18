"""Deterministic, synthetic two-token mechanism experiments; no protocol risk feed."""
from copy import deepcopy
from math import sqrt
from backend.app.domain.stable_swap import get_y


class Pool:
    """Token0 is stressed collateral; token1 is a fixed USD-1 numeraire.

    v3 uses overlapping, tick-aligned ranges and integrates each crossed interval.
    Fee revenue is tracked separately in v3 (no auto compounding).
    """
    def __init__(self, kind='Curve', depth=20e6, amp=100, fee=.0004, narrow_ticks=200, outer_share=.2):
        if kind not in ('Curve', 'Uniswap v2', 'Uniswap v3') or depth <= 0 or amp <= 0 or not 0 <= fee < 1:
            raise ValueError('Invalid pool parameters')
        self.kind, self.amp, self.fee = kind, amp, fee
        self.x = self.y = depth / 2
        self.s = 1.
        self.fees = [0., 0.]
        self.ranges = []
        if not 0 <= outer_share <= 1:raise ValueError('Invalid outer allocation')
        for ticks, share in ((narrow_ticks, 1-outer_share), (2000, outer_share)):
            if not 1 <= ticks <= 2000: raise ValueError('Tick width outside supported range')
            a, b = 1.0001 ** (-ticks/2), 1.0001 ** (ticks/2)
            liquidity = depth * share / ((1-1/b) + (1-a))
            self.ranges.append([a, b, liquidity])

    def price(self):
        if self.kind == 'Uniswap v3': return self.s ** 2
        if self.kind == 'Uniswap v2': return self.y/self.x
        eps = max(.01, min(self.x, self.y) * 1e-6)
        return max(0., (self.y-get_y(0, 1, self.x+eps, [self.x,self.y], self.amp))/eps)

    def balances(self):
        if self.kind != 'Uniswap v3': return self.x,self.y
        x=y=0.
        for a,b,l in self.ranges:
            s=min(b,max(a,self.s))
            x += l*(1/s-1/b)
            y += l*(s-a)
        return x,y

    def active_liquidity(self):
        if self.kind!='Uniswap v3':return None
        # Active just below current price for token0 sales; exhausted lower edge = 0.
        return sum(l for a,b,l in self.ranges if a+1e-12<self.s<=b+1e-12)

    def sell_capacity_to_price(self, price):
        target=sqrt(price)
        return sum(l*(1/min(b,max(a,target))-1/min(b,max(a,self.s)))
                   for a,b,l in self.ranges)/(1-self.fee)

    def withdraw(self, fraction):
        if not 0 <= fraction < 1: raise ValueError('Invalid withdrawal fraction')
        self.x *= 1-fraction; self.y *= 1-fraction
        for r in self.ranges:r[2] *= 1-fraction

    def trade(self, amount, buy=False):
        """Returns output, gross input filled; unfilled input never charged."""
        if amount < 0: raise ValueError('Negative input')
        if amount == 0:return 0.,0.
        net = amount*(1-self.fee)
        if self.kind != 'Uniswap v3':
            x,y=(self.y,self.x) if buy else (self.x,self.y)
            out = y*net/(x+net) if self.kind=='Uniswap v2' else max(0.,y-get_y(0,1,x+net,[x,y],self.amp))
            if buy:self.y+=amount;self.x-=out
            else:self.x+=amount;self.y-=out
            return out,amount
        remaining, out, consumed = net,0.,0.
        boundaries=sorted({v for a,b,_ in self.ranges for v in (a,b)},reverse=not buy)
        for boundary in boundaries:
            if (buy and boundary<=self.s+1e-12) or (not buy and boundary>=self.s-1e-12):continue
            midpoint=(self.s+boundary)/2
            l=sum(l for a,b,l in self.ranges if a<midpoint<b)
            if l<=0:break # no liquidity: stop, do not fabricate a fill
            capacity=l*(boundary-self.s) if buy else l*(1/boundary-1/self.s)
            used=min(remaining,capacity)
            new_s=self.s+used/l if buy else 1/(1/self.s+used/l)
            out += l*(1/self.s-1/new_s) if buy else l*(self.s-new_s)
            self.s=new_s;remaining-=used;consumed+=used
            if remaining<=1e-9:break
        filled=consumed/(1-self.fee)
        self.fees[1 if buy else 0]+=filled*self.fee
        return max(0.,out),max(0.,filled)

    def quote(self, amount, buy=False):
        return deepcopy(self).trade(amount,buy)


def collateral_at_risk(positions, price):
    return sum(p['collateral_tokens']*price for p in positions
               if p['debt_usd']>0 and p['collateral_tokens']*price*p['threshold'] < p['debt_usd'])


def simulate(config, positions, progress=None):
    c=config; book=deepcopy(positions)
    for p in book:
        if p['collateral_tokens']<0 or p['debt_usd']<0 or not 0<p['threshold']<=1:
            raise ValueError('Invalid collateral book')
    pool=Pool(c['kind'],c['depth'],c['amp'],narrow_ticks=c['narrow_ticks'],outer_share=c.get('outer_share',.2))
    rows=[]; history=[1.]; settlements=[]
    cash=c['arb_capital']; liquidator_cash=c['liquidator_capital']; removed=0.; previous_withdrawal=0.
    sold=liquidated=0.; funding_paid=gas_paid=0.
    for block in range(c['blocks']+1):
        if block==0:
            rows.append(dict(block=0,price=1.,oracle=1.,lp_removed_pct=0.,at_risk_usd=collateral_at_risk(book,1.),debt_repaid_usd=0.,liquidation_tokens=0.,arb_spend_usd=0.,arb_cash_usd=cash,pending_redemption_usd=0.,unfilled_sell_tokens=0.,pool_depth_usd=sum(pool.balances())))
            continue
        cash+=sum(v for due,v in settlements if due<=block)
        settlements=[(due,v) for due,v in settlements if due>block]
        discount=max(0,1-pool.price())
        # A capped fraction of remaining LP ownership; momentum increases response.
        response=c['lp_speed']*max(0,discount-c['lp_trigger']) + c['lp_acceleration']*previous_withdrawal
        withdrawal=min(max(0,c['lp_max']-removed),max(0,response))
        pool.withdraw(withdrawal/max(1e-12,1-removed))
        removed+=withdrawal;previous_withdrawal=withdrawal
        sale=c['sell_tokens']/c['sell_blocks'] if block<=c['sell_blocks'] else 0.
        _,filled=pool.trade(sale);sold+=filled
        # Synthetic oracle observes the pre-liquidation quote with explicit block lag.
        history.append(pool.price())
        oracle=history[max(0,block-c['oracle_lag'])]
        at_risk=collateral_at_risk(book,oracle)
        repaid=seized=0.
        for p in book:
            if p['collateral_tokens']*oracle*p['threshold'] >= p['debt_usd'] or p['debt_usd']<=0:continue
            debt=min(p['debt_usd']*c['close_factor'],liquidator_cash,p['collateral_tokens']*oracle/(1+c['bonus']))
            tokens=debt*(1+c['bonus'])/max(oracle,1e-12)
            proceeds,fill=pool.quote(tokens)
            if debt>0 and fill>=tokens*(1-1e-8) and proceeds-debt>c['gas']:
                pool.trade(tokens)
                p['collateral_tokens']-=tokens;p['debt_usd']-=debt
                liquidator_cash+=proceeds-debt-c['gas'];repaid+=debt;seized+=tokens;gas_paid+=c['gas']
        liquidated+=repaid
        # Finite capital, gas, pool fee, redemption haircut and financing over delay.
        spend=0.
        if pool.price()<c['redemption_value'] and cash>c['gas']:
            budget=min(cash-c['gas'],c['arb_capital']*.1)
            tokens,fill=pool.quote(budget,buy=True)
            funding=fill*c['funding_apr']*c['redemption_delay']*c['block_seconds']/(365*86400)
            profit=tokens*c['redemption_value']-fill-c['gas']-funding
            if fill>0 and profit>0 and fill+c['gas']+funding<=cash:
                pool.trade(budget,buy=True);spend=fill
                cash-=fill+c['gas']+funding;funding_paid+=funding;gas_paid+=c['gas']
                settlements.append((block+max(1,c['redemption_delay']),tokens*c['redemption_value']))
        rows.append(dict(block=block,price=pool.price(),oracle=oracle,lp_removed_pct=removed*100,
            at_risk_usd=at_risk,debt_repaid_usd=repaid,liquidation_tokens=seized,arb_spend_usd=spend,
            arb_cash_usd=cash,pending_redemption_usd=sum(v for _,v in settlements),unfilled_sell_tokens=sale-filled,
            pool_depth_usd=sum(pool.balances())))
        if progress:progress(block/c['blocks'])
    trough=min(range(len(rows)),key=lambda i:rows[i]['price'])
    recovery=next((i for i in range(trough,len(rows)-c['recovery_samples']+1)
        if all(abs(r['price']-1)<=c['recovery_band'] for r in rows[i:i+c['recovery_samples']])),None)
    return dict(label='SYNTHETIC MECHANISM EXPERIMENT — NOT LIVE ONCHAIN RISK',config=c,initial_positions=positions,
        ending_positions=book,steps=rows,summary=dict(trough_block=trough,recovery_block=recovery,
        recovery_blocks_after_trough=None if recovery is None else recovery-trough,total_debt_repaid_usd=liquidated,
        total_holder_tokens_sold=sold,gas_paid_usd=gas_paid,funding_paid_usd=funding_paid,
        liquidator_ending_cash_usd=liquidator_cash))


def default_config():
    return dict(kind='Curve',depth=20e6,amp=100,narrow_ticks=200,blocks=80,sell_tokens=8e6,sell_blocks=10,
        arb_capital=2e6,liquidator_capital=1e6,gas=10.,funding_apr=.1,redemption_delay=15,redemption_value=1.,
        block_seconds=12,lp_max=.6,lp_speed=2.,lp_acceleration=.5,lp_trigger=.005,oracle_lag=2,
        close_factor=.5,bonus=.05,recovery_band=.01,recovery_samples=5)


def default_positions():
    return [dict(account=f'Synthetic {i+1}',collateral_tokens=1e6,debt_usd=debt,threshold=.8)
            for i,debt in enumerate((790000.,770000.,740000.,700000.,650000.))]
