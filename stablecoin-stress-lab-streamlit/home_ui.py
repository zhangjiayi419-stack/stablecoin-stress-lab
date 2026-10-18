"""A concise research cover with an optional illustrative CSS animation."""
import streamlit as st


def render_cover(route):
    st.markdown('''<style>
.research-hero{padding:25px 0 10px;border-top:1px solid #25344a}.hero-label{font:11px monospace;letter-spacing:.19em;color:#70b7ff}.hero-title{font-size:clamp(38px,5vw,66px);line-height:1.05;letter-spacing:-.055em;font-weight:650;margin:22px 0;color:#e5edf7;max-width:870px}.hero-description{font-size:17px;line-height:1.6;color:#a6b7cb;max-width:720px;margin-bottom:30px}.mechanism-strip{display:flex;gap:10px;align-items:center;margin:20px 0}.mechanism-node{flex:1;border:1px solid #30445c;background:#101d2d;padding:20px 14px;min-height:100px;animation:research-pulse 12s infinite;color:#b9cee5}.mechanism-node:nth-child(2){animation-delay:3s}.mechanism-node:nth-child(3){animation-delay:6s}.mechanism-node:nth-child(4){animation-delay:9s}.mechanism-node strong{display:block;color:#e5edf7;font-size:14px;margin:8px 0}.mechanism-node small{font:10px monospace;color:#8da7c6}.motion-paused .mechanism-node{animation-play-state:paused}@keyframes research-pulse{0%,24%{border-color:#70b7ff;box-shadow:inset 0 2px #70b7ff;background:#182e46}25%,100%{border-color:#30445c;box-shadow:none;background:#101d2d}}@media(prefers-reduced-motion:reduce){.mechanism-node{animation:none}}@media(max-width:650px){.mechanism-strip{display:grid;grid-template-columns:1fr 1fr}.mechanism-node{min-height:90px}}
</style><section class="research-hero"><div class="hero-label">01 / STABLECOIN STRESS LAB / RESEARCH WORKSPACE</div><div class="hero-title">Systemic Liquidity &amp;<br>Depeg Contagion Lab</div><div class="hero-description">Empirical dislocation tracking, econometric tail-risk forecasting, and AMM liquidity spiral simulations.</div></section>''',unsafe_allow_html=True)
    cols=st.columns(3)
    entries=[('OBSERVE','Explore Markets','Recorded USD prices and historical pool evidence.','Historical Research'),('EVALUATE','Compare Models','Shared test windows, baseline errors and traceable forecasts.','Forecast Lab'),('EXPERIMENT','Run Stress Test','AMM curves, LP exits, liquidation feedback and recovery.','Mechanism Lab')]
    for col,(label,title,description,page) in zip(cols,entries):
        with col:
            with st.container(border=True):
                st.markdown(f'<div class="card-label">{label}</div>',unsafe_allow_html=True)
                st.subheader(title);st.caption(description)
                st.button(title+' →',key='cover_'+page,on_click=route,args=(page,),width='stretch')
    from impact_animation import render_impact_animation
    render_impact_animation()
    st.divider()
