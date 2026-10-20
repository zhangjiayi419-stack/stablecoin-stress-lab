"""Native CSS intro: no iframe/JavaScript dependency or reserved iframe space."""
import streamlit as st
from mechanism_engine import Pool


def opening_markup(sequence=0):
    quotes=[]
    for fraction in [0,.15,.35,.5,.6]:
        p=Pool('Curve',20e6);p.trade(20e6*fraction)
        quotes.append(p.price())
    return '''<style>
.opening-demo{position:relative;border:1px solid #3a536d;border-radius:6px;background:#0d1724;padding:18px 20px;margin-bottom:8px;min-height:142px;box-sizing:border-box;overflow:hidden}
.opening-label{font:10px monospace;letter-spacing:.08em;color:#b3c9dd}.opening-scene{animation:intro-scene 4.2s linear both}.opening-price{font:600 30px monospace;color:#e6f2ff;margin:10px 0}.opening-price:after{content:'$1.00';animation:intro-price 4.2s linear both}.opening-depth{height:17px;border-radius:3px;background:#284d50;overflow:hidden}.opening-depth-fill{height:100%;width:50%;background:#70b7ff;animation:intro-imbalance 4.2s ease-in-out both}.opening-note{color:#c0d2e3;font-size:12px;margin-top:10px}.opening-end{position:absolute;inset:40px 20px auto;font-size:21px;line-height:1.5;color:#e6f2ff;animation:intro-end 4.2s linear both}
@keyframes intro-price{0%,20%{content:'$1.00'}35%{content:'__Q1__'}50%{content:'__Q2__'}65%{content:'__Q3__'}80%,100%{content:'__Q4__'}}
@keyframes intro-imbalance{0%,20%{width:50%}40%{width:65%}60%{width:83%}80%,100%{width:99%}}
@keyframes intro-scene{0%,84%{opacity:1}94%,100%{opacity:0}}
@keyframes intro-end{0%,88%{opacity:0}100%{opacity:1}}
@media(prefers-reduced-motion:reduce){.opening-scene{display:none;animation:none}.opening-end{position:static;opacity:1;animation:none;margin:14px 0}.opening-demo{min-height:0}}
</style><section class="opening-demo" aria-label="Opening liquidity illustration"><div class="opening-label">ILLUSTRATIVE FIXED-DEPTH POOL · NOT HISTORICAL DATA</div><div class="opening-scene"><div class="opening-price" aria-label="Illustrative quote falls from one dollar"></div><div class="opening-depth"><div class="opening-depth-fill"></div></div><div class="opening-note">A $12m sale enters a $20m pool. Output reserves shrink; the quote falls.</div></div><div class="opening-end">A price near $1 does not mean you can sell at $1.</div></section>'''.replace('__Q1__',f'${quotes[1]:.4f}').replace('__Q2__',f'${quotes[2]:.4f}').replace('__Q3__',f'${quotes[3]:.4f}').replace('__Q4__',f'${quotes[4]:.4f}').replace('intro-',f'intro-{sequence}-')


def replay_opening():
    st.session_state['_home_intro_replay']=True


def render_opening():
    show=not st.session_state.get('_home_intro_seen',False) or st.session_state.pop('_home_intro_replay',False)
    st.session_state['_home_intro_seen']=True
    if show:
        sequence=st.session_state.get('_intro_sequence',0)+1
        st.session_state['_intro_sequence']=sequence
        st.markdown(opening_markup(sequence),unsafe_allow_html=True)
        st.button('Skip / close opening',key='intro_close',help='Dismiss the illustration immediately. The homepage stays available below.')
    st.button('Replay opening illustration',key='intro_replay',on_click=replay_opening,help='Replay the 4.2-second illustration. Automatic playback happens once per session.')
