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
.stButton>button[kind="primary"]:hover {background:#60e2e7;border-color:#60e2e7;color:#07131e;}
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
.block-container{padding-top:2rem;background:transparent;}
[data-testid="stApp"]{background:radial-gradient(ellipse 60% 40% at 85% -6%,rgba(43,112,150,.2),transparent 76%),radial-gradient(ellipse 32% 32% at -4% 40%,rgba(93,69,152,.12),transparent 85%),#080e1a;}
[data-testid="stSidebar"]{background:linear-gradient(155deg,#101d30,#0b1423 70%)!important;}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label{border-radius:10px;padding:.42rem .6rem;transition:background .18s ease,transform .18s ease;}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:hover{background:rgba(92,225,220,.08);transform:translateX(2px);}
[data-testid="stMetric"]{border-color:#2b4059;border-radius:15px;background:linear-gradient(145deg,rgba(25,44,66,.92),rgba(15,28,47,.93));box-shadow:0 12px 30px rgba(0,0,0,.1);transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease;animation:rise .35s ease both;}
[data-testid="stMetric"]:hover{transform:translateY(-3px);border-color:rgba(92,225,220,.48);box-shadow:0 16px 34px rgba(0,0,0,.18);}
[data-testid="stMetricLabel"]{text-transform:uppercase;letter-spacing:.065em;font-weight:700;font-size:.78rem;}
[data-testid="stPlotlyChart"]{border-radius:15px;box-shadow:0 9px 26px rgba(0,0,0,.1);animation:rise .4s ease both;}
[data-testid="stTabs"] [role="tablist"]{gap:1.25rem;border-bottom:1px solid #293e58;}
[data-testid="stTabs"] button[role="tab"]{font-weight:700;color:#9fb1c9;}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{color:#6ae3de;}
.stButton>button,.stDownloadButton>button{transition:transform .16s ease,background .16s ease,border-color .16s ease,box-shadow .16s ease;}
.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-1px);box-shadow:0 8px 22px rgba(21,142,145,.12);}
.stButton>button[kind="primary"]{background:linear-gradient(115deg,#62e0d9,#6cbadf);}
.stButton>button[kind="primary"]:hover{background:linear-gradient(115deg,#79eee7,#83cef0);}
.sidebar-source{display:flex;flex-direction:column;gap:5px;border:1px solid #304963;border-radius:12px;padding:14px;background:rgba(60,98,128,.13);margin-top:.7rem;}
.sidebar-source span{font-size:.6rem;letter-spacing:.16em;font-weight:800;color:#64ded9;}.sidebar-source strong{font-size:.83rem;color:#edf7ff;}.sidebar-source small{font-size:.72rem;color:#a4b8d0;}
.hero{position:relative;overflow:hidden;padding:30px 33px;margin:.55rem 0 1.5rem;border:1px solid rgba(105,177,207,.32);border-radius:18px;background:linear-gradient(105deg,rgba(30,72,97,.6),rgba(23,41,74,.76) 60%,rgba(31,35,73,.78));box-shadow:0 15px 38px rgba(0,0,0,.11);animation:rise .36s ease both;}
.hero:after{content:"";position:absolute;right:-5%;top:-110px;width:380px;height:380px;border-radius:50%;background:radial-gradient(circle,rgba(95,223,218,.14),transparent 68%);pointer-events:none;}
.hero h2{font-size:1.86rem!important;margin:.15rem 0 .5rem!important;}.hero p{color:#bad0e1;margin:0;font-size:.9rem;}
.empty-state{border:1px solid #37516e;border-radius:17px;padding:33px;background:linear-gradient(125deg,#15263d,#111e31);margin:1rem 0;}.empty-state h3{font-size:1.35rem!important;margin:.25rem 0 .5rem;}.empty-state p{color:#afc3d7;max-width:760px;margin:0;}
.insight{border:1px solid #314a63;border-left:3px solid #60ded9;background:linear-gradient(100deg,#15273d,#122136);transition:transform .18s ease,border-color .18s ease;}.insight:hover{transform:translateX(2px);border-color:#5bd6d2;}
.insight small{color:#80bac6;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;font-weight:700;}
.footer-note{border-top:1px solid #25364e;margin-top:2rem;}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important;}}
</style>
"""
