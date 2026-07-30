# EGX Shariah Market Intelligence

تطبيق Streamlit احترافي لتحليل الأسهم المتوافقة مع الشريعة في السوق المصري اعتمادًا على طبقة EGX قابلة للتعديل، مع Gemini Structured Output.

## الفكرة
- إدخال بيانات EGX من CSV أو JSON رسمي.
- فلترة الأسهم المتوافقة مع الشريعة.
- ترتيب الفرص حسب الزخم والسيولة.
- استخدام Gemini لإخراج JSON منظم للفرص.

## الملفات
- `app.py`
- `requirements.txt`
- `README.md`

## التشغيل المحلي
```bash
pip install -r requirements.txt
streamlit run app.py
