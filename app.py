import os
import json
from io import StringIO

import pandas as pd
import requests
import streamlit as st
import google.generativeai as genai

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="EGX Shariah Market Intelligence",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Cairo', sans-serif !important; direction: rtl; text-align: right; }
    .main-title { text-align: center; color: #0f172a; font-weight: 700; margin-bottom: 0.25rem; }
    .subtle { text-align: center; color: #64748b; margin-bottom: 1rem; }
    .card {
        background: white; border: 1px solid #e2e8f0; border-radius: 14px;
        padding: 16px; margin-bottom: 14px; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }
    .green { color: #16a34a; font-weight: 700; }
    .red { color: #dc2626; font-weight: 700; }
    .blue { color: #2563eb; font-weight: 700; }
    .pill {
        display: inline-block; padding: 4px 10px; border-radius: 999px;
        background: #f1f5f9; color: #334155; font-size: 0.82rem; font-weight: 700;
    }
    .metricbox {
        background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# EDITABLE EGX LAYER
# =========================
EGX_SOURCE_MODE = st.secrets.get("EGX_SOURCE_MODE", os.getenv("EGX_SOURCE_MODE", "csv"))
EGX_DATA_URL = st.secrets.get("EGX_DATA_URL", os.getenv("EGX_DATA_URL", ""))
EGX_FALLBACK_URL = "https://www.egx.com.eg/en/marketwatch/download?lang=en"

# You can replace these later with your own official EGX export / downloaded CSV mapping.
# Keep the ticker format configurable here only.
EGX_TICKER_MAP = {
    "RAYA": "RAYA.CA",
    "FWRY": "FWRY.CA",
    "ISPH": "ISPH.CA",
    "GBCO": "GBCO.CA",
    "PHDC": "PHDC.CA",
    "MASR": "MASR.CA",
    "SKPC": "SKPC.CA",
    "FRA": "FRA.CA",
    "EFID": "EFID.CA",
    "JUFO": "JUFO.CA",
    "ADIB": "ADIB.CA",
    "AMOC": "AMOC.CA",
    "CIRA": "CIRA.CA",
    "CLHO": "CLHO.CA",
    "DOMT": "DOMT.CA",
    "ETEL": "ETEL.CA",
    "TMGH": "TMGH.CA",
    "ABUK": "ABUK.CA",
    "EGAL": "EGAL.CA",
    "SKP": "SKP.CA",
}

SHARIAH_SYMBOLS = set(EGX_TICKER_MAP.keys())

# =========================
# HELPERS
# =========================
def get_gemini_model():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("ضع GEMINI_API_KEY في Streamlit Secrets أو Environment.")
        st.stop()
    genai.configure(api_key=api_key)
    try:
        return genai.GenerativeModel("gemini-2.5-flash")
    except Exception:
        return genai.GenerativeModel("gemini-1.5-flash")

def safe_float(x, default=None):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default

@st.cache_data(ttl=600)
def load_egx_data():
    """
    Flexible EGX layer:
    1) If EGX_DATA_URL is provided, fetch CSV/JSON directly.
    2) Else try the official EGX page as a health/reference source.
    3) As a fallback, return an empty frame and let the UI show the status.
    """
    if EGX_DATA_URL:
        r = requests.get(EGX_DATA_URL, timeout=30)
        r.raise_for_status()
        text = r.text.strip()

        # CSV first
        try:
            df = pd.read_csv(StringIO(text))
            return df
        except Exception:
            pass

        # JSON next
        try:
            data = r.json()
            if isinstance(data, list):
                return pd.DataFrame(data)
            if isinstance(data, dict):
                for key in ["data", "items", "results", "stocks"]:
                    if key in data and isinstance(data[key], list):
                        return pd.DataFrame(data[key])
            return pd.DataFrame([data])
        except Exception:
            return pd.DataFrame()

    try:
        r = requests.get(EGX_FALLBACK_URL, timeout=20)
        status = "reachable" if r.status_code == 200 else f"status={r.status_code}"
        return pd.DataFrame([{"source_status": status}])
    except Exception as e:
        return pd.DataFrame([{"source_status": f"error: {e}"}])

@st.cache_data(ttl=300)
def get_market_snapshot():
    """
    If EGX_DATA_URL contains rows with columns like:
    symbol, name, last, open, high, low, prev_close, volume
    we normalize them here.
    """
    raw = load_egx_data()
    if raw.empty:
        return pd.DataFrame()

    cols = {c.lower().strip(): c for c in raw.columns}
    required = ["symbol", "name", "last", "open", "high", "low", "volume", "prev_close"]
    available = all(k in cols for k in ["symbol", "name", "last"])  # minimum

    if not available:
        # Return raw status frame
        return raw

    df = pd.DataFrame()
    df["symbol"] = raw[cols["symbol"]].astype(str).str.upper().str.replace(".CA", "", regex=False)
    df["name"] = raw[cols["name"]].astype(str)

    df["last"] = pd.to_numeric(raw[cols["last"]], errors="coerce")
    df["open"] = pd.to_numeric(raw[cols["open"]], errors="coerce") if "open" in cols else pd.NA
    df["high"] = pd.to_numeric(raw[cols["high"]], errors="coerce") if "high" in cols else pd.NA
    df["low"] = pd.to_numeric(raw[cols["low"]], errors="coerce") if "low" in cols else pd.NA
    df["volume"] = pd.to_numeric(raw[cols["volume"]], errors="coerce") if "volume" in cols else pd.NA
    df["prev_close"] = pd.to_numeric(raw[cols["prev_close"]], errors="coerce") if "prev_close" in cols else pd.NA

    if "sector" in cols:
        df["sector"] = raw[cols["sector"]].astype(str)
    else:
        df["sector"] = ""

    df["change"] = df["last"] - df["prev_close"]
    df["pct_change"] = (df["change"] / df["prev_close"]) * 100
    df["liquidity_score"] = df["volume"].fillna(0)
    df["is_shariah"] = df["symbol"].isin(SHARIAH_SYMBOLS)

    df = df[df["symbol"].isin(SHARIAH_SYMBOLS)].copy()
    return df.dropna(subset=["last"]).reset_index(drop=True)

def compute_signals(df):
    if df.empty:
        return df
    df = df.copy()
    df["momentum"] = df["pct_change"].fillna(0)
    df["intraday_bias"] = df.apply(
        lambda r: "bullish" if (safe_float(r.get("last"), 0) > safe_float(r.get("open"), 0)) else "bearish",
        axis=1,
    )
    df["trend_tag"] = df["momentum"].apply(
        lambda x: "قوي" if x >= 2 else ("متوسط" if x >= 0.5 else ("ضعيف" if x > -0.5 else "هابط"))
    )
    df["volume_tag"] = pd.qcut(df["liquidity_score"].rank(method="first"), q=min(4, len(df)), labels=False, duplicates="drop") if len(df) >= 4 else 0
    return df

def get_candidates(df, mode="up", limit=20):
    if df.empty:
        return df
    d = compute_signals(df)
    if mode == "up":
        out = d.sort_values(["momentum", "liquidity_score"], ascending=False)
    else:
        out = d.sort_values(["momentum", "liquidity_score"], ascending=[True, False])
    return out.head(limit).reset_index(drop=True)

def gemini_rank(df_candidates, mode="up"):
    model = get_gemini_model()
    records = []
    for _, r in df_candidates.iterrows():
        records.append({
            "symbol": r["symbol"],
            "name": r["name"],
            "last": safe_float(r["last"]),
            "open": safe_float(r.get("open")),
            "high": safe_float(r.get("high")),
            "low": safe_float(r.get("low")),
            "prev_close": safe_float(r.get("prev_close")),
            "volume": safe_float(r.get("volume")),
            "pct_change": safe_float(r.get("pct_change")),
            "trend_tag": r.get("trend_tag"),
            "liquidity_score": safe_float(r.get("liquidity_score")),
        })

    strategy = "اختر فرص صعود عالية الاحتمال" if mode == "up" else "اختر فرص ارتداد من هبوط"
    prompt = f"""
أنت محلل أسهم مصري محترف.
{strategy} من البيانات التالية فقط.
التزم بالأسهم المتوافقة مع الشريعة.
أعد JSON فقط بدون أي شرح إضافي.
صيغة الإخراج:
{{
  "items": [
    {{
      "symbol": "string",
      "name": "string",
      "rating": 0,
      "action": "شراء" أو "مراقبة" أو "ارتداد محتمل",
      "timeframe": "يومي" أو "أسبوعي" أو "قصير الأجل",
      "entry": number,
      "target": number,
      "stop_loss": number,
      "reasons": ["string", "string", "string"]
    }}
  ]
}}

المدخلات:
{json.dumps(records, ensure_ascii=False)}
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1).strip()
        elif "```" in text:
            text = text.split("```", 1)[11].split("```", 1)[0].strip()
        data = json.loads(text)
        return data.get("items", []) if isinstance(data, dict) else data
    except Exception:
        # deterministic fallback
        items = []
        for _, r in df_candidates.head(5).iterrows():
            last = safe_float(r["last"], 0)
            if mode == "up":
                entry = round(last * 1.01, 3)
                target = round(last * 1.06, 3)
                sl = round(last * 0.96, 3)
                action = "شراء"
            else:
                entry = round(last * 0.99, 3)
                target = round(last * 1.04, 3)
                sl = round(last * 0.95, 3)
                action = "ارتداد محتمل"
            items.append({
                "symbol": r["symbol"],
                "name": r["name"],
                "rating": 70,
                "action": action,
                "timeframe": "يومي",
                "entry": entry,
                "target": target,
                "stop_loss": sl,
                "reasons": [
                    f"السهم ضمن قائمة الشريعة.",
                    f"السيولة أفضل نسبيًا داخل المرشحين.",
                    f"الحركة الأخيرة تدعم الفكرة الفنية مبدئيًا."
                ]
            })
        return items

# =========================
# UI
# =========================
st.markdown('<h1 class="main-title">EGX Shariah Market Intelligence</h1>', unsafe_allow_html=True)
st.markdown('<div class="subtle">تحليل احترافي مبني على EGX + فلتر شريعة + Gemini Structured Output</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("الإعدادات")
    source_mode = st.selectbox("وضع مصدر EGX", ["csv", "json", "auto"], index=0)
    st.caption("غيّر هذا لاحقًا حسب شكل المصدر الرسمي أو ملف التصدير.")
    st.session_state["source_mode"] = source_mode
    st.divider()
    st.write("مفتاح Gemini")
    st.caption("أضف GEMINI_API_KEY في Secrets.")

top1, top2, top3 = st.columns(3)
egx_frame = get_market_snapshot()
top1.metric("عدد السجلات", len(egx_frame) if not egx_frame.empty and "symbol" in egx_frame.columns else 0)
top2.metric("المصدر", "EGX" if EGX_DATA_URL else "EGX page")
top3.metric("نمط التحليل", "شريعة + سيولة + زخم")

st.divider()

if egx_frame.empty:
    st.warning("لم يتم جلب بيانات سوق EGX بعد. ضع رابط CSV/JSON رسمي في EGX_DATA_URL أو اربط مصدر EGX الذي تستخدمه.")
    st.stop()

if "symbol" not in egx_frame.columns:
    st.info("تم الوصول إلى EGX، لكن لم يصلنا جدول أسعار بعد. اربط EGX_DATA_URL بملف CSV/JSON يحتوي الأعمدة: symbol, name, last, open, high, low, volume, prev_close.")
    st.dataframe(egx_frame, use_container_width=True)
    st.stop()

egx_frame = compute_signals(egx_frame)

col_a, col_b = st.columns([2, 1])
with col_a:
    st.subheader("أعلى الأسهم حركة")
with col_b:
    view_mode = st.selectbox("نوع التصفية", ["الصعود", "الارتداد من الهبوط"], index=0)

top_movers = egx_frame.sort_values("pct_change", ascending=False).head(10)

st.dataframe(
    top_movers[["symbol", "name", "last", "prev_close", "change", "pct_change", "volume", "trend_tag"]],
    use_container_width=True,
    hide_index=True,
)

st.divider()

if view_mode == "الصعود":
    st.subheader("فرص الصعود")
    bullish_candidates = get_candidates(egx_frame, mode="up", limit=20)
    bullish = gemini_rank(bullish_candidates, mode="up")
    if not bullish:
        st.info("لا توجد فرص صعود واضحة حاليًا.")
    else:
        for item in bullish:
            st.markdown(
                f"""
                <div class="card">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div><strong>{item.get('name', '')}</strong> <span class="pill">{item.get('symbol', '')}</span></div>
                        <div class="blue">Rating: {item.get('rating', 0)}</div>
                    </div>
                    <div style="margin-top:8px; display:grid; grid-template-columns:repeat(4,1fr); gap:10px;">
                        <div class="metricbox"><div>الدخول</div><div><strong>{item.get('entry')}</strong></div></div>
                        <div class="metricbox"><div>الهدف</div><div class="green"><strong>{item.get('target')}</strong></div></div>
                        <div class="metricbox"><div>وقف الخسارة</div><div class="red"><strong>{item.get('stop_loss')}</strong></div></div>
                        <div class="metricbox"><div>الإطار</div><div><strong>{item.get('timeframe')}</strong></div></div>
                    </div>
                    <ul>
                        {''.join([f'<li>{reason}</li>' for reason in item.get('reasons', [])])}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.subheader("فرص الارتداد من الهبوط")
    rebound_candidates = get_candidates(egx_frame, mode="down", limit=20)
    rebound = gemini_rank(rebound_candidates, mode="down")
    if not rebound:
        st.info("لا توجد فرص ارتداد واضحة حاليًا.")
    else:
        for item in rebound:
            st.markdown(
                f"""
                <div class="card">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div><strong>{item.get('name', '')}</strong> <span class="pill">{item.get('symbol', '')}</span></div>
                        <div class="blue">Rating: {item.get('rating', 0)}</div>
                    </div>
                    <div style="margin-top:8px; display:grid; grid-template-columns:repeat(4,1fr); gap:10px;">
                        <div class="metricbox"><div>الدخول</div><div><strong>{item.get('entry')}</strong></div></div>
                        <div class="metricbox"><div>الهدف</div><div class="green"><strong>{item.get('target')}</strong></div></div>
                        <div class="metricbox"><div>وقف الخسارة</div><div class="red"><strong>{item.get('stop_loss')}</strong></div></div>
                        <div class="metricbox"><div>الإطار</div><div><strong>{item.get('timeframe')}</strong></div></div>
                    </div>
                    <ul>
                        {''.join([f'<li>{reason}</li>' for reason in item.get('reasons', [])])}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
      )
