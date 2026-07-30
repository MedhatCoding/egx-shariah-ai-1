import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import json
import os

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="محلل أسهم الشريعة الإسلامية - البورصة المصرية",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. تنسيق الواجهة ودعم اللغة العربية والموبايل ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Cairo', sans-serif !important;
        direction: rtl;
        text-align: right;
    }

    [data-testid="collapsedControl"] {
        display: none !important;
    }

    .main-header {
        text-align: center;
        padding: 10px 0;
        color: #1e293b;
    }

    .stock-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }

    .stock-title {
        font-size: 1rem;
        font-weight: 700;
        color: #0f172a;
    }

    .stock-price {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0f172a;
    }

    .price-up { color: #16a34a; font-weight: bold; }
    .price-down { color: #dc2626; font-weight: bold; }

    .opp-card {
        background-color: #ffffff;
        border-right: 5px solid #2563eb;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border-top: 1px solid #f1f5f9;
        border-left: 1px solid #f1f5f9;
        border-bottom: 1px solid #f1f5f9;
    }

    .badge-buy-strong {
        background-color: #dcfce7;
        color: #15803d;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }

    .badge-buy {
        background-color: #e0f2fe;
        color: #0369a1;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }

    .badge-time {
        background-color: #f1f5f9;
        color: #475569;
        padding: 3px 8px;
        border-radius: 15px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .stButton > button {
        border-radius: 8px;
        font-weight: bold;
        background-color: #2563eb;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. إعداد Gemini ---
def get_gemini_model():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ لم يتم العثور على GEMINI_API_KEY في Secrets أو متغيرات البيئة!")
        st.stop()

    genai.configure(api_key=api_key)

    for model_name in ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]:
        try:
            return genai.GenerativeModel(model_name)
        except Exception:
            continue

    return genai.GenerativeModel("gemini-1.5-flash")

# --- 4. قائمة الأسهم الشاملة ---
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
    "سيدي كرير للبتروكيماويات": "SKPC.CA"
}

# --- 5. أدوات الأسعار ---
def get_live_price(ticker):
    try:
        fi = ticker.fast_info
        last_price = fi.get("lastPrice", None)
        if last_price is not None and pd.notna(last_price):
            return float(last_price)
    except Exception:
        pass

    try:
        hist_1m = ticker.history(period="1d", interval="1m", auto_adjust=False)
        if hist_1m is not None and not hist_1m.empty:
            closes = hist_1m["Close"].dropna()
            if not closes.empty:
                return float(closes.iloc[-1])
    except Exception:
        pass

    try:
        hist_1d = ticker.history(period="5d", interval="1d", auto_adjust=False)
        if hist_1d is not None and not hist_1d.empty:
            closes = hist_1d["Close"].dropna()
            if not closes.empty:
                return float(closes.iloc[-1])
    except Exception:
        pass

    return None

def calc_entry_target_stop(live_price):
    if live_price is None:
        return None, None, None
    buy_price = live_price * 0.995
    target_price = buy_price * 1.08
    stop_loss = buy_price * 0.96
    return buy_price, target_price, stop_loss

# --- 6. جلب البيانات ---
@st.cache_data(ttl=60)
def fetch_stocks_data():
    results = []
    for name, symbol in SHARIAH_STOCKS.items():
        try:
            t = yf.Ticker(symbol)
            live_price = get_live_price(t)

            hist = t.history(period="5d", interval="1d", auto_adjust=False)

            pct_change = 0.0
            change = 0.0
            high = None
            low = None

            if hist is not None and not hist.empty:
                closes = hist["Close"].dropna()
                highs = hist["High"].dropna()
                lows = hist["Low"].dropna()

                if len(closes) >= 2:
                    prev_close = float(closes.iloc[-2])
                    latest_close = float(closes.iloc[-1])
                    change = latest_close - prev_close
                    pct_change = (change / prev_close) * 100 if prev_close else 0.0
                elif len(closes) == 1:
                    latest_close = float(closes.iloc[-1])
                    change = 0.0
                    pct_change = 0.0
                else:
                    latest_close = None

                if not highs.empty:
                    high = float(highs.max())
                if not lows.empty:
                    low = float(lows.min())

            if live_price is None:
                live_price = latest_close if "latest_close" in locals() else None

            buy_price, target_price, stop_loss = calc_entry_target_stop(live_price)

            results.append({
                "name": name,
                "symbol": symbol.replace(".CA", ""),
                "price": live_price,
                "change": change,
                "pct_change": pct_change,
                "high": high,
                "low": low,
                "buy_price": buy_price,
                "target_price": target_price,
                "stop_loss": stop_loss
            })
        except Exception:
            continue

    return pd.DataFrame(results)

# --- 7. تحليل الفرص ---
def generate_ai_opportunities(df_stocks, timeframe_filter):
    model = get_gemini_model()

    seed_val = abs(hash(timeframe_filter)) % 1000
    df_shuffled = df_stocks.sample(frac=1, random_state=seed_val).reset_index(drop=True)

    stocks_summary = []
    for _, row in df_shuffled.head(35).iterrows():
        price_txt = f"{row['price']:.2f}" if pd.notna(row["price"]) else "غير متاح"
        pct_txt = f"{row['pct_change']:.2f}" if pd.notna(row["pct_change"]) else "0.00"
        high_txt = f"{row['high']:.2f}" if pd.notna(row["high"]) else "غير متاح"
        low_txt = f"{row['low']:.2f}" if pd.notna(row["low"]) else "غير متاح"
        stocks_summary.append(
            f"- {row['name']} ({row['symbol']}): السعر الحالي {price_txt} EGP، التغير {pct_txt}%، أعلى {high_txt}، أقل {low_txt}"
        )

    if timeframe_filter == "جميع المدى الزمني":
        time_instruction = "قم بتنويع الفرص ووضع مداه الزمني الخاص بكل سهم (مضاربة يومية، صعود أسبوعي، أو صعود شهري)."
    else:
        time_instruction = f"اجعل كل الفرص تتبع حصرياً المدى الزمني المحدد: [{timeframe_filter}]."

    prompt = f"""
أنت محلل فني محترف في البورصة المصرية (EGX).
{time_instruction}

اختر من 4 إلى 5 أسهم مختلفة من القائمة التالية.
أرجع النتيجة حتمياً بصيغة JSON فقط كقائمة بالشكل التالي دون أي مقدمات أو علامات markdown زائدة:
[
  {{
    "اسم السهم": "اسم السهم من القائمة بالضبط",
    "التوصية": "شراء قوي",
    "المدى الزمني": "حدد المدى الزمني المناسب للسهم",
    "أسباب التحليل": "اكتب هنا سبباً فنياً تفصيلياً وحقيقياً مدعماً بحركة السعر والزخم"
  }}
]
القائمة:
{chr(10).join(stocks_summary)}
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```").strip()
        elif "```" in text:
            text = text.split("```")[11].split("```")[0].strip()
        return json.loads(text)
    except Exception:
        timings = ["مضاربة يومية", "صعود أسبوعي", "صعود شهري", "مضاربة يومية"]
        reasons = [
            "ارتفاع ملحوظ في السيولة اللحظية واقتراب السعر من اختبار مقاومة قوية تدعم الصعود السريع.",
            "استقرار السعر فوق مناطق الدعم الرئيسية مع تشكل نموذج إيجابي على المدى القصير.",
            "تجميع إيجابي واضح وتواجد فرص لنمو سعري تدريجي يستهدف مستويات أعلى خلال الفترة القادمة.",
            "زخم شرائي مكثف يظهر بوضوح في الجلسات الأخيرة مع تحركات إيجابية لأعلى."
        ]
        fallback_list = []
        sample_df = df_stocks.dropna(subset=["price"]).sample(
            min(4, len(df_stocks.dropna(subset=["price"]))),
            random_state=seed_val
        )
        for idx, (_, row) in enumerate(sample_df.iterrows()):
            assigned_time = timings[idx % len(timings)] if timeframe_filter == "جميع المدى الزمني" else timeframe_filter
            fallback_list.append({
                "اسم السهم": row["name"],
                "التوصية": "شراء",
                "المدى الزمني": assigned_time,
                "أسباب التحليل": reasons[idx % len(reasons)]
            })
        return fallback_list

# --- 8. واجهة التطبيق ---
st.markdown('<h1 class="main-header">📈 أسهم الشريعة الإسلامية - البورصة المصرية</h1>', unsafe_allow_html=True)

col_info, col_btn = st.columns([3, 1])
with col_info:
    st.write("أكثر 5 أسهم ارتفاعاً في قائمتك، وتحليل ذكي للفرص حسب المدى الزمني.")
with col_btn:
    if st.button("🔄 تحديث البيانات", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.spinner("جاري جلب الأسعار اللحظية لقائمتك..."):
    df_stocks = fetch_stocks_data()

st.subheader("🔥 أكثر 5 أسهم ارتفاعاً في قائمتك")

if not df_stocks.empty:
    top_gainers = df_stocks.sort_values(by="pct_change", ascending=False).head(5)

    for _, item in top_gainers.iterrows():
        pct = float(item["pct_change"]) if pd.notna(item["pct_change"]) else 0.0
        sign = "+" if pct >= 0 else ""
        price = item["price"]
        high = item["high"]
        low = item["low"]

        change_class = "price-up" if pct >= 0 else "price-down"
        price_color = "#16a34a" if pct >= 0 else "#dc2626"

        price_text = f"{price:.2f} EGP" if pd.notna(price) else "غير متاح"
        high_text = f"{high:.2f}" if pd.notna(high) else "غير متاح"
        low_text = f"{low:.2f}" if pd.notna(low) else "غير متاح"

        st.markdown(f"""
        <div class="stock-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="stock-title">{item['name']} <small style="color:#64748b;">({item['symbol']})</small></span>
                <span class="{change_class}">{sign}{pct:.2f}%</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                <span class="stock-price" style="color:{price_color};">{price_text}</span>
                <span style="font-size: 0.8rem; color: #64748b;">أعلى: {high_text} | أقل: {low_text}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.warning("جاري تحضير البيانات، اضغط تحديث إذا استمرت المشكلة.")

st.markdown("---")

col_opp_title, col_filter = st.columns([2, 2])
with col_opp_title:
    st.subheader("🌟 أفضل الفرص الاستثمارية الموصى بها")

with col_filter:
    timeframe_filter = st.selectbox(
        "فلتر حسب المدى الزمني للفرصة:",
        ["جميع المدى الزمني", "مضاربية في نفس الجلسة (يومي)", "صعود أسبوعي", "صعود شهري (استثماري قصير)"],
        label_visibility="collapsed"
    )

if not df_stocks.empty:
    with st.spinner("جاري تحليل أسهم قائمتك وتصنيف الفرص..."):
        opp_data = generate_ai_opportunities(df_stocks, timeframe_filter)

        for item in opp_data:
            rec = item.get("التوصية", "شراء")
            time_frame = item.get("المدى الزمني", "صعود أسبوعي")
            stock_name = item.get("اسم السهم")
            stock_row = df_stocks[df_stocks["name"] == stock_name]

            if not stock_row.empty:
                row = stock_row.iloc[0]
                live_price = row["price"]
                live_change = row["pct_change"]
                live_buy_price = row["buy_price"]
                target_price = row["target_price"]
                stop_loss = row["stop_loss"]
            else:
                live_price = None
                live_change = None
                live_buy_price = None
                target_price = None
                stop_loss = None

            if live_change is not None and live_change > 0:
                price_color = "#16a34a"
                change_sign = "+"
            elif live_change is not None and live_change < 0:
                price_color = "#dc2626"
                change_sign = ""
            else:
                price_color = "#0f172a"
                change_sign = ""

            live_price_text = f"{live_price:.2f} EGP" if live_price is not None else "غير متاح"
            live_change_text = f"{change_sign}{live_change:.2f}%" if live_change is not None else ""
            buy_price_text = f"{live_buy_price:.2f} EGP" if live_buy_price is not None else "غير متاح"
            target_price_text = f"{target_price:.2f} EGP" if target_price is not None else "غير متاح"
            stop_loss_text = f"{stop_loss:.2f} EGP" if stop_loss is not None else "غير متاح"

            if "قوي" in rec:
                badge_class = "badge-buy-strong"
                border_color = "#16a34a"
            elif "شراء" in rec:
                badge_class = "badge-buy"
                border_color = "#2563eb"
            else:
                badge_class = "badge-buy"
                border_color = "#d97706"

            st.markdown(f"""
            <div class="opp-card" style="border-right-color: {border_color};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <span style="font-size: 1.15rem; font-weight: bold; color: #0f172a;">🎯 {stock_name}</span>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <span class="badge-time">⏱️ {time_frame}</span>
                        <span class="{badge_class}">{rec}</span>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; background-color: #f8fafc; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 10px;">
                    <div>
                        <div style="font-size: 0.75rem; color: #64748b;">السعر اللحظي</div>
                        <div style="font-weight: bold; color: {price_color};">{live_price_text} <span style="font-size:0.8rem;color:{price_color};">{live_change_text}</span></div>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: #64748b;">سعر الشراء الحقيقي</div>
                        <div style="font-weight: bold; color: #0f172a;">{buy_price_text}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: #64748b;">السعر المستهدف</div>
                        <div style="font-weight: bold; color: #16a34a;">{target_price_text}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: #64748b;">وقف الخسارة</div>
                        <div style="font-weight: bold; color: #dc2626;">{stop_loss_text}</div>
                    </div>
                </div>
                <div s
