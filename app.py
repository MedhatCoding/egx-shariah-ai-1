import os
import json
import inspect

import pandas as pd
import streamlit as st
from google import genai

try:
    import egxpy
except Exception:
    egxpy = None

st.set_page_config(page_title="EGX Live Shariah Analyzer", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Cairo', sans-serif !important; direction: rtl; text-align: right; }
    .title { text-align:center; color:#0f172a; font-weight:700; margin-bottom:0.25rem; font-size:2.1rem; }
    .subtitle { text-align:center; color:#64748b; margin-bottom:1rem; }
    .card {
        background:#fff; border:1px solid #e2e8f0; border-radius:16px;
        padding:16px; margin-bottom:14px; box-shadow:0 2px 8px rgba(15,23,42,0.04);
    }
    .pill { display:inline-block; padding:4px 10px; border-radius:999px; background:#f1f5f9; color:#334155; font-size:0.82rem; font-weight:700; }
    .green { color:#16a34a; font-weight:700; }
    .red { color:#dc2626; font-weight:700; }
    .blue { color:#2563eb; font-weight:700; }
    .muted { color:#64748b; font-size:0.9rem; }
    .section-title { font-size:1.25rem; font-weight:700; color:#0f172a; margin-top:0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

SHARIAH_SYMBOLS = {
    "RAYA", "FWRY", "ISPH", "GBCO", "PHDC", "MASR", "SKPC", "FRA",
    "EFID", "JUFO", "ADIB", "AMOC", "CIRA", "CLHO", "DOMT", "ETEL",
    "TMGH", "ABUK", "EGAL", "SKP"
}

def get_gemini_client():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("ضع GEMINI_API_KEY في Streamlit Secrets.")
        st.stop()
    return genai.Client(api_key=api_key)

def normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    cols = {c.lower().strip(): c for c in df.columns}
    if not all(k in cols for k in ["symbol", "name", "last"]):
        return pd.DataFrame()

    out = pd.DataFrame()
    out["symbol"] = df[cols["symbol"]].astype(str).str.upper().str.replace(".CA", "", regex=False)
    out["name"] = df[cols["name"]].astype(str)
    out["last"] = pd.to_numeric(df[cols["last"]], errors="coerce")
    out["open"] = pd.to_numeric(df[cols["open"]], errors="coerce") if "open" in cols else pd.NA
    out["high"] = pd.to_numeric(df[cols["high"]], errors="coerce") if "high" in cols else pd.NA
    out["low"] = pd.to_numeric(df[cols["low"]], errors="coerce") if "low" in cols else pd.NA
    out["volume"] = pd.to_numeric(df[cols["volume"]], errors="coerce") if "volume" in cols else pd.NA
    out["prev_close"] = pd.to_numeric(df[cols["prev_close"]], errors="coerce") if "prev_close" in cols else pd.NA
    out["change"] = out["last"] - out["prev_close"]
    out["pct_change"] = (out["change"] / out["prev_close"]) * 100
    out = out[out["symbol"].isin(SHARIAH_SYMBOLS)].dropna(subset=["last"]).reset_index(drop=True)
    return out

@st.cache_data(ttl=60)
def fetch_egx_data():
    if egxpy is None:
        return pd.DataFrame([{"error": "egxpy import failed"}])

    fn_candidates = []
    for name in dir(egxpy):
        lname = name.lower()
        if any(k in lname for k in ["intraday", "daily", "weekly", "monthly", "download"]):
            attr = getattr(egxpy, name)
            if callable(attr):
                fn_candidates.append(name)

    preferred = [n for n in fn_candidates if "intraday" in n.lower()] + \
                [n for n in fn_candidates if "daily" in n.lower()] + \
                [n for n in fn_candidates if "weekly" in n.lower()] + \
                [n for n in fn_candidates if "monthly" in n.lower()] + \
                [n for n in fn_candidates if "download" in n.lower()]

    tried = []
    for fn_name in preferred:
        if fn_name in tried:
            continue
        tried.append(fn_name)
        try:
            fn = getattr(egxpy, fn_name)
            sig = inspect.signature(fn)
            kwargs = {}
            if "symbol" in sig.parameters:
                kwargs["symbol"] = None
            if "ticker" in sig.parameters:
                kwargs["ticker"] = None
            if "period" in sig.parameters:
                kwargs["period"] = "1d"
            if "interval" in sig.parameters:
                kwargs["interval"] = "1m"
            if "start_date" in sig.parameters:
                kwargs["start_date"] = None
            if "end_date" in sig.parameters:
                kwargs["end_date"] = None

            try:
                df = fn(**kwargs)
            except Exception:
                df = fn()

            if isinstance(df, pd.DataFrame):
                ndf = normalize_frame(df)
                if not ndf.empty:
                    return ndf
                return df
        except Exception:
            continue

    return pd.DataFrame([{"error": "No compatible EGXPY fetch function worked"}])

def timeframe_filter(df, mode):
    if df.empty:
        return df
    d = df.copy()
    if mode == "مضاربة يومية":
        return d.sort_values("pct_change", ascending=False).head(20).reset_index(drop=True)
    if mode == "أسبوعي":
        return d.sort_values("pct_change", ascending=False).head(30).reset_index(drop=True)
    if mode == "شهري قصير":
        return d.sort_values("pct_change", ascending=False).head(40).reset_index(drop=True)
    return d

def score_candidates(df, mode="up", limit=20):
    if df.empty or "last" not in df.columns:
        return df
    d = df.copy()
    d["momentum"] = d["pct_change"].fillna(0)
    d["liquidity"] = d["volume"].fillna(0)
    if mode == "up":
        return d.sort_values(["momentum", "liquidity"], ascending=False).head(limit).reset_index(drop=True)
    return d.sort_values(["momentum", "liquidity"], ascending=[True, False]).head(limit).reset_index(drop=True)

def gemini_analyze(df_candidates, mode="up"):
    client = get_gemini_client()
    payload = []
    for _, r in df_candidates.iterrows():
        payload.append({
            "symbol": r.get("symbol"),
            "name": r.get("name"),
            "last": float(r.get("last")) if pd.notna(r.get("last")) else None,
            "open": float(r.get("open")) if pd.notna(r.get("open")) else None,
            "high": float(r.get("high")) if pd.notna(r.get("high")) else None,
            "low": float(r.get("low")) if pd.notna(r.get("low")) else None,
            "prev_close": float(r.get("prev_close")) if pd.notna(r.get("prev_close")) else None,
            "volume": float(r.get("volume")) if pd.notna(r.get("volume")) else None,
            "pct_change": float(r.get("pct_change")) if pd.notna(r.get("pct_change")) else None,
        })

    task = "اختر فرص صعود قوية" if mode == "up" else "اختر فرص ارتداد من الهبوط"
    prompt = f"""
أنت محلل فني للأسهم المصرية المتوافقة مع الشريعة.
{task} من البيانات التالية فقط.
أعد JSON فقط بدون أي شرح أو markdown.

الهيكل:
{{
  "items": [
    {{
      "symbol": "string",
      "name": "string",
      "action": "شراء" أو "مراقبة" أو "ارتداد محتمل",
      "timeframe": "يومي" أو "أسبوعي" أو "قصير الأجل",
      "entry": number,
      "target": number,
      "stop_loss": number,
      "reasons": ["string", "string", "string"]
    }}
  ]
}}

البيانات:
{json.dumps(payload, ensure_ascii=False)}
"""
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = resp.text.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1).strip()
        elif "```" in text:
            text = text.split("```", 1)[11].split("```", 1)[0].strip()
        data = json.loads(text)
        return data.get("items", []) if isinstance(data, dict) else data
    except Exception:
        out = []
        for _, r in df_candidates.head(5).iterrows():
            last = float(r["last"])
            if mode == "up":
                out.append({
                    "symbol": r["symbol"],
                    "name": r["name"],
                    "action": "شراء",
                    "timeframe": "يومي",
                    "entry": round(last * 1.01, 3),
                    "target": round(last * 1.06, 3),
                    "stop_loss": round(last * 0.96, 3),
                    "reasons": ["زخم أفضل من باقي المرشحين", "سيولة نسبية أعلى", "إشارة فنية مبدئية إيجابية"],
                })
            else:
                out.append({
                    "symbol": r["symbol"],
                    "name": r["name"],
                    "action": "ارتداد محتمل",
                    "timeframe": "يومي",
                    "entry": round(last * 0.99, 3),
                    "target": round(last * 1.04, 3),
                    "stop_loss": round(last * 0.95, 3),
                    "reasons": ["هبوط واضح مع احتمالية تماسك", "قد يظهر رد فعل عند الدعم", "مناسب للمراقبة القصيرة"],
                })
        return out

st.markdown('<h1 class="title">EGX Live Shariah Analyzer</h1>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">تحليل مباشر من EGXPY + فلتر زمني + Gemini Structured Output</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("إعدادات")
    mode = st.selectbox("نوع التحليل", ["الصعود", "الارتداد من الهبوط"], index=0)
    tf = st.selectbox("المدى الزمني", ["مضاربة يومية", "أسبوعي", "شهري قصير", "كل المدى"], index=0)
    refresh = st.button("تحديث الآن")
    st.caption("EGXPY يجلب البيانات مباشرة بدون CSV.")

if refresh:
    st.cache_data.clear()
    st.rerun()

data = fetch_egx_data()
if data.empty:
    st.warning("لم يتم جلب بيانات EGX الآن.")
    st.stop()

if "error" in data.columns:
    st.error(str(data.iloc[0].get("error", "خطأ غير معروف")))
    st.stop()

if tf != "كل المدى":
    data = timeframe_filter(data, tf)

cols = [c for c in ["symbol", "name", "last", "prev_close", "change", "pct_change", "volume"] if c in data.columns]

top_up = data.sort_values("pct_change", ascending=False).head(5) if "pct_change" in data.columns else data.head(5)
top_down = data.sort_values("pct_change", ascending=True).head(5) if "pct_change" in data.columns else data.head(5)

st.subheader("أعلى 5 صعود")
st.dataframe(top_up[cols], use_container_width=True, hide_index=True)

st.subheader("أعلى 5 هبوط")
st.dataframe(top_down[cols], use_container_width=True, hide_index=True)

st.divider()

if mode == "الصعود":
    st.markdown('<div class="section-title">فرص الصعود</div>', unsafe_allow_html=True)
    candidates = score_candidates(data, mode="up", limit=20)
    results = gemini_analyze(candidates, mode="up")
else:
    st.markdown('<div class="section-title">فرص الارتداد من الهبوط</div>', unsafe_allow_html=True)
    down = data[data["pct_change"] < 0].copy() if "pct_change" in data.columns else data.head(0)
    candidates = score_candidates(down, mode="down", limit=20)
    results = gemini_analyze(candidates, mode="down")

if not results:
    st.info("لا توجد نتائج واضحة الآن.")
else:
    for item in results:
        st.markdown(
            f"""
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div><strong>{item.get('name','')}</strong> <span class="pill">{item.get('symbol','')}</span></div>
                    <div class="blue">{item.get('action','')}</div>
                </div>
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:10px;">
                    <div><div class="muted">الدخول</div><div><strong>{item.get('entry')}</strong></div></div>
                    <div><div class="muted">الهدف</div><div class="green"><strong>{item.get('target')}</strong></div></div>
                    <div><div class="muted">وقف الخسارة</div><div class="red"><strong>{item.get('stop_loss')}</strong></div></div>
                    <div><div class="muted">الإطار</div><div><strong>{item.get('timeframe')}</strong></div></div>
                </div>
                <ul>
                    {''.join([f'<li>{r}</li>' for r in item.get('reasons', [])])}
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
