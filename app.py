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

st.set_page_config(page_title="EGX Analyzer", page_icon="📈", layout="wide")

SHARIAH_SYMBOLS = {
    "RAYA", "FWRY", "ISPH", "GBCO", "PHDC", "MASR", "SKPC", "FRA",
    "EFID", "JUFO", "ADIB", "AMOC", "CIRA", "CLHO", "DOMT", "ETEL",
    "TMGH", "ABUK", "EGAL", "SKP"
}

def get_client():
    key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        st.error("ضع GEMINI_API_KEY في Secrets.")
        st.stop()
    return genai.Client(api_key=key)

@st.cache_data(ttl=60)
def load_data():
    if egxpy is None:
        return pd.DataFrame([{"error": "egxpy import failed"}])

    funcs = []
    for name in dir(egxpy):
        if callable(getattr(egxpy, name)) and any(k in name.lower() for k in ["intraday", "daily", "download"]):
            funcs.append(name)

    for name in funcs:
        try:
            fn = getattr(egxpy, name)
            sig = inspect.signature(fn)
            kwargs = {}
            if "symbol" in sig.parameters:
                kwargs["symbol"] = None
            if "interval" in sig.parameters:
                kwargs["interval"] = "1m"
            if "period" in sig.parameters:
                kwargs["period"] = "1d"

            df = fn(**kwargs)
            if isinstance(df, pd.DataFrame) and not df.empty:
                cols = {c.lower(): c for c in df.columns}
                if not all(k in cols for k in ["symbol", "name", "last"]):
                    continue
                out = pd.DataFrame()
                out["symbol"] = df[cols["symbol"]].astype(str).str.upper()
                out["name"] = df[cols["name"]].astype(str)
                out["last"] = pd.to_numeric(df[cols["last"]], errors="coerce")
                out["volume"] = pd.to_numeric(df[cols["volume"]], errors="coerce") if "volume" in cols else pd.NA
                out["prev_close"] = pd.to_numeric(df[cols["prev_close"]], errors="coerce") if "prev_close" in cols else pd.NA
                out["pct_change"] = ((out["last"] - out["prev_close"]) / out["prev_close"]) * 100
                out = out[out["symbol"].isin(SHARIAH_SYMBOLS)].dropna(subset=["last"])
                if not out.empty:
                    return out.reset_index(drop=True)
        except Exception:
            continue

    return pd.DataFrame([{"error": "No compatible EGXPY function worked"}])

def analyze(df, mode):
    client = get_client()
    sample = df.head(10)[["symbol", "name", "last", "volume", "pct_change"]].to_dict(orient="records")
    prompt = f"""
أعطِ JSON فقط.
اختر أفضل 5 أسهم من البيانات التالية حسب {mode}.
الهيكل:
{{"items":[{{"symbol":"", "name":"", "action":"", "entry":0, "target":0, "stop_loss":0}}]}}
البيانات:
{json.dumps(sample, ensure_ascii=False)}
"""
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    text = resp.text.strip()
    if "```" in text:
        text = text.split("```", 1)[1].split("```", 1).strip()
    try:
        data = json.loads(text)
        return data.get("items", [])
    except Exception:
        return []

st.title("EGX Analyzer")

mode = st.selectbox("التحليل", ["الصعود", "الهبوط"])
refresh = st.button("تحديث")

if refresh:
    st.cache_data.clear()
    st.rerun()

df = load_data()

if "error" in df.columns:
    st.error(df.iloc["error"])
    st.stop()

st.subheader("أعلى 5 صعود")
st.dataframe(df.sort_values("pct_change", ascending=False).head(5), use_container_width=True, hide_index=True)

st.subheader("أعلى 5 هبوط")
st.dataframe(df.sort_values("pct_change", ascending=True).head(5), use_container_width=True, hide_index=True)

st.subheader("النتائج")
results = analyze(df, mode)
if results:
    st.json(results)
else:
    st.info("لا توجد نتائج واضحة الآن.")
