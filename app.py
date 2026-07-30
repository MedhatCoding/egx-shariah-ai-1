import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import json
import os
import requests

st.set_page_config(
    page_title="محلل أسهم الشريعة الإسلامية - البورصة المصرية",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
html, body, [class*="st-"] { font-family: 'Cairo', sans-serif !important; direction: rtl; text-align: right; }
[data-testid="collapsedControl"] { display: none !important; }
.main-header { text-align: center; padding: 10px 0; color: #1e293b; }
.stock-card, .opp-card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.03);
}
.opp-card { border-right: 5px solid #2563eb; }
.stock-title { font-size: 1rem; font-weight: 700; color: #0f172a; }
.stock-price { font-size: 1.15rem; font-weight: 700; color: #0f172a; }
.price-up { color: #16a34a; font-weight: bold; }
.price-down { color: #dc2626; font-weight: bold; }
.badge-buy-strong, .badge-buy, .badge-time, .badge-neutral {
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: bold;
    display: inline-block;
}
.badge-buy-strong { background-color: #dcfce7; color: #15803d; }
.badge-buy { background-color: #e0f2fe; color: #0369a1; }
.badge-time { background-color: #f1f5f9; color: #475569; font-size: 0.75rem; }
.badge-neutral { background-color: #fef3c7; color: #b45309; }
.stButton > button {
    border-radius: 8px;
    font-weight: bold;
    background-color: #2563eb;
    color: white;
}
</style>
""", unsafe_allow_html=True)

EGX_URL = "https://www.egx.com.eg/en/marketwatch/download?lang=en"

SHARIAH_STOCKS = {
    "القاهرة للخدمات التعليمية": "CAED.CA",
    "شركة مستشفي كليوباترا": "CLHO.CA",
    "كوبر للاستثمار التجاري والتطوير العقاري": "COPR.CA",
    "القاهرة للزيوت والصابون": "COSG.CA",
    "شركة القاهرة للأدوية": "CPCI.CA",
    "كريستمارك للمقاولات والتطوير العمراني": "CRST.CA",
    "ديجتايز للاستثمار والتقنية": "DGTZ.CA",
    "العربية لاستصلاح الاراضي": "EALR.CA",
    "مطاحن شرق الدلتا": "EDFM.CA",
    "العامة لاستصلاح الاراضي و التنمية": "AALR.CA",
    "الشركة العربية لادارة وتطوير الاصول": "ACAMD.CA",
    "مصرف أبو ظبي الإسلامي - مصر": "ADIB.CA",
    "اراب للتنمية والاستثمار العقاري": "ADRI.CA",
    "مطاحن ومخابز الاسكندرية": "AFMC.CA",
    "اطلس للاستثمار والصناعات الغذائية": "AIFI.CA",
    "اجواء للصناعات الغذائية - مصر": "AJWA.CA",
    "الاسكندرية للخدمات الطبية - المركز الطبي": "AMES.CA",
    "الاسكندرية للزيوت المعدنية": "AMOC.CA",
    "نوفيدا للإستثمار والتكنولوجيا": "AMPI.CA",
    "ايديتا للصناعات الغذائية": "EFID.CA",
    "مصر للألومنيوم": "EGAL.CA",
    "غاز مصر": "EGAS.CA",
    "المصريين للاسكان والتنمية والتعمير": "EHDR.CA",
    "المصرية للمشروعات السياحية": "EITP.CA",
    "النصر لتصنيع الحاصلات الزراعية": "ELNA.CA",
    "بنك فيصل الاسلامي المصري - بالدولار": "FAITA.CA",
    "فيوتشر كير للصناعات الطبية": "FCMD.CA",
    "الاولي للاستثمار والتنمية العقارية": "FIRE.CA",
    "العبوات الدوائية المتطورة": "APPC.CA",
    "العربيه وبولفارا للغزل والنسيج - يونيراب": "APSW.CA",
    "العربية للاسمنت": "ARCC.CA",
    "التوفيق للتأجير التمويلي - أية.تي.ليس": "ATLC.CA",
    "مصر الوطنية للصلب - عتاقة": "ATQA.CA",
    "الاسكندرية للادوية والصناعات الكيماوية": "AXPH.CA",
    "بي اي دي- البدر للاستثمار والتنمية": "BIDI.CA",
    "بي اي جي للتجارة والاستثمار": "BIGP.CA",
    "جلاكسو سميث كلاين": "BIOC.CA",
    "الفنار للمقاولات العمومية والإنشاءات الهندسية": "FNAR.CA",
    "الغربية الإسلامية للتنمية العمرانية": "GIHD.CA",
    "مجموعة جي . أم . سي للاستثمارات الصناعية": "GMCI.CA",
    "جي بي آي للنمو العمراني": "GPIM.CA",
    "جلوبال تليكوم القابضة": "GTHE.CA",
    "الدولية للأسمدة والكيماويات": "ICFC.CA",
    "المشروعات الصناعية والهندسية": "IEEC.CA",
    "الدوليه للمحاصيل الزراعيه": "IFAP.CA",
    "المجموعة المتكاملة للأعمال الهندسية": "INEG.CA",
    "سماد مصر (ايجيفرت)": "SMFR.CA",
    "الاسكندرية للغزل والنسيج (سبينهوس)": "SPIN.CA",
    "سبيد ميديكال": "SPMD.CA",
    "تنمية للاستثمار العقاري": "TANM.CA",
    "مطاحن مصر العليا": "UEFM.CA",
    "الاتحاد الصيدلي للخدمات الطبية والاستثمار": "UPMS.CA",
    "فرتيكا للصناعة و التجارة": "VERT.CA",
    "وادي كوم امبو لاستصلاح الاراضي": "WKOL.CA",
    "الزيوت المستخلصة ومنتجاتها": "ZEOT.CA",
    "فوديكو - الاسماعيلية الوطنية للصناعات الغذائية": "INFI.CA",
    "الاسماعيلية مصر للدواجن": "ISMA.CA",
    "الحديد والصلب للمناجم والمحاجر": "ISMQ.CA",
    "جهينة للصناعات الغذائية": "JUFO.CA",
    "النصر للملابس والمنسوجات - كابو": "KABO.CA",
    "مصر بني سويف للاسمنت": "MBSC.CA",
    "مصر للاسمنت - قنا": "MCQE.CA",
    "ماكرو جروب": "MCRO.CA",
    "مصر لإنتاج الأسمدة - موبكو": "MFPC.CA",
    "مصر لصناعة الكيماويات": "MICH.CA",
    "مطاحن ومخابز شمال القاهرة": "MILS.CA",
    "مصر انتركونتنتال لصناعة الجرانيت والرخام": "MISR.CA",
    "المصرية الكويتية للاستثمار والتجارة": "MKIT.CA",
    "مرسى مرسى علم للتنمية السياحية": "MMAT.CA",
    "المصرية لنظم التعليم الحديثة": "MOED.CA",
    "مصر للزيوت والصابون": "MOSC.CA",
    "ممفيس للادوية والصناعات الكيماوية": "MPCI.CA",
    "المنصورة للدواجن": "MPCO.CA",
    "ام.ام جروب للصناعة والتجارة العالمية": "MTIE.CA",
    "النصر للاعمال المدنية": "NCCW.CA",
    "النيل لحليج الاقطان": "NCGC.CA",
    "شمال الصعيد للتنمية والانتاج الزراعي (نيوداب)": "NEDA.CA",
    "مستشفى النزهة الدولي": "NINH.CA",
    "شركة العبور للإستثمار العقاري": "OBRI.CA",
    "اكتوبر فارما": "OCPH.CA",
    "البويات والصناعات الكيماوية - باكين": "PACH.CA",
    "بريميم هيلثكير جروب": "PHGC.CA",
    "القاهرة للدواجن": "POUL.CA",
    "الشركة العامة لمنتجات السيراميك والبورسلين": "PRCL.CA",
    "الاستثمار العقاري العربي - اليكو": "RREI.CA",
    "رووبكس العالمية لتصنيع البلاستيك والاكريليك": "RUBX.CA",
    "بنك البركة مصر": "SAUD.CA",
    "اسمنت سيناء": "SCEM.CA",
    "مطاحن ومخابز جنوب القاهرة وگيزة": "SCFM.CA",
    "سبأ الدولية للأدوية والصناعات الكيماوية": "SIPC.CA",
    "سيدي كرير للبتروكيماويات": "SKPC.CA",
}

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

@st.cache_data(ttl=300)
def fetch_egx_reference():
    try:
        r = requests.get(EGX_URL, timeout=15)
        return "EGX market data page reachable" if r.status_code == 200 else "EGX market data page unavailable"
    except Exception:
        return "EGX market data page unavailable"

@st.cache_data(ttl=180)
def fetch_stocks_data():
    rows = []
    for name, symbol in SHARIAH_STOCKS.items():
        try:
            hist = yf.Ticker(symbol).history(period="10d", interval="1d")
            if hist is None or hist.empty:
                continue
            close = hist["Close"].dropna()
            high = hist["High"].dropna()
            low = hist["Low"].dropna()
            volume = hist["Volume"].dropna()
            if len(close) >= 2:
                current = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                change = current - prev
                pct_change = (change / prev) * 100 if prev else 0
            else:
                current = float(close.iloc[-1])
                change = 0.0
                pct_change = 0.0
            ma5 = float(close.tail(5).mean()) if len(close) >= 5 else float(close.mean())
            ma10 = float(close.mean())
            vol_avg = float(volume.tail(5).mean()) if len(volume) >= 5 else float(volume.mean()) if len(volume) else 0.0
            recent_high = float(high.tail(5).max()) if len(high) >= 1 else current
            recent_low = float(low.tail(5).min()) if len(low) >= 1 else current
            rows.append({
                "name": name,
                "symbol": symbol.replace(".CA", ""),
                "price": current,
                "change": change,
                "pct_change": pct_change,
                "high": float(high.max()) if len(high) else current,
                "low": float(low.min()) if len(low) else current,
                "ma5": ma5,
                "ma10": ma10,
                "vol_avg": vol_avg,
                "recent_high": recent_high,
                "recent_low": recent_low,
            })
        except Exception:
            continue
    return pd.DataFrame(rows)

def build_market_context(df):
    df = df.copy()
    df["trend_score"] = (df["price"] - df["ma5"]) / df["ma5"].replace(0, pd.NA) * 100
    df["volume_score"] = df["vol_avg"].fillna(0)
    df["momentum_score"] = df["pct_change"].fillna(0)
    return df

def prepare_candidates(df, mode):
    df = build_market_context(df)
    if mode == "الصعود":
        cand = df.sort_values(["momentum_score", "volume_score"], ascending=False)
    else:
        cand = df[df["pct_change"] < 0].sort_values(["pct_change", "volume_score"], ascending=[True, False])
    return cand.head(20).reset_index(drop=True)

def gemini_structured_analysis(df_candidates, mode, timeframe_filter):
    model = get_gemini_model()
    payload = []
    for _, r in df_candidates.iterrows():
        payload.append({
            "name": r["name"],
            "symbol": r["symbol"],
            "price": round(float(r["price"]), 4),
            "pct_change": round(float(r["pct_change"]), 4),
            "high": round(float(r["high"]), 4),
            "low": round(float(r["low"]), 4),
            "ma5": round(float(r["ma5"]), 4),
            "ma10": round(float(r["ma10"]), 4),
            "vol_avg": round(float(r["vol_avg"]), 4),
            "recent_high": round(float(r["recent_high"]), 4),
            "recent_low": round(float(r["recent_low"]), 4),
        })
    instruction = "اختر الأسهم المرشحة للصعود" if mode == "الصعود" else "اختر الأسهم الهابطة المرشحة للارتداد"
    if timeframe_filter == "جميع المدى الزمني":
        time_instruction = "يمكنك توزيع الفرص بين يومي وأسبوعي وشهري قصير حسب ما تراه مناسبًا."
    else:
        time_instruction = f"التزم حصريًا بالمدى الزمني التالي: {timeframe_filter}."
    prompt = f"""
أنت محلل فني للأسهم المصرية المتوافقة مع الشريعة.
{instruction} فقط من البيانات التالية.
{time_instruction}
أعد JSON فقط بصيغة قائمة، كل عنصر يحتوي المفاتيح:
اسم السهم، التوصية، المدى الزمني، سعر الشراء، السعر المستهدف، وقف الخسارة، أسباب التحليل.
لا تضف أي نص خارج JSON.
المدخلات:
{json.dumps(payload, ensure_ascii=False)}
"""
    try:
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1).strip()
        elif "```" in text:
            text = text.split("```", 1)[11].split("```", 1)[0].strip()
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("items", [])
        return data[:5]
    except Exception:
        out = []
        if df_candidates.empty:
            return out
        for _, r in df_candidates.head(4).iterrows():
            price = float(r["price"])
            if mode == "الصعود":
                rec, tgt, sl = "شراء", price * 1.08, price * 0.96
                reason = "زخم إيجابي وسيولة أفضل من باقي القائمة، مع احتمالية استمرار الحركة إذا ثبت فوق متوسطه القصير."
            else:
                rec, tgt, sl = "ارتداد محتمل", price * 1.06, price * 0.95
                reason = "هبوط واضح مع تماسك نسبي قرب دعم، ما يمنحه احتمال رد فعل صاعد إذا ظهرت سيولة شرائية."
            out.append({
                "اسم السهم": r["name"],
                "التوصية": rec,
                "المدى الزمني": "مضاربة يومية",
                "سعر الشراء": f"{price:.2f}",
                "السعر المستهدف": f"{tgt:.2f}",
                "وقف الخسارة": f"{sl:.2f}",
                "أسباب التحليل": reason,
            })
        return out

st.markdown('<h1 class="main-header">📈 أسهم الشريعة الإسلامية - البورصة المصرية</h1>', unsafe_allow_html=True)

c1, c2 = st.columns([3, 1])
with c1:
    st.write("تحليل أولي للأسهم الحلال عالية السيولة، مع فلتر صعود وفرص ارتداد من الهبوط.")
with c2:
    if st.button("🔄 تحديث البيانات", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.caption(fetch_egx_reference())

with st.spinner("جاري جلب الأسعار وتحضير التحليل..."):
    df_stocks = fetch_stocks_data()

st.subheader("🔥 أعلى 5 أسهم حركة")
if not df_stocks.empty:
    top = df_stocks.sort_values(by="pct_change", ascending=False).head(5)
    for _, item in top.iterrows():
        cls = "price-up" if item["pct_change"] >= 0 else "price-down"
        sign = "+" if item["pct_change"] >= 0 else ""
        st.markdown(
            f'''
            <div class="stock-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span class="stock-title">{item["name"]} <small style="color:#64748b;">({item["symbol"]})</small></span>
                    <span class="{cls}">{sign}{item["pct_change"]:.2f}%</span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
                    <span class="stock-price">{item["price"]:.2f} EGP</span>
                    <span style="font-size:0.8rem;color:#64748b;">أعلى: {item["high"]:.2f} | أقل: {item["low"]:.2f}</span>
                </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
else:
    st.warning("لا توجد بيانات كافية الآن.")

st.markdown("---")
left, right = st.columns([2, 2])
with left:
    st.subheader("🌟 فرص الصعود")
with right:
    timeframe_filter = st.selectbox(
        "فلتر حسب المدى الزمني للفرصة:",
        ["جميع المدى الزمني", "مضاربية في نفس الجلسة (يومي)", "صعود أسبوعي", "صعود شهري (استثماري قصير)"],
        label_visibility="collapsed",
    )

if not df_stocks.empty:
    with st.spinner("جاري استخراج فرص الصعود..."):
        bullish_candidates = prepare_candidates(df_stocks, "الصعود")
        bullish = gemini_structured_analysis(bullish_candidates, "الصعود", timeframe_filter)

        for item in bullish:
            stock_name = item.get("اسم السهم")
            rec = item.get("التوصية", "شراء")
            tframe = item.get("المدى الزمني", "مضاربة يومية")
            row = df_stocks[df_stocks["name"] == stock_name]
            live_price = float(row.iloc[0]["price"]) if not row.empty else None
            live_change = float(row.iloc[0]["pct_change"]) if not row.empty else None

            st.markdown(
                f'''
                <div class="opp-card" style="border-right-color:#16a34a;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                        <span style="font-size:1.15rem;font-weight:bold;color:#0f172a;">🎯 {stock_name}</span>
                        <div style="display:flex;gap:8px;align-items:center;">
                            <span class="badge-time">⏱️ {tframe}</span>
                            <span class="badge-buy-strong">{rec}</span>
                        </div>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;background-color:#f8fafc;padding:10px;border-radius:8px;text-align:center;margin-bottom:10px;">
                        <div>
                            <div style="font-size:0.75rem;color:#64748b;">السعر اللحظي</div>
                            <div style="font-weight:bold;color:#0f172a;">{(f'{live_price:.2f} EGP' if live_price is not None else 'غير متاح')} <span style="font-size:0.8rem;color:#64748b;">{(f'({live_change:+.2f}%)' if live_change is not None else '')}</span></div>
                        </div>
                        <div>
                            <div style="font-size:0.75rem;color:#64748b;">سعر الدخول/الشراء</div>
                            <div style="font-weight:bold;color:#0f172a;">{item.get('سعر الشراء')} EGP</div>
                        </div>
                        <div>
                            <div style="font-size:0.75rem;color:#64748b;">السعر المستهدف</div>
                            <div style="font-weight:bold;color:#16a34a;">{item.get('السعر المستهدف')} EGP</div>
                        </div>
                        <div>
                            <div style="font-size:0.75rem;color:#64748b;">وقف الخسارة</div>
                            <div style="font-weight:bold;color:#dc2626;">{item.get('وقف الخسارة')} EGP</div>
                        </div>
                    </div>
                    <div style="font-size:0.9rem;color:#334155;"><strong>💡 أسباب التحليل:</strong> {item.get('أسباب التحليل')}</div>
                </div>
                ''',
                unsafe_allow_html=True,
            )

st.markdown("---")
st.subheader("🟦 فرص الارتداد من الهبوط")

if not df_stocks.empty:
    down = df_stocks[df_stocks["pct_change"] < 0].sort_values(by="pct_change", ascending=True)
    if not down.empty:
        with st.spinner("جاري استخراج فرص الارتداد..."):
            rebound_candidates = prepare_candidates(down, "الارتداد")
            rebound = gemini_structured_analysis(rebound_candidates, "الارتداد", timeframe_filter)

            for item in rebound:
                stock_name = item.get("اسم السهم")
                rec = item.get("التوصية", "ارتداد محتمل")
                tframe = item.get("المدى الزمني", "مضاربة يومية")
                row = df_stocks[df_stocks["name"] == stock_name]
                live_price = float(row.iloc[0]["price"]) if not row.empty else None
                live_change = float(row.iloc[0]["pct_change"]) if not row.empty else None

                st.markdown(
                    f'''
                    <div class="opp-card" style="border-right-color:#7c3aed;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                            <span style="font-size:1.15rem;font-weight:bold;color:#0f172a;">🟦 {stock_name}</span>
                            <div style="display:flex;gap:8px;align-items:center;">
                                <span class="badge-time">⏱️ {tframe}</span>
                                <span class="badge-neutral">{rec}</span>
                            </div>
                        </div>
                        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;background-color:#f8fafc;padding:10px;border-radius:8px;text-align:center;margin-bottom:10px;">
                            <div>
                                <div style="font-size:0.75rem;color:#64748b;">السعر اللحظي</div>
                                <div style="font-weight:bold;color:#0f172a;">{(f'{live_price:.2f} EGP' if live_price is not None else 'غير متاح')} <span style="font-size:0.8rem;color:#64748b;">{(f'({live_change:+.2f}%)' if live_change is not None else '')}</span></div>
                            </div>
                            <div>
                                <div style="font-size:0.75rem;color:#64748b;">سعر الدخول/الشراء</div>
                                <div style="font-weight:bold;color:#0f172a;">{item.get('سعر الشراء')} EGP</div>
                            </div>
                            <div>
                                <div style="font-size:0.75rem;color:#64748b;">السعر المستهدف</div>
                                <div style="font-weight:bold;color:#16a34a;">{item.get('السعر المستهدف')} EGP</div>
                            </div>
                            <div>
                                <div style="font-size:0.75rem;color:#64748b;">وقف الخسارة</div>
                                <div style="font-weight:bold;color:#dc2626;">{item.get('وقف الخسارة')} EGP</div>
                            </div>
                        </div>
                
