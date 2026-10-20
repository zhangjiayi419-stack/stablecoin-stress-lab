"""Shared terminal palette for Streamlit surfaces and Vega-Lite figures."""
import altair as alt
import streamlit as st

PALETTE = {'blue':'#70b7ff','mint':'#48d5b4','amber':'#dfb969','muted':'#8193aa'}

@alt.theme.register('stablecoin_terminal', enable=True)
def terminal_chart_theme():
    return {
        'background':'#0d1520',
        'config':{
            'font':'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
            'view':{'stroke':None},
            'axis':{'labelColor':'#9aaec5','titleColor':'#b8c8da','domainColor':'#304156',
                    'tickColor':'#304156','gridColor':'#1d2b3c','gridOpacity':.8,
                    'labelFontSize':11,'titleFontSize':11,'titleFontWeight':400,
                    'labelPadding':8,'titlePadding':14},
            'legend':{'labelColor':'#b8c8da','titleColor':'#b8c8da','labelFontSize':11,
                      'symbolStrokeWidth':3,'padding':8},
            'title':{'color':'#e5edf7','fontSize':14,'anchor':'start'},
            'range':{'category':['#70b7ff','#48d5b4','#dfb969','#a99aef','#ed8d99'],
                     'heatmap':['#14233a','#244876','#4786bd','#b1d9f2']},
            'line':{'color':'#70b7ff','strokeWidth':2},
            'point':{'color':'#70b7ff'},
            'bar':{'color':'#70b7ff'},
            'text':{'color':'#dce7f5'},
            'background':'#0d1520'
        }
    }

CSS = '''<style>
:root{color-scheme:dark;--ink:#dce7f5;--muted:#92a5bd;--teal:#48d5b4;--surface:#101a27;--line:#25344a;--mono:"SFMono-Regular",Consolas,"Liberation Mono",monospace}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#080e17;color:var(--ink)}
[data-testid="stHeader"]{background:rgba(8,14,23,.96);border-bottom:1px solid #1d2b3d}
.stMainBlockContainer{max-width:1380px;padding-top:3rem;padding-bottom:2.7rem}
h1,h2,h3{color:#e6eef9;letter-spacing:-.03em}h1{font-weight:600!important;font-size:2.25rem!important;line-height:1.2!important}h2{font-size:1.45rem!important}h3{font-size:1.08rem!important;font-weight:600!important}
.stMarkdown p{line-height:1.65}.stCaption,[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p,[data-testid="stCaptionContainer"] span{color:#becde0!important;opacity:1;font-size:.8rem;line-height:1.65}
a{color:#82bdff}a:hover{color:#b7d8ff}
[data-testid="stSidebar"]{background:#0b131f;color:#dce7f5;border-right:1px solid #213148}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#8fa4be}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:.38rem .15rem}
[data-testid="stSidebar"] [role="radiogroup"]{gap:.3rem}
[data-testid="stSidebar"] label:has(input:checked){background:#14263a;border-radius:5px;box-shadow:inset 2px 0 #70b7ff}
[data-testid="stMetric"]{background:linear-gradient(125deg,#111d2d,#0e1724);border:1px solid #25364d;border-top:2px solid #345270;border-radius:5px;min-height:7.4rem;padding:1rem 1.15rem}
[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p{color:#9db0c8;font-size:.76rem;letter-spacing:.035em}
[data-testid="stMetricValue"],[data-testid="stMetricValue"]>div{color:#e5f0ff;font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:1.75rem;font-weight:500;letter-spacing:-.045em}
[data-testid="stMetricDelta"]{font-family:var(--mono);font-size:.72rem}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-color:#25344a!important;border-radius:5px}
[data-testid="stForm"]{background:#0d1724;border-color:#283b52;border-radius:5px;padding:1.2rem}
[data-testid="stExpander"]{background:#0d1724;border-color:#25344a!important;border-radius:5px}
[data-testid="stExpander"] summary:hover{color:#8bc3ff}
[data-testid="stPlotlyChart"],[data-testid="stVegaLiteChart"]{background:#0d1520;border:1px solid #213148;border-radius:5px;padding:10px}
[data-testid="stDataFrame"]{border:1px solid #25344a;border-radius:5px;overflow:hidden}
[data-baseweb="tab-list"]{border-bottom-color:#25344a;gap:1.2rem}
[data-baseweb="tab"]{color:#92a5bd;font-size:.82rem}
[data-baseweb="tab"][aria-selected="true"]{color:#83c2ff}
[data-baseweb="tab-highlight"]{background:#70b7ff;height:2px}
[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="textarea"]{background:#111f30!important;color:#e1ebf7!important;border-color:#30445f!important;border-radius:4px!important}
[data-baseweb="select"] svg{fill:#9fb3cc}
input,textarea{color:#e1ebf7!important;caret-color:#70b7ff;font-variant-numeric:tabular-nums}
input[type="number"]{font-family:var(--mono)}
[data-testid="stWidgetLabel"] p{font-size:.8rem;color:#b3c3d8}
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"] button{border-radius:4px;border:1px solid #314862;background:#132236;color:#cddff3;font-size:.82rem;min-height:2.5rem}
.stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"] button:hover{border-color:#70b7ff;color:#d9ecff;background:#192f49}
.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]{background:#79baff;color:#081320;border-color:#79baff;font-weight:600}
.stButton>button[kind="primary"]:hover{background:#a0ceff;border-color:#a0ceff;color:#07101c}
button:focus-visible,input:focus-visible{outline:2px solid #70b7ff;outline-offset:2px}
[data-testid="stTable"] td,[data-testid="stTable"] th{white-space:normal!important;overflow-wrap:anywhere;max-width:340px;vertical-align:top;font-size:.75rem}
hr{border-color:#223249!important}
.eyebrow{font-family:var(--mono);font-size:.68rem;letter-spacing:.15em;font-weight:500;color:#6fb9ff;margin-bottom:10px;text-transform:uppercase}
.deck{color:#9badc4;font-size:.97rem;max-width:890px;margin:8px 0 22px;line-height:1.65}
.data-strip{font-family:var(--mono);border:1px solid #24364c;border-left:2px solid #5d95cc;background:#0c1725;padding:10px 13px;margin:0 0 22px;font-size:.69rem;color:#99b0ca;line-height:1.85;border-radius:3px}
.brand{font-size:1.02rem;font-weight:600;letter-spacing:-.02em;margin:4px 0 5px;color:#e1ecfb}.brand-mark{color:#70b7ff;font-size:1.5rem}
.sidebar-kicker{font-family:var(--mono);color:#6e91b9;font-size:.63rem;letter-spacing:.15em;margin-top:5px;margin-bottom:27px}
.card-label{font-family:var(--mono);font-size:.66rem;letter-spacing:.12em;color:#7fa4cd;font-weight:500;text-transform:uppercase}
.badge{display:inline-block;background:#112a30;border:1px solid #244851;color:#77ccba;padding:3px 8px;border-radius:3px;font-family:var(--mono);font-size:.68rem}
.sidebar-footer{border-top:1px solid #26374d;margin-top:28px;padding-top:18px;color:#8299b5;font-size:.72rem;line-height:1.9}
.sidebar-footer strong{color:#bdd1e8;font-family:var(--mono);font-size:.71rem;font-weight:400}
code{background:#13263b!important;color:#a7d3ff!important}
#vg-tooltip-element{background:#142238!important;color:#dce7f5!important;border:1px solid #395472!important;box-shadow:0 5px 18px #0008!important}
#vg-tooltip-element td,#vg-tooltip-element th{color:#dce7f5!important}
@media(max-width:700px){h1{font-size:1.8rem!important}.stMainBlockContainer{padding-top:3rem}[data-testid="stMetricValue"]>div{font-size:1.55rem}.data-strip{font-size:.65rem}}
</style>'''


def install_terminal_theme():
    alt.theme.enable('stablecoin_terminal')
    st.markdown(CSS,unsafe_allow_html=True)
