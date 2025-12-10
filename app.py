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
    # Tarih objesini string'e çeviriyoruz ki sorgulaması kolay olsun
    if "date" in data and isinstance(data["date"], datetime.date):
        data["date_str"] = data["date"].strftime("%Y-%m-%d")
    
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

# --- 3. FİNANSAL HESAPLAMA FONKSİYONLARI ---
def calculate_totals(df):
    if df.empty:
        return 0, 0, 0
    
    df['date_dt'] = pd.to_datetime(df['date_str'])
    today = pd.Timestamp.now().normalize()
    start_week = today - pd.Timedelta(days=today.dayofweek) # Pazartesi
    start_month = today.replace(day=1)
    
    # Filtrelemeler
    daily_sum = df[df['date_dt'] == today]['amount'].sum()
    weekly_sum = df[df['date_dt'] >= start_week]['amount'].sum()
    monthly_sum = df[df['date_dt'] >= start_month]['amount'].sum()
    
    return daily_sum, weekly_sum, monthly_sum

# --- 4. ARAYÜZ VE NAVİGASYON ---
st.sidebar.title("🚀 Life OS")
main_module = st.sidebar.selectbox(
    "Modül Seç", 
    ["Dil Asistanı", "Fiziksel Takip", "Finans Merkezi"]
)

# ==========================================
# MODÜL 1: DİL ASİSTANI (Aynı Kalıyor)
# ==========================================
if main_module == "Dil Asistanı":
    # ... (Eski kodlarının aynısı buraya gelecek) ...
    st.title("🇩🇪 🇬🇧 Dil Asistanı")
    st.info("Bu modül önceki versiyonla aynıdır.")
    # (Kod kalabalığı olmasın diye burayı kısalttım, senin eski kodunu buraya yapıştırabilirsin)

# ==========================================
# MODÜL 2: FİZİKSEL TAKİP (Aynı Kalıyor)
# ==========================================
elif main_module == "Fiziksel Takip":
    # ... (Eski kodlarının aynısı buraya gelecek) ...
    st.title("💪 Fiziksel Takip")
    st.info("Bu modül önceki versiyonla aynıdır.")

# ==========================================
# MODÜL 3: FİNANS MERKEZİ (YENİLENMİŞ)
# ==========================================
elif main_module == "Finans Merkezi":
    st.title("💰 Finansal Yönetim Paneli")
    
    # Sekmeler
    tab_overview, tab_expense, tab_payment = st.tabs(["📊 Genel Bakış", "💸 Harcama Ekle", "💳 Ödeme Ekle"])

    # --- TAB 1: GENEL BAKIŞ VE RAPORLAR ---
    with tab_overview:
        st.header("Finansal Durum")
        
        # Verileri Çek
        df_exp = get_data("expenses")
        df_pay = get_data("payments")
        
        col1, col2 = st.columns(2)
        
        # Harcama Özetleri
        with col1:
            st.subheader("Harcamalar (Gider)")
            if not df_exp.empty:
                d_exp, w_exp, m_exp = calculate_totals(df_exp)
                st.metric("Bugün", f"{d_exp:,.2f} TL")
                st.metric("Bu Hafta", f"{w_exp:,.2f} TL")
                st.metric("Bu Ay", f"{m_exp:,.2f} TL")
            else:
                st.info("Henüz harcama verisi yok.")

        # Ödeme Özetleri
        with col2:
            st.subheader("Ödemeler (Borç/Fatura)")
            if not df_pay.empty:
                d_pay, w_pay, m_pay = calculate_totals(df_pay)
                st.metric("Bugün", f"{d_pay:,.2f} TL")
                st.metric("Bu Hafta", f"{w_pay:,.2f} TL")
                st.metric("Bu Ay", f"{m_pay:,.2f} TL")
            else:
                st.info("Henüz ödeme verisi yok.")

        st.divider()
        
        # Grafiksel Analiz
        if not df_exp.empty:
            st.subheader("Harcama Dağılımı (Kategorilere Göre)")
            
            # Kategori bazlı toplam
            cat_sum = df_exp.groupby("category")["amount"].sum().reset_index()
            
            c_chart1, c_chart2 = st.columns(2)
            
            with c_chart1:
                # Pasta Grafiği
                fig1, ax1 = plt.subplots()
                ax1.pie(cat_sum['amount'], labels=cat_sum['category'], autopct='%1.1f%%', startangle=90)
                ax1.axis('equal') 
                st.pyplot(fig1)
            
            with c_chart2:
                # Gereklilik Analizi
                nec_sum = df_exp.groupby("necessity")["amount"].sum()
                st.write("Fuzuli vs Gerekli Harcama Analizi:")
                st.bar_chart(nec_sum)

            # Detaylı Tablo
            st.subheader("Son Harcamalar")
            st.dataframe(df_exp[['date_str', 'place', 'amount', 'category', 'necessity', 'desc']], use_container_width=True)

    # --- TAB 2: HARCAMA GİRİŞİ (Senin Excel Formatına Göre) ---
    with tab_expense:
        st.header("Yeni Harcama Kaydı")
        with st.form("expense_form"):
            col1, col2, col3 = st.columns(3)
            
            date_in = col1.date_input("Tarih", datetime.date.today())
            place_in = col2.text_input("Yer (Mağaza/Kurum)")
            amount_in = col3.number_input("Tutar (TL)", min_value=0.0, step=10.0, format="%.2f")
            
            col4, col5, col6 = st.columns(3)
            cat_in = col4.selectbox("Tür", ["Market", "Yiyecek", "İçecek", "Kuruyemiş", "Eğlence", "Bakım", "Yatırım", "Diğer"])
            method_in = col5.selectbox("Şekil", ["Banka Kartı", "Kredi Kartı", "Nakit"])
            card_name = col6.text_input("Kart İsmi (Varsa)", placeholder="DenizBank, Garanti vb.")
            
            col7, col8 = st.columns(2)
            installments = col7.number_input("Taksit Sayısı", min_value=1, value=1)
            necessity = col8.selectbox("Gerekli mi?", ["Evet", "Hayır"])
            
            desc_in = st.text_area("Açıklama / Ürün Detayı")
            
            submitted_exp = st.form_submit_button("Harcamayı Kaydet")
            
            if submitted_exp:
                expense_data = {
                    "date": datetime.datetime.combine(date_in, datetime.time.min),
                    "place": place_in,
                    "amount": amount_in,
                    "category": cat_in,
                    "method": method_in,
                    "card_name": card_name,
                    "installments": installments,
                    "necessity": necessity,
                    "desc": desc_in,
                    "status": "Completed"
                }
                save_to_db("expenses", expense_data)

    # --- TAB 3: ÖDEME GİRİŞİ (Senin Excel Formatına Göre) ---
    with tab_payment:
        st.header("Ödeme / Borç / Fatura Kaydı")
        with st.form("payment_form"):
            p_col1, p_col2, p_col3 = st.columns(3)
            
            p_date = p_col1.date_input("Tarih", datetime.date.today())
            p_place = p_col2.text_input("Yer / Kanal (İnternet Bankacılığı vb.)")
            p_amount = p_col3.number_input("Tutar (TL)", min_value=0.0, step=10.0, format="%.2f")
            
            p_col4, p_col5, p_col6 = st.columns(3)
            p_type = p_col4.selectbox("Türü", ["Kredi Kartı Borcu", "Kredi Ödemesi", "Fatura", "KYK Borcu", "Apple/Abonelik", "Diğer"])
            p_method = p_col5.selectbox("Şekil", ["Havale/EFT", "Otomatik Ödeme", "Nakit"])
            p_account = p_col6.text_input("Hangi Hesaptan?", value="Deniz Maaş")
            
            p_desc = st.text_area("Açıklama (Örn: Garanti Bonus Borcu)")
            
            submitted_pay = st.form_submit_button("Ödemeyi Kaydet")
            
            if submitted_pay:
                payment_data = {
                    "date": datetime.datetime.combine(p_date, datetime.time.min),
                    "place": p_place,
                    "amount": p_amount,
                    "category": p_type, # Kod içinde category olarak tutalım, analiz kolaylığı için
                    "method": p_method,
                    "account_name": p_account,
                    "desc": p_desc,
                    "status": "Completed"
                }
                save_to_db("payments", payment_data)
        
        # Son Ödemeler Listesi
        st.divider()
        st.subheader("Son Yapılan Ödemeler")
        df_pay_view = get_data("payments")
        if not df_pay_view.empty:
             st.dataframe(df_pay_view[['date_str', 'category', 'amount', 'place', 'account_name']], use_container_width=True)
