import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from gtts import gTTS
import io
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import yfinance as yf
import time

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

# --- 2. SEMBOL KÜTÜPHANESİ ---
SYMBOL_MAP = {
    "Borsa İstanbul (BIST)": {
        "THYAO.IS": "Türk Hava Yolları", "GARAN.IS": "Garanti BBVA", "ASELS.IS": "Aselsan",
        "EREGL.IS": "Erdemir", "KCHOL.IS": "Koç Holding", "SASA.IS": "SASA Polyester",
        "AKBNK.IS": "Akbank", "YKBNK.IS": "Yapı Kredi", "SISE.IS": "Şişecam",
        "BIMAS.IS": "BİM Mağazaları", "TUPRS.IS": "Tüpraş", "FROTO.IS": "Ford Otosan",
        "ISCTR.IS": "İş Bankası (C)", "PETKM.IS": "Petkim", "HEKTS.IS": "Hektaş"
    },
    "Döviz (TL Karşılığı)": {
        "USDTRY=X": "Dolar / TL", "EURTRY=X": "Euro / TL", "GBPTRY=X": "Sterlin / TL",
        "CHFTRY=X": "İsviçre Frangı / TL", "EURUSD=X": "Euro / Dolar Paritesi"
    },
    "Altın & Emtia": {
        "XAUTRY=X": "Gram Altın (TL)", "GC=F": "Ons Altın (Dolar)",
        "XAGTRY=X": "Gümüş (TL)", "SI=F": "Ons Gümüş (Dolar)", "BZ=F": "Brent Petrol (Dolar)"
    },
    "Kripto Para (TL)": {
        "BTC-TRY": "Bitcoin (TL)", "ETH-TRY": "Ethereum (TL)", "SOL-TRY": "Solana (TL)",
        "AVAX-TRY": "Avalanche (TL)", "XRP-TRY": "Ripple (TL)", "USDT-TRY": "Tether (TL)"
    }
}

# --- 3. YARDIMCI FONKSİYONLAR ---

def save_to_db(collection_name, data):
    """Veriyi kaydeder"""
    data["created_at"] = firestore.SERVER_TIMESTAMP
    if "date" in data and isinstance(data["date"], datetime.date):
        data["date_str"] = data["date"].strftime("%Y-%m-%d")
    if "due_date" in data and isinstance(data["due_date"], datetime.date):
        data["due_date_str"] = data["due_date"].strftime("%Y-%m-%d")
    db.collection(collection_name).add(data)

def delete_multiple_docs(collection_name, doc_ids):
    """Toplu silme işlemi"""
    for doc_id in doc_ids:
        db.collection(collection_name).document(doc_id).delete()
    st.toast(f"🗑️ {len(doc_ids)} kayıt silindi!")
    time.sleep(1)
    st.rerun()

def update_doc_from_editor(collection_name, doc_id, changes):
    """Tablodan gelen değişikliği veritabanına yazar"""
    # Tarih formatı düzeltmesi
    if "date_str" in changes:
        # String tarihi datetime objesine çevirip saklayabiliriz veya string olarak tutabiliriz
        # Burada basitlik adına string tutuyoruz, analizde çeviriyoruz.
        pass
    
    db.collection(collection_name).document(doc_id).update(changes)
    st.toast("✏️ Kayıt Güncellendi!")

def get_data(collection_name):
    """Veriyi çeker ve DataFrame oluşturur"""
    try:
        docs = db.collection(collection_name).order_by("created_at", direction=firestore.Query.DESCENDING).stream()
        items = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            item['Sil'] = False # Checkbox için varsayılan değer
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
    # Tarih sütunu yoksa hata vermemesi için kontrol
    if 'date_str' not in df.columns: return 0, 0, 0
    
    df['date_dt'] = pd.to_datetime(df['date_str'])
    today = pd.Timestamp.now().normalize()
    start_week = today - pd.Timedelta(days=today.dayofweek)
    start_month = today.replace(day=1)
    
    d_sum = df[df['date_dt'] == today]['amount'].sum()
    w_sum = df[df['date_dt'] >= start_week]['amount'].sum()
    m_sum = df[df['date_dt'] >= start_month]['amount'].sum()
    return d_sum, w_sum, m_sum

# Cacheli Fiyat Çekme
@st.cache_data(ttl=600)
def get_asset_current_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1d")
        if not history.empty: return history['Close'].iloc[-1]
        return 0.0
    except: return 0.0

# --- 4. ARAYÜZ ---
st.sidebar.title("🚀 Life OS")
main_module = st.sidebar.selectbox("Modül Seç", ["Dil Asistanı", "Fiziksel Takip", "Finans Merkezi"])

# ... (DİL ASİSTANI VE FİZİKSEL TAKİP MODÜLLERİNİ BURAYA AYNEN YAPIŞTIRABİLİRSİNİZ) ...
# Yer kaplamaması için burayı özet geçiyorum, önceki kodun aynısı kalacak.
if main_module == "Dil Asistanı":
    st.info("Dil Asistanı Modülü Aktif (Kodları önceki versiyondan alınız)")
elif main_module == "Fiziksel Takip":
    st.info("Fiziksel Takip Modülü Aktif (Kodları önceki versiyondan alınız)")

# ==========================================
# MODÜL 3: FİNANS MERKEZİ (GÜNCELLENMİŞ VERSİYON)
# ==========================================
elif main_module == "Finans Merkezi":
    st.title("💰 Finansal Yönetim Paneli")
    
    tabs = st.tabs(["📊 Genel Bakış", "💸 Harcama", "💳 Ödeme", "🤝 Borç/Alacak", "📈 Yatırım"])
    
    # Verileri Çek
    df_exp = get_data("expenses")
    df_pay = get_data("payments")
    df_inv = get_data("investments")
    df_debt = get_data("debts")

    # --- TAB 1: GENEL BAKIŞ ---
    with tabs[0]:
        st.header("Finansal Durum")
        c1, c2, c3 = st.columns(3)
        with c1:
            if not df_exp.empty:
                d, w, m = calculate_totals(df_exp)
                st.metric("Bu Ay Harcama", f"{m:,.2f} TL", f"Bugün: {d:,.2f}")
        with c2:
            if not df_pay.empty:
                _, _, m_pay = calculate_totals(df_pay)
                st.metric("Bu Ay Ödeme", f"{m_pay:,.2f} TL")
        with c3:
            if not df_inv.empty:
                tot = df_inv['amount'].sum()
                st.metric("Toplam Yatırım", f"{tot:,.2f} TL")
        
        st.divider()
        if not df_exp.empty:
            cat_sum = df_exp.groupby("category")["amount"].sum()
            fig, ax = plt.subplots(figsize=(4, 4))
            ax.pie(cat_sum, labels=cat_sum.index, autopct='%1.1f%%', startangle=90)
            st.pyplot(fig)

    # --- TAB 2: HARCAMA ---
    with tabs[1]:
        st.header("Harcama Yönetimi")
        
        # Giriş Alanı (Session State ile Temizleme)
        with st.container(border=True):
            st.subheader("Yeni Harcama")
            c1, c2, c3 = st.columns(3)
            # Key parametreleri ile state yönetimi
            date_in = c1.date_input("Tarih", datetime.date.today(), key="e_date")
            place_in = c2.text_input("Yer", key="e_place")
            amount_in = c3.number_input("Tutar (TL)", min_value=0.0, step=10.0, key="e_amount")
            
            c4, c5, c6 = st.columns(3)
            cat_in = c4.selectbox("Tür", ["Market", "Yiyecek", "İçecek", "Ulaşım", "Eğlence", "Diğer"], key="e_cat")
            method_in = c5.selectbox("Şekil", ["Kredi Kartı", "Nakit", "Banka Kartı"], key="e_method")
            nec_in = c6.selectbox("Gerekli mi?", ["Evet", "Hayır"], key="e_nec")
            desc_in = st.text_area("Açıklama", key="e_desc")
            
            if st.button("Harcamayı Kaydet", type="primary"):
                save_to_db("expenses", {
                    "date": datetime.datetime.combine(date_in, datetime.time.min),
                    "place": place_in, "amount": amount_in, "category": cat_in,
                    "method": method_in, "necessity": nec_in, "desc": desc_in
                })
                # State'i temizle ve yenile
                st.rerun()

        st.divider()
        st.subheader("Harcama Kayıtları (Düzenle & Sil)")
        
        if not df_exp.empty:
            # Gerekli Sütunları Seç ve Sırala
            display_cols = ['Sil', 'date_str', 'place', 'amount', 'category', 'method', 'necessity', 'desc', 'id']
            # Sütun yoksa oluştur (Dataframe yapısını korumak için)
            for col in display_cols:
                if col not in df_exp.columns and col != 'Sil': df_exp[col] = ""
            
            # Data Editor Konfigürasyonu
            edited_df = st.data_editor(
                df_exp[display_cols],
                column_config={
                    "Sil": st.column_config.CheckboxColumn(help="Silmek için seç", default=False),
                    "date_str": st.column_config.DateColumn("Tarih", format="YYYY-MM-DD"),
                    "place": "Yer",
                    "amount": st.column_config.NumberColumn("Tutar", format="%.2f TL"),
                    "category": st.column_config.SelectboxColumn("Kategori", options=["Market", "Yiyecek", "İçecek", "Ulaşım", "Eğlence", "Diğer"]),
                    "method": "Ödeme Şekli",
                    "necessity": st.column_config.SelectboxColumn("Gerekli?", options=["Evet", "Hayır"]),
                    "desc": "Açıklama",
                    "id": None # ID sütununu gizle
                },
                hide_index=True,
                num_rows="dynamic", # Yeni satır eklemeye izin verir
                key="exp_editor"
            )

            # Silme Butonu
            to_delete = edited_df[edited_df['Sil'] == True]['id'].tolist()
            if to_delete:
                if st.button(f"Seçili {len(to_delete)} Kaydı Sil", type="primary"):
                    delete_multiple_docs("expenses", to_delete)

            # Düzenleme Tespiti (Session State üzerinden farkları bulabiliriz)
            # Streamlit data_editor otomatik olarak veriyi görselleştirir, 
            # ancak DB güncellemesi için değişiklikleri yakalamamız lazım.
            # Basit Yöntem: Data Editor 'on_change' desteklemez, ama rerun olduğunda 'edited_rows' session state'de olur.
            # Daha gelişmiş bir yapı için kullanıcı düzenleyip 'Enter'a bastığında update fonksiyonunu tetiklemek gerekir.
            # Şu anlık 'Silme' ve 'Ekleme' sorunsuz. Hücre düzenlemeyi kaydetmek için:
            
            # Not: Streamlit data_editor anlık DB update için biraz kompleks bir logic gerektirir.
            # Kullanıcıya "Değişiklikleri Kaydet" butonu sunmak en güvenlisidir.
            # Ancak biz "Görünürde düzenle" mantığıyla ilerledik. 
            # Gerçek zamanlı update için aşağıdaki gibi bir mekanizma kullanılabilir:
            
            # Bu örnekte karmaşıklığı artırmamak için; Data Editor görsel olarak düzenlemeye izin verir.
            # Ancak veritabanına geri yazmak için manuel bir buton koyalım veya
            # her değişiklikte tüm tabloyu tarayıp farkları bulmak performanslı olmaz.
            # Kullanıcı deneyimi için en temizi:
            
            if st.button("Tablodaki Değişiklikleri Kaydet"):
                # edited_df ile df_exp arasındaki farkları bulup update etme mantığı
                # Basitçe ID üzerinden döngü kurarak update edebiliriz
                for index, row in edited_df.iterrows():
                    # Orijinal veriyi bul (Hafızadan)
                    if row['id']: # Yeni eklenen boş satırlar hariç
                        update_data = {
                            "date_str": str(row['date_str']) if row['date_str'] else "",
                            "place": row['place'],
                            "amount": row['amount'],
                            "category": row['category'],
                            "method": row['method'],
                            "necessity": row['necessity'],
                            "desc": row['desc']
                        }
                        db.collection("expenses").document(row['id']).update(update_data)
                st.success("Tablo güncellendi!")
                time.sleep(1)
                st.rerun()

    # --- TAB 3: ÖDEME ---
    with tabs[2]:
        st.header("Ödeme Takibi")
        
        with st.container(border=True):
            st.subheader("Ödeme Ekle")
            c1, c2, c3 = st.columns(3)
            p_date = c1.date_input("Tarih", key="p_date")
            p_amount = c2.number_input("Tutar", min_value=0.0, step=10.0, key="p_amt")
            p_place = c3.text_input("Yer / Kurum", key="p_place")
            
            c4, c5 = st.columns(2)
            p_type = c4.selectbox("Tür", ["Kredi Kartı", "Fatura", "Kredi", "Diğer"], key="p_type")
            p_acc = c5.text_input("Hesap", value="Maaş Kartı", key="p_acc")
            p_desc = st.text_area("Açıklama", key="p_desc")
            
            if st.button("Ödemeyi Kaydet", type="primary"):
                save_to_db("payments", {
                    "date": datetime.datetime.combine(p_date, datetime.time.min),
                    "amount": p_amount, "category": p_type, 
                    "place": p_place, "account": p_acc, "desc": p_desc
                })
                st.rerun()

        st.divider()
        if not df_pay.empty:
            display_cols_p = ['Sil', 'date_str', 'category', 'amount', 'place', 'account', 'desc', 'id']
            for col in display_cols_p:
                 if col not in df_pay.columns and col != 'Sil': df_pay[col] = ""

            edited_df_p = st.data_editor(
                df_pay[display_cols_p],
                column_config={
                    "Sil": st.column_config.CheckboxColumn(default=False),
                    "date_str": st.column_config.DateColumn("Tarih"),
                    "amount": st.column_config.NumberColumn("Tutar", format="%.2f TL"),
                    "id": None
                },
                hide_index=True,
                key="pay_editor"
            )
            
            to_del_p = edited_df_p[edited_df_p['Sil'] == True]['id'].tolist()
            if to_del_p:
                if st.button(f"Seçili {len(to_del_p)} Ödemeyi Sil"):
                    delete_multiple_docs("payments", to_del_p)
            
            if st.button("Ödeme Tablosunu Güncelle"):
                for index, row in edited_df_p.iterrows():
                    if row['id']:
                        db.collection("payments").document(row['id']).update({
                            "place": row['place'], "amount": row['amount'], "desc": row['desc']
                        })
                st.success("Güncellendi!")
                time.sleep(1)
                st.rerun()

    # --- TAB 4: BORÇ / ALACAK ---
    with tabs[3]:
        st.header("Borç Defteri")
        debt_mode = st.radio("Yön", ["Verdim (Alacak)", "Aldım (Borç)"], horizontal=True)
        
        with st.container(border=True):
            d1, d2, d3 = st.columns(3)
            d_person = d1.text_input("Kişi", key="d_per")
            d_amount = d2.number_input("Miktar", min_value=0.0, key="d_amt")
            d_curr = d3.selectbox("Birim", ["TL", "USD", "EUR", "Altın"], key="d_cur")
            
            d4, d5 = st.columns(2)
            d_date = d4.date_input("Verilme Tarihi", key="d_date")
            d_due = d5.date_input("Vade Tarihi", key="d_due")
            
            if st.button("Borç Kaydet", type="primary"):
                save_to_db("debts", {
                    "type": "Alacak" if "Verdim" in debt_mode else "Borç",
                    "person": d_person, "amount": d_amount, "currency": d_curr,
                    "date": datetime.datetime.combine(d_date, datetime.time.min),
                    "due_date": datetime.datetime.combine(d_due, datetime.time.min),
                    "status": "Aktif"
                })
                st.rerun()

        st.divider()
        if not df_debt.empty:
            cols_d = ['Sil', 'type', 'person', 'amount', 'currency', 'date_str', 'due_date_str', 'status', 'id']
            for col in cols_d:
                 if col not in df_debt.columns and col != 'Sil': df_debt[col] = ""

            edited_df_d = st.data_editor(
                df_debt[cols_d],
                column_config={
                    "Sil": st.column_config.CheckboxColumn(default=False),
                    "type": st.column_config.SelectboxColumn("Tür", options=["Alacak", "Borç"]),
                    "status": st.column_config.SelectboxColumn("Durum", options=["Aktif", "Ödendi"]),
                    "id": None
                },
                hide_index=True,
                key="debt_editor"
            )
            
            to_del_d = edited_df_d[edited_df_d['Sil'] == True]['id'].tolist()
            if to_del_d:
                if st.button(f"Seçili {len(to_del_d)} Borç Kaydını Sil"):
                    delete_multiple_docs("debts", to_del_d)
            
            if st.button("Borç Tablosunu Güncelle"):
                for index, row in edited_df_d.iterrows():
                    if row['id']:
                        db.collection("debts").document(row['id']).update({
                            "person": row['person'], "amount": row['amount'], "status": row['status']
                        })
                st.success("Güncellendi!")
                time.sleep(1)
                st.rerun()

    # --- TAB 5: YATIRIM (AYNI KALDI - GÖRSELLEŞTİRME AMAÇLI) ---
    with tabs[4]:
        st.info("Yatırım Modülü (Önceki kodun aynısı kullanılabilir)")
        # Yatırım kodunu buraya önceki cevaptan ekleyebilirsiniz.
        # Sayfa yapısı bozulmasın diye burayı kısa tutuyorum.
        pass
