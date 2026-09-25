"""RetailMind visual system: midnight canvas, restrained cyan and violet."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root {--bg:#0a1424;--panel:#132239;--panel2:#182a43;--border:#29415e;--muted:#a9bad0;--cyan:#49d5db;--violet:#a68af9;--danger:#ff737d;}
html,body,[class*="css"],[data-testid="stApp"] {font-family:'DM Sans',sans-serif!important;}
[data-testid="stApp"] {background:radial-gradient(circle at 70% 0%,#132740 0%,#0a1424 52%);color:#f4f7fb;}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#15263d,#101d30)!important;border-right:1px solid var(--border);}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {color:#c4d0e2;}
.block-container {max-width:1480px;padding-top:1.35rem;padding-bottom:3rem;}
h1,h2,h3,h4 {font-family:'Manrope',sans-serif!important;letter-spacing:-.035em!important;color:#f5f8fc!important;}
h1 {font-size:2.25rem!important;font-weight:800!important;} h2 {font-size:1.4rem!important;font-weight:750!important;} h3 {font-size:1.1rem!important;}
[data-testid="stMetric"] {border:1px solid var(--border);border-radius:14px;padding:19px 20px;background:linear-gradient(135deg,#172941,#112036);min-height:126px;}
[data-testid="stMetricLabel"] {font-size:.88rem;color:#b8c7d9;} [data-testid="stMetricValue"] {font-family:'Manrope',Arial,sans-serif;font-weight:800;font-size:1.6rem;}
[data-testid="stMetricDelta"] {font-size:.8rem;}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:var(--border)!important;border-radius:14px!important;background:rgba(20,35,57,.72);}
[data-testid="stPlotlyChart"] {border:1px solid var(--border);border-radius:14px;background:#132239;overflow:hidden;}
[data-testid="stDataFrame"] {border:1px solid var(--border);border-radius:12px;overflow:hidden;}
[data-testid="stAlert"] {border-radius:12px;}
.stButton>button[kind="primary"] {background:#47d4db;color:#07131e;border:0;font-weight:700;border-radius:9px;}
.stButton>button {border-radius:9px;border-color:#36516d;font-weight:600;}
.stButton>button:hover {border-color:#49d5db;color:#49d5db;}
.stSelectbox label,.stDateInput label,.stNumberInput label,.stSlider label,.stFileUploader label {font-size:.82rem!important;color:#bac9dc!important;font-weight:600!important;}
.eyebrow {text-transform:uppercase;letter-spacing:.16em;color:#66dfe4;font-size:.7rem;font-weight:700;}
.subtle {color:#a9bad0;font-size:1rem;margin-top:-.55rem;}
.brand {font-family:'Manrope',Arial,sans-serif;font-weight:800;font-size:1.45rem;letter-spacing:-.05em;color:white;margin:8px 0 0;}
.brand span {color:#49d5db;}.brand-sub {font-size:.62rem;letter-spacing:.13em;text-transform:uppercase;color:#8ea5c4;margin-bottom:18px;}
.callout {padding:20px;border:1px solid #345270;border-radius:14px;background:linear-gradient(115deg,#18314a,#14243b);margin:10px 0 24px;}
.callout strong {font-family:'Manrope',Arial,sans-serif;font-size:1.16rem;}.callout p {color:#b7c8db;margin:.35rem 0 0;}
.insight {border-left:3px solid #49d5db;background:#14243a;border-radius:0 10px 10px 0;padding:12px 16px;margin:10px 0;}
.insight b {color:#f4f7fb;}.insight small {color:#95aac2;}.insight p {margin:4px 0;color:#c2d0df;}
.footer-note {color:#8097b2;font-size:.78rem;padding-top:1.5rem;}
@media(max-width:1100px){
  [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;}
  [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{min-width:200px!important;flex:1 1 200px!important;width:auto!important;}
  [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:has([data-testid="stPlotlyChart"]){min-width:100%!important;flex-basis:100%!important;}
  [data-testid="stMetric"]{min-height:110px;}
}
@media(max-width:850px){.block-container{padding-left:1rem;padding-right:1rem;}h1{font-size:1.7rem!important;}}
</style>
"""
