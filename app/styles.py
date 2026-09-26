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
.block-container{max-width:1560px;padding:1.35rem 2.2rem 3.5rem;}
.block-container>div:first-child{gap:.55rem;}
[data-testid="stSidebar"]{box-shadow:14px 0 44px rgba(0,0,0,.16);}
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-testid="stWidgetLabel"] p{font-size:.66rem!important;letter-spacing:.18em;text-transform:uppercase;color:#7f9ab7!important;font-weight:800;}
[data-testid="stSidebar"] label[data-testid="stRadioOption"]{margin:.16rem 0;padding:.62rem .74rem!important;border:1px solid transparent;border-radius:11px!important;min-height:42px;}
[data-testid="stSidebar"] label[data-testid="stRadioOption"]>div>div:first-child{display:none;}
[data-testid="stSidebar"] label[data-testid="stRadioOption"] p{font-size:.86rem;font-weight:650;color:#9eb4cb;}
[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"]{background:linear-gradient(95deg,rgba(62,205,206,.16),rgba(62,205,206,.035));border-color:rgba(102,231,224,.27);box-shadow:inset 3px 0 #65e4dd;}
[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] p{color:#eefefd!important;}
[data-testid="stSidebar"] .brand{font-size:1.64rem;margin-top:12px;}
[data-testid="stSidebar"] .brand-sub{margin-bottom:27px;}
.page-heading{padding:1.3rem 0 1.05rem;border-bottom:1px solid #26394f;margin-bottom:1rem;}
.page-heading h1{font-size:2.55rem!important;margin:.2rem 0 .32rem!important;line-height:1.16;}
.page-heading p{margin:0;color:#9db3cc;font-size:.97rem;}
.command-hero{position:relative;display:grid;grid-template-columns:minmax(0,1.2fr) minmax(340px,.8fr);gap:2rem;overflow:hidden;padding:2.6rem 2.75rem;margin:1rem 0 1.15rem;border:1px solid #315a6c;border-radius:19px;background:radial-gradient(circle at 75% 5%,rgba(67,208,201,.17),transparent 36%),linear-gradient(115deg,#12293d,#142941 52%,#152541);box-shadow:0 28px 65px rgba(0,0,0,.2);animation:rise .38s ease both;}
.command-hero:before{content:"";position:absolute;width:550px;height:550px;border:1px solid rgba(112,218,218,.095);border-radius:50%;right:-145px;top:-280px;pointer-events:none;}
.command-hero__copy,.hero-visual{position:relative;z-index:1;min-width:0;}
.hero-status{display:flex;align-items:center;gap:.6rem;font-size:.64rem;letter-spacing:.2em;color:#74e1d9;font-weight:800;}
.hero-status__sep{color:#4c6f83;}.status-pulse{width:8px;height:8px;display:inline-block;border-radius:50%;background:#64e4d8;box-shadow:0 0 0 5px rgba(93,220,210,.12),0 0 16px rgba(93,220,210,.55);}
.command-hero h1{font-size:clamp(3.15rem,5.3vw,5.55rem)!important;letter-spacing:-.075em!important;line-height:1.035;margin:1.15rem 0 1rem!important;font-weight:800!important;}
.command-hero h1 em{font-style:normal;color:#67e4dc;background:linear-gradient(90deg,#66e9db,#a5d8ed);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;}
.command-hero p{max-width:520px;color:#aac4d4;font-size:1rem;line-height:1.65;margin:0;}
.hero-chips{display:flex;flex-wrap:wrap;gap:.48rem;margin-top:1.75rem;}.hero-chips span{border:1px solid rgba(112,158,183,.3);background:rgba(168,218,225,.055);border-radius:6px;padding:.48rem .68rem;color:#d0e2eb;font-size:.73rem;font-weight:700;}
.hero-visual{align-self:stretch;display:flex;flex-direction:column;justify-content:space-between;border:1px solid rgba(130,207,210,.21);border-radius:15px;background:linear-gradient(135deg,rgba(10,28,43,.75),rgba(14,43,58,.52));padding:1.35rem 1.5rem;min-height:255px;box-shadow:inset 0 1px rgba(255,255,255,.045);}
.hero-visual__top,.hero-visual__foot{display:flex;justify-content:space-between;gap:1rem;align-items:center;font-size:.66rem;color:#8faec2;}.hero-visual__top span:first-child{letter-spacing:.16em;color:#63d8d2;font-weight:800;}.hero-visual__value{font-family:'Manrope',sans-serif;font-size:3.3rem;font-weight:800;letter-spacing:-.07em;color:#f6ffff;line-height:1;margin-top:1rem;}.hero-visual__value small{display:block;font-family:'DM Sans',sans-serif;font-size:.71rem;letter-spacing:.03em;color:#96b9c8;font-weight:600;margin-top:.45rem;}.hero-visual__spark{height:98px;margin:.2rem 0;}.hero-visual__spark svg{display:block;width:100%;height:100%;}.hero-visual__foot{border-top:1px solid rgba(137,181,190,.17);padding-top:.65rem;}.hero-visual__foot strong{color:#f2faff;}
.signal-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.8rem;margin:0 0 2.2rem;}.signal-card{position:relative;display:flex;flex-direction:column;min-width:0;min-height:165px;padding:1.15rem 1.2rem 1.05rem;border:1px solid #284057;border-radius:14px;background:linear-gradient(145deg,rgba(20,38,56,.94),rgba(13,28,45,.96));box-shadow:0 10px 32px rgba(0,0,0,.1);transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease;animation:rise .42s ease both;}.signal-card:hover{transform:translateY(-3px);border-color:#558c99;box-shadow:0 18px 34px rgba(0,0,0,.22);}.signal-card__top{display:flex;justify-content:space-between;align-items:center;gap:.5rem;color:#9aadc3;text-transform:uppercase;font-size:.66rem;font-weight:800;letter-spacing:.1em;}.signal-card__dot{width:7px;height:7px;border-radius:50%;background:var(--card-accent);box-shadow:0 0 13px var(--card-accent);}.signal-card strong{font-family:'Manrope',sans-serif;font-size:clamp(1.55rem,2.5vw,2.25rem);font-weight:800;letter-spacing:-.055em;color:#f4faff;line-height:1.2;margin:.72rem 0 .3rem;overflow-wrap:anywhere;}.signal-card small{font-size:.72rem;color:#8fa7be;margin-top:auto;}.signal-card__track{height:3px;border-radius:3px;background:rgba(152,181,204,.13);overflow:hidden;margin-top:.85rem;}.signal-card__track i{display:block;height:100%;background:var(--card-accent);border-radius:3px;}.signal-card--teal{--card-accent:#64e1d7}.signal-card--blue{--card-accent:#8dbbff}.signal-card--violet{--card-accent:#b5a0ff}.signal-card--amber{--card-accent:#f1bb7c}
.section-head{margin:1.75rem 0 .78rem;}.section-head span{color:#62dcd5;letter-spacing:.19em;font-size:.66rem;font-weight:800;}.section-head h2{font-size:1.43rem!important;margin:.25rem 0 .25rem!important;}.section-head p{color:#90a9c0;font-size:.82rem;margin:0;}
.evidence-panel{border:1px solid #2c455d;border-radius:15px;background:linear-gradient(150deg,#162b40,#102137);overflow:hidden;min-height:315px;}.evidence-panel__head{display:flex;justify-content:space-between;gap:1rem;padding:1rem 1.25rem;border-bottom:1px solid #2d4960;color:#79ddd6;font-size:.67rem;letter-spacing:.15em;font-weight:800;}.evidence-panel__head span{color:#90a8bf;}.evidence-row{padding:.8rem 1.25rem;border-bottom:1px solid rgba(115,154,183,.12);}.evidence-row:last-child{border-bottom:0;}.evidence-row span{display:block;color:#65cbc8;font-size:.62rem;letter-spacing:.12em;font-weight:800;}.evidence-row strong{display:block;color:#f0f8ff;font-size:.92rem;margin:.17rem 0;}.evidence-row p{font-size:.73rem;color:#9eb3c6;margin:0;line-height:1.35;}
[data-testid="stExpander"]{border:1px solid #2b4359!important;border-radius:10px!important;background:rgba(17,34,51,.7);}[data-testid="stExpander"] summary{font-size:.8rem;font-weight:700;color:#a7c5d0!important;}
[data-testid="stPlotlyChart"]{background:linear-gradient(145deg,#13283d,#101e30);border-color:#2b435b;}
@media(max-width:1200px){.command-hero{grid-template-columns:1fr 1fr;padding:2rem;}.signal-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media(max-width:800px){.block-container{padding:4.4rem .9rem 2.5rem;}.command-hero{display:block;padding:1.7rem 1.35rem;}.command-hero h1{font-size:3.2rem!important;}.hero-visual{margin-top:1.5rem;min-height:235px;}.signal-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.page-heading h1{font-size:2rem!important;}}
@media(max-width:520px){.block-container{padding:4.3rem .7rem 2rem;}.command-hero{margin-top:.7rem;border-radius:15px;}.command-hero h1{font-size:2.9rem!important;}.hero-status{font-size:.55rem;letter-spacing:.12em;}.hero-chips span{font-size:.64rem;}.signal-grid{gap:.55rem;}.signal-card{padding:.9rem;min-height:152px;}.signal-card strong{font-size:1.44rem;}.signal-card small{font-size:.67rem;}.hero-visual__value{font-size:2.7rem;}.section-head h2{font-size:1.25rem!important;}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important;}}
</style>
"""
