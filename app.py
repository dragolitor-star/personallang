import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from gtts import gTTS
import io
import pandas as pd
import datetime
import matplotlib.pyplot as plt

# --- 1. AYARLAR VE BAĞLANTI ---
st.set_page_config(page_title="My Life OS", page_icon="🧠", layout="wide")

if not firebase_admin._apps:
    try:
        key_dict = dict(st.secrets["firebase"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Bağlantı Hatası: {e}")
        st.stop()

db = firestore.client()

# --- 2. ORTAK FONKSİYONLAR ---
def save_to_db(collection_name, data):
    """Veriyi belirtilen koleksiyona kaydeder"""
    data["created_at"] = firestore.SERVER_TIMESTAMP
    # Tarih objesini string'e çeviriyoruz
    if "date" in data and isinstance(data["date"], datetime.date):
        data["date_str"] = data["date"].strftime("%Y-%m-%d")
    # Vade tarihi varsa onu da çevir
    if "due_date" in data and isinstance(data["due_date"], datetime.date):
        data["due_date_str"] = data["due_date"].strftime("%Y-%m-%d")
    
    db.collection(collection_name).add(data)
    st.toast(f"✅ Kayıt Başarılı: {collection_name}")

def get_data(collection_name):
    """Koleksiyondaki tüm veriyi çeker"""
    try:
        docs = db.collection(collection_name).order_by("created_at", direction=firestore.Query.DESCENDING).stream()
        items = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            items.append(item)
        return pd.DataFrame(items)
    except:
        return pd.DataFrame()

def speak(text, lang='en'):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp, format='audio/mp3')
    except: pass

def calculate_totals(df):
    if df.empty: return 0, 0, 0
    df['date_dt'] = pd.to_datetime(df['date_str'])
    today = pd.Timestamp.now().normalize()
    start_week = today - pd.Timedelta(days=today.dayofweek)
    start_month = today.replace(day=1)
    
    d_sum = df[df['date_dt'] == today]['amount'].sum()
    w_sum = df[df['date_dt'] >= start_week]['amount'].sum()
    m_sum = df[df['date_dt'] >= start_month]['amount'].sum()
    return d_sum, w_sum, m_sum

# --- 3. ARAYÜZ VE NAVİGASYON ---
st.sidebar.title("🚀 Life OS")
main_module = st.sidebar.selectbox(
    "Modül Seç", 
    ["Dil Asistanı", "Fiziksel Takip", "Finans Merkezi"]
)

# ==========================================
# MODÜL 1 & 2 (ÖZET GEÇİLDİ - AYNEN KORUNUYOR)
# ==========================================
if main_module == "Dil Asistanı":
    st.title("🇩🇪 🇬🇧 Dil Asistanı")
    st.info("Dil modülü aktif.")
    # (Eski kodlarını buraya ekleyebilirsin)

elif main_module == "Fiziksel Takip":
    st.title("💪 Fiziksel Takip")
    st.info("Spor ve sağlık modülü aktif.")
    # (Eski kodlarını buraya ekleyebilirsin)

# ==========================================
# MODÜL 3: FİNANS MERKEZİ (YENİLENMİŞ & GELİŞMİŞ)
# ==========================================
elif main_module == "Finans Merkezi":
    st.title("💰 Finansal Yönetim Paneli")
    
    # 5 Sekmeli Yapı
    tabs = st.tabs(["📊 Genel Bakış", "💸 Harcama", "💳 Ödeme", "🤝 Borç/Alacak", "📈 Yatırım"])

    # --- TAB 1: GENEL BAKIŞ ---
    with tabs[0]:
        st.header("Finansal Özet")
        df_exp = get_data("expenses")
        df_pay = get_data("payments")
        df_inv = get_data("investments")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader("Harcamalar")
            if not df_exp.empty:
                d, w, m = calculate_totals(df_exp)
                st.metric("Bu Ay", f"{m:,.2f} TL", f"Bugün: {d:,.2f}")
            else: st.write("-")
            
        with c2:
            st.subheader("Yatırımlar")
            if not df_inv.empty:
                total_inv = df_inv['amount'].sum()
                st.metric("Toplam Yatırım (Giriş)", f"{total_inv:,.2f} TL")
            else: st.write("-")

        with c3:
            st.subheader("Ödemeler")
            if not df_pay.empty:
                _, _, m_pay = calculate_totals(df_pay)
                st.metric("Bu Ay Ödenen", f"{m_pay:,.2f} TL")
            else: st.write("-")
        
        st.divider()
        if not df_exp.empty:
            st.subheader("Harcama Pastası")
            cat_sum = df_exp.groupby("category")["amount"].sum()
            fig, ax = plt.subplots(figsize=(4,4))
            ax.pie(cat_sum, labels=cat_sum.index, autopct='%1.1f%%', startangle=90)
            st.pyplot(fig)

    # --- TAB 2: HARCAMA ---
    with tabs[1]:
        st.header("Yeni Harcama")
        with st.form("expense_form"):
            col1, col2, col3 = st.columns(3)
            date_in = col1.date_input("Tarih", datetime.date.today())
            place_in = col2.text_input("Yer")
            amount_in = col3.number_input("Tutar (TL)", min_value=0.0, step=10.0)
            
            col4, col5, col6 = st.columns(3)
            cat_in = col4.selectbox("Tür", ["Market", "Yiyecek", "Ulaşım", "Eğlence", "Diğer"])
            method_in = col5.selectbox("Şekil", ["Kredi Kartı", "Nakit", "Banka Kartı"])
            nec_in = col6.selectbox("Gerekli mi?", ["Evet", "Hayır"])
            
            desc_in = st.text_area("Açıklama")
            if st.form_submit_button("Kaydet"):
                save_to_db("expenses", {
                    "date": datetime.datetime.combine(date_in, datetime.time.min),
                    "place": place_in, "amount": amount_in, "category": cat_in,
                    "method": method_in, "necessity": nec_in, "desc": desc_in
                })
        
        st.divider()
        st.subheader("Son Harcamalar")
        df_exp_view = get_data("expenses")
        if not df_exp_view.empty:
            st.dataframe(df_exp_view[['date_str', 'place', 'amount', 'category', 'necessity']], use_container_width=True)

    # --- TAB 3: ÖDEME ---
    with tabs[2]:
        st.header("Ödeme / Borç Kapatma")
        with st.form("pay_form"):
            c1, c2 = st.columns(2)
            p_date = c1.date_input("Tarih")
            p_amount = c2.number_input("Tutar", min_value=0.0)
            p_type = st.selectbox("Ödeme Türü", ["Kredi Kartı Borcu", "Fatura", "Kredi", "Diğer"])
            p_desc = st.text_area("Açıklama")
            if st.form_submit_button("Ödemeyi Kaydet"):
                save_to_db("payments", {
                    "date": datetime.datetime.combine(p_date, datetime.time.min),
                    "amount": p_amount, "category": p_type, "desc": p_desc
                })
        
        st.divider()
        st.subheader("Son Ödemeler")
        df_pay_view = get_data("payments")
        if not df_pay_view.empty:
            st.dataframe(df_pay_view[['date_str', 'category', 'amount', 'desc']], use_container_width=True)

    # --- TAB 4: BORÇ / ALACAK TAKİBİ (YENİ) ---
    with tabs[3]:
        st.header("🤝 Borç Defteri")
        
        debt_type = st.radio("İşlem Yönü", ["🟢 Borç Verdim (Alacaklıyım)", "🔴 Borç Aldım (Borçluyum)"], horizontal=True)
        
        with st.form("debt_form"):
            d1, d2, d3 = st.columns(3)
            person = d1.text_input("Kişi / Kurum Adı")
            amount = d2.number_input("Miktar", min_value=0.0)
            currency = d3.selectbox("Para Birimi / Tür", ["TL", "USD", "EUR", "Çeyrek Altın", "Gram Altın", "Diğer"])
            
            d4, d5 = st.columns(2)
            date_given = d4.date_input("Verilme/Alınma Tarihi", datetime.date.today())
            date_due = d5.date_input("Geri Ödeme Tarihi (Vade)")
            
            notes = st.text_area("Notlar")
            
            if st.form_submit_button("Kaydı Oluştur"):
                save_to_db("debts", {
                    "type": "Alacak" if "Alacak" in debt_type else "Borç",
                    "person": person, "amount": amount, "currency": currency,
                    "date": datetime.datetime.combine(date_given, datetime.time.min),
                    "due_date": datetime.datetime.combine(date_due, datetime.time.min),
                    "status": "Aktif", "notes": notes
                })

        st.divider()
        st.subheader("Borç/Alacak Durumu")
        df_debt = get_data("debts")
        if not df_debt.empty:
            # Sadece aktifleri gösterelim veya filtre ekleyelim
            st.dataframe(df_debt[['type', 'person', 'amount', 'currency', 'due_date_str', 'status']], use_container_width=True)
        else:
            st.info("Kayıtlı borç/alacak bulunamadı.")

    # --- TAB 5: YATIRIM TAKİBİ (YENİ) ---
    with tabs[4]:
        st.header("📈 Yatırım Portföyü")
        
        with st.form("invest_form"):
            i1, i2, i3 = st.columns(3)
            inv_date = i1.date_input("Yatırım Tarihi")
            inv_cat = i2.selectbox("Yatırım Aracı", ["Altın", "Döviz", "Borsa (Hisse)", "Fon", "Kripto", "Diğer"])
            inv_name = i3.text_input("Varlık Adı (Örn: Gram Altın, ASELS)", value="Gram Altın")
            
            i4, i5 = st.columns(2)
            inv_qty = i4.number_input("Adet / Miktar", min_value=0.0, format="%.4f")
            inv_total = i5.number_input("Toplam Yatırılan Tutar (TL)", min_value=0.0)
            
            if st.form_submit_button("Yatırımı Ekle"):
                save_to_db("investments", {
                    "date": datetime.datetime.combine(inv_date, datetime.time.min),
                    "category": inv_cat, "asset_name": inv_name,
                    "quantity": inv_qty, "amount": inv_total,
                    "status": "Tutuluyor"
                })

        st.divider()
        st.subheader("Portföyüm")
        df_inv = get_data("investments")
        if not df_inv.empty:
            st.dataframe(df_inv[['date_str', 'category', 'asset_name', 'quantity', 'amount']], use_container_width=True)
            
            # Toplam Yatırım Özeti
            total_tl = df_inv['amount'].sum()
            st.success(f"💰 Toplam Yatırılan Ana Para: {total_tl:,.2f} TL")
        else:
            st.info("Henüz yatırım kaydı yok.")
