"""Client-side playback of precomputed deterministic order-impact states."""
import json
import streamlit as st
import streamlit.components.v1 as components
from mechanism_engine import Pool


def render_impact_animation():
    st.subheader('Interactive order-impact experiment')
    a,b=st.columns([2,1])
    fraction=a.slider('Sell size (% of initial pool value)',0.,60.,20.,step=1.,key='hero_order')
    model=b.selectbox('Illustrative AMM',['Curve','Uniswap v3'],key='hero_model')
    total=20e6;amount=total*fraction/100;frames=[]
    for i in range(41):
        p=Pool(model,total);request=amount*i/40;out,filled=p.trade(request);x,y=p.balances()
        frames.append(dict(progress=i/40,share=x/(x+y)*100,price=p.price(),avg=out/filled if filled else None,
            filled=filled,unfilled=max(0,request-filled),requested=request))
    html='''<!doctype html><html><head><style>
body{margin:0;background:#0d1724;color:#cbd9eb;font:13px system-ui;padding:18px;border:1px solid #2b3b52;border-radius:6px}button{background:#18304c;color:#dceaff;border:1px solid #456284;border-radius:4px;padding:8px 15px;cursor:pointer}.label{font:10px monospace;color:#8fa5bf;letter-spacing:.12em}.bar{height:43px;display:flex;margin:18px 0;border:1px solid #33475e;border-radius:4px;overflow:hidden}.x{background:#447eb8;transition:width .08s}.y{background:#327e70;flex:1}.x,.y{display:flex;align-items:center;justify-content:center;white-space:nowrap;font:12px monospace}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:17px 0}.value{font:17px monospace;margin-top:8px;color:#e4effb}.caption{font-size:11px;color:#91a4bc;line-height:1.6}@media(prefers-reduced-motion:reduce){.x{transition:none}}
</style></head><body><div class="label">DETERMINISTIC ILLUSTRATION · TOKEN0 SALE / TOKEN1 USD-1 NUMERAIRE</div><div class="bar"><div class="x" id="x"></div><div class="y" id="y"></div></div><div class="metrics"><div><span class="label">MARGINAL QUOTE</span><div class="value" id="price"></div></div><div><span class="label">AVERAGE NET RATE</span><div class="value" id="average"></div></div><div><span class="label">UNFILLED TOKENS</span><div class="value" id="unfilled"></div></div></div><button id="play">Play sale</button> <button id="reset">Reset</button><span id="progress" class="caption"></span><p class="caption">Balances are token quantities, not independently marked USD TVL. Each frame solves the same initial pool with a larger single order. Fixed depth USD 20m at par, A=100, fee=4 bps; v3 has 80% inner ±200 ticks and 20% outer ±2000 ticks. No live data, LP exits or forecast is implied.</p><script>
const frames=__DATA__;let index=0,timer=null;const el=id=>document.getElementById(id);function render(){const f=frames[index];el('x').style.width=f.share+'%';el('x').textContent='Token0 '+f.share.toFixed(1)+'%';el('y').textContent='Token1 '+(100-f.share).toFixed(1)+'%';el('price').textContent=f.price.toFixed(4);el('average').textContent=f.avg===null?'—':f.avg.toFixed(4);el('unfilled').textContent=Math.round(f.unfilled).toLocaleString('en-US');el('progress').textContent='  '+Math.round(f.progress*100)+'% of requested sale';}function pause(){clearInterval(timer);timer=null;el('play').textContent='Play sale';}el('play').onclick=()=>{if(timer){pause();return}if(index===frames.length-1)index=0;el('play').textContent='Pause';timer=setInterval(()=>{index++;render();if(index===frames.length-1)pause()},90)};el('reset').onclick=()=>{pause();index=0;render()};render();
</script></body></html>'''.replace('__DATA__',json.dumps(frames,allow_nan=False))
    if hasattr(st,'iframe'):st.iframe(html,height=330,alt='Illustrative pool composition and single-order execution impact')
    else:components.html(html,height=330,scrolling=False)
