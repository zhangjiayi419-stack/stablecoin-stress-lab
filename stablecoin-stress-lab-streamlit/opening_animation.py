"""Optional, skippable 4.2-second synthetic intro, once per Streamlit session."""
import json
import streamlit as st
import streamlit.components.v1 as components
from mechanism_engine import Pool


def render_opening():
    if st.session_state.get('_home_intro_seen',False):return
    st.session_state['_home_intro_seen']=True
    frames=[]
    for i in range(41):
        pool=Pool('Curve',20e6);pool.trade(12e6*i/40)
        x,y=pool.balances();frames.append(dict(price=pool.price(),share=x/(x+y)*100))
    markup='''<!doctype html><html><head><style>body{margin:0;background:#0d1724;color:#dceaff;font:14px system-ui}section{border:1px solid #30445c;border-radius:6px;padding:16px}header{display:flex;justify-content:space-between;align-items:center;color:#91a7be;font:10px monospace;letter-spacing:.08em}button{color:#c4d8ed;background:transparent;border:1px solid #456284;border-radius:4px;padding:5px 12px;cursor:pointer}.quote{font:600 32px monospace;margin:10px 0}.bar{display:flex;height:16px;background:#327e70;border-radius:3px;overflow:hidden}.sell{width:50%;background:#447eb8}#label{margin:10px 0 0;color:#a6bdd3;font-size:12px}#end{display:none;font-size:21px;line-height:1.5;padding:20px 0 6px}</style></head><body><section><header><span>ILLUSTRATIVE POOL · NOT A HISTORICAL REPLAY</span><button id="skip">Skip intro →</button></header><div id="scene"><div class="quote" id="price">$1.00</div><div class="bar"><div class="sell" id="share"></div></div><p id="label">The quote is near $1.00. Then a large sell order arrives.</p></div><div id="end">A price near $1 does not mean you can sell at $1.</div></section><script>const frames=__FRAMES__;let stopped=false,start=null;function finish(){stopped=true;document.getElementById('scene').style.display='none';document.getElementById('end').style.display='block';document.getElementById('skip').style.display='none'}document.getElementById('skip').onclick=finish;function tick(now){if(stopped)return;if(start===null)start=now;let t=(now-start)/4200;if(t>=1){finish();return}let u=Math.max(0,Math.min(1,(t-.2)/.65)),f=frames[Math.round(u*40)];document.getElementById('price').textContent='$'+f.price.toFixed(4);document.getElementById('share').style.width=f.share+'%';if(t>.2)document.getElementById('label').textContent='Illustrative $12m sale into a fixed $20m pool: output reserves shrink, the quote falls.';requestAnimationFrame(tick)}if(matchMedia('(prefers-reduced-motion: reduce)').matches)finish();else requestAnimationFrame(tick);</script></body></html>'''.replace('__FRAMES__',json.dumps(frames))
    if hasattr(st,'iframe'):st.iframe(markup,height=190,alt='Optional opening: sell order, depleted reserves and falling quote')
    else:components.html(markup,height=190,scrolling=False)
