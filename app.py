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
    },
     "ABD Borsaları (Dolar)": {
        "AAPL": "Apple", "MSFT": "Microsoft", "TSLA": "Tesla", 
        "NVDA": "NVIDIA", "AMZN": "Amazon", "GOOG": "Google"
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
        
def delete_from_db(collection_name, doc_id):
    """Verilen ID'ye sahip dökümanı siler (Tekli)"""
    try:
        db.collection(collection_name).document(doc_id).delete()
        st.toast("🗑️ Kayıt Silindi!")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Silme hatası: {e}")

def speak(text, lang='en'):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp, format='audio/mp3')
    except: pass

def calculate_totals(df_in):
    """Günlük, Haftalık, Aylık toplam hesaplar - Güvenli Versiyon"""
    if df_in.empty: return 0, 0, 0
    if 'date_str' not in df_in.columns: return 0, 0, 0
    
    # Orijinal veriyi bozmamak için kopya alıyoruz
    df = df_in.copy()
    
    try:
        df['date_dt'] = pd.to_datetime(df['date_str'], errors='coerce')
        today = pd.Timestamp.now().normalize()
        start_week = today - pd.Timedelta(days=today.dayofweek)
        start_month = today.replace(day=1)
        
        # 'amount' sütununu sayıya çevir
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        
        d_sum = df[df['date_dt'] == today]['amount'].sum()
        w_sum = df[df['date_dt'] >= start_week]['amount'].sum()
        m_sum = df[df['date_dt'] >= start_month]['amount'].sum()
        return d_sum, w_sum, m_sum
    except:
        return 0, 0, 0

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

# ==========================================
# MODÜL 1: DİL ASİSTANI
# ==========================================
if main_module == "Dil Asistanı":
    st.title("🇩🇪 🇬🇧 Dil Asistanı")
    lang_menu = st.sidebar.radio("İşlemler", ["Kelime Ekle", "Excel'den Yükle", "Kelime Listesi", "Günlük Test"])
    
    if lang_menu == "Kelime Ekle":
        st.subheader("Manuel Ekleme")
        # Form kullanımı
        with st.form("word_add_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            en = c1.text_input("🇬🇧 İngilizce")
            de = c2.text_input("🇩🇪 Almanca")
            tr = c3.text_input("🇹🇷 Türkçe")
            sent = st.text_area("Örnek Cümle")
            if st.form_submit_button("Kaydet"):
                save_to_db("vocabulary", {"en": en, "de": de, "tr": tr, "sentence_source": sent, "learned_count": 0})
                st.rerun()

    elif lang_menu == "Excel'den Yükle":
        st.subheader("Toplu Yükleme")
        lang_type = st.radio("Dil Seçimi", ["🇬🇧 İngilizce", "🇩🇪 Almanca"])
        up_file = st.file_uploader("Excel Dosyası", type=["xlsx", "xls"])
        
        if up_file and st.button("Yüklemeyi Başlat"):
            try:
                df = pd.read_excel(up_file)
                df.columns = df.columns.str.strip()
                count = 0
                progress_bar = st.progress(0)
                for idx, row in df.iterrows():
                    word_data = {}
                    phrase_col = next((c for c in df.columns if "harase" in c.lower() or "hrase" in c.lower()), None)
                    word_data["sentence_source"] = str(row[phrase_col]) if phrase_col and pd.notna(row[phrase_col]) else ""

                    if "İngilizce" in lang_type:
                        word_data["en"] = str(row.get("Word", ""))
                        m1 = str(row.get("Meaning 1", ""))
                        m2 = str(row.get("Meaning 2", ""))
                        word_data["tr"] = f"{m1}, {m2}".strip(", ") if pd.notna(row.get("Meaning 2")) else m1
                        word_data["de"] = ""
                    else:
                        word_data["de"] = str(row.get("Word", ""))
                        tr_col = next((c for c in df.columns if "turkish" in c.lower()), None)
                        m1 = str(row.get("Meaning 1", ""))
                        tr_val = str(row[tr_col]) if tr_col else m1
                        word_data["tr"] = tr_val
                        word_data["en"] = ""

                    if word_data["tr"] and (word_data["en"] or word_data["de"]):
                        word_data["learned_count"] = 0
                        save_to_db("vocabulary", word_data)
                        count += 1
                    progress_bar.progress((idx + 1) / len(df))
                st.success(f"{count} kelime eklendi!")
                time.sleep(1)
                st.rerun()
            except Exception as e: st.error(f"Hata: {e}")

    elif lang_menu == "Kelime Listesi":
        df = get_data("vocabulary")
        if not df.empty:
            search = st.text_input("Kelime Ara")
            if search:
                df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
            
            st.markdown("### Kelimeler")
            for index, row in df.iterrows():
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 2, 4, 1])
                    col1.write(f"🇬🇧 {row.get('en', '-')}")
                    col2.write(f"🇩🇪 {row.get('de', '-')}")
                    col3.write(f"🇹🇷 {row.get('tr', '-')}")
                    if col4.button("Sil", key=f"del_voc_{row['id']}"):
                        delete_from_db("vocabulary", row['id'])
                    st.divider()

    elif lang_menu == "Günlük Test":
        st.subheader("🧠 Quiz")
        if 'quiz_started' not in st.session_state:
            st.session_state.update({'quiz_started': False, 'score': 0, 'idx': 0, 'data': []})

        def new_quiz():
            df = get_data("vocabulary")
            if len(df) < 5: 
                st.warning("Yeterli kelime yok.")
                return
            st.session_state['data'] = df.sample(min(15, len(df))).to_dict('records')
            st.session_state.update({'quiz_started': True, 'score': 0, 'idx': 0, 'show': False})

        if not st.session_state['quiz_started']:
            if st.button("Testi Başlat"): new_quiz()
        else:
            q_data = st.session_state['data']
            idx = st.session_state['idx']
            if idx < len(q_data):
                q = q_data[idx]
                st.progress((idx)/len(q_data))
                st.markdown(f"### ❓ {q.get('en') or q.get('de')}")
                if st.session_state.get('show'):
                    st.success(f"**{q['tr']}**")
                    st.info(q.get('sentence_source'))
                    c1, c2 = st.columns(2)
                    if c1.button("✅ Bildim"):
                        st.session_state['score'] += 1
                        st.session_state['idx'] += 1
                        st.session_state['show'] = False
                        st.rerun()
                    if c2.button("❌ Bilemedim"):
                        st.session_state['idx'] += 1
                        st.session_state['show'] = False
                        st.rerun()
                elif st.button("Göster"):
                    st.session_state['show'] = True
                    st.rerun()
            else:
                st.balloons()
                st.success(f"Skor: {st.session_state['score']}")
                if st.button("Tekrar"): new_quiz()

# ==========================================
# MODÜL 2: FİZİKSEL TAKİP
# ==========================================
elif main_module == "Fiziksel Takip":
    st.title("💪 Fiziksel Gelişim")
    phys_menu = st.sidebar.radio("Alt Menü", ["İdman Takibi", "Ölçü Takibi", "Öğün Takibi"])

    if phys_menu == "İdman Takibi":
        st.subheader("🏋️‍♂️ İdman Kaydı")
        # Form kullanımı
        with st.form("workout_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            w_type = c1.selectbox("Tür", ["Fitness", "Kardiyo", "Yüzme", "Yoga"])
            dur = c2.number_input("Süre (dk)", 10, 300, 60)
            note = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"):
                save_to_db("workouts", {"type": w_type, "duration": dur, "notes": note, "date": datetime.date.today()})
                st.rerun()
        
        st.divider()
        df = get_data("workouts")
        if not df.empty:
            st.write("Geçmiş İdmanlar")
            for idx, row in df.iterrows():
                cl1, cl2, cl3, cl4 = st.columns([2, 2, 4, 1])
                cl1.write(f"📅 {row.get('date_str', '-')}")
                cl2.write(f"🏃 {row['type']} ({row['duration']} dk)")
                cl3.write(f"📝 {row['notes']}")
                if cl4.button("Sil", key=f"del_wrk_{row['id']}"):
                    delete_from_db("workouts", row['id'])

    elif phys_menu == "Ölçü Takibi":
        st.subheader("📏 Vücut Analizi")
        with st.form("body_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            w = c1.number_input("Kilo", format="%.1f")
            f = c2.number_input("Yağ %", format="%.1f")
            m = c3.number_input("Kas %", format="%.1f")
            if st.form_submit_button("Kaydet"):
                save_to_db("measurements", {"weight": w, "fat": f, "muscle": m, "date": datetime.date.today()})
                st.rerun()
        st.divider()
        df = get_data("measurements")
        if not df.empty:
            # Grafik için veri temizliği
            df['date'] = pd.to_datetime(df['date_str'], errors='coerce')
            df['weight'] = pd.to_numeric(df['weight'], errors='coerce')
            df = df.dropna(subset=['date', 'weight']).sort_values('date')
            
            st.line_chart(df, x='date', y='weight')
            
            with st.expander("Kayıtları Düzenle"):
                for idx, row in df.iterrows():
                    c1, c2, c3 = st.columns([2, 2, 1])
                    c1.write(f"{row['date_str']}")
                    c2.write(f"{row['weight']} kg")
                    if c3.button("Sil", key=f"del_meas_{row['id']}"):
                        delete_from_db("measurements", row['id'])

    elif phys_menu == "Öğün Takibi":
        st.subheader("🥗 Beslenme")
        with st.form("meal_form", clear_on_submit=True):
            c1, c2 = st.columns([1,2])
            cal = c1.number_input("Kalori", 0, 2000)
            meal = c2.text_input("İçerik")
            if st.form_submit_button("Ekle"):
                save_to_db("meals", {"calories": cal, "content": meal, "date": datetime.date.today()})
                st.rerun()
        
        st.divider()
        df = get_data("meals")
        if not df.empty:
            df['calories'] = pd.to_numeric(df['calories'], errors='coerce').fillna(0)
            tod = str(datetime.date.today())
            total = df[df['date_str'] == tod]['calories'].sum()
            st.metric("Bugün Alınan", f"{total} kcal")
            
            for idx, row in df.iterrows():
                c1, c2, c3, c4 = st.columns([2, 2, 4, 1])
                c1.write(row.get('date_str', '-'))
                c2.write(f"{row['calories']} kcal")
                c3.write(row['content'])
                if c4.button("Sil", key=f"del_meal_{row['id']}"):
                    delete_from_db("meals", row['id'])

# ==========================================
# MODÜL 3: FİNANS MERKEZİ
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
                inv_total = pd.to_numeric(df_inv['amount'], errors='coerce').sum()
                st.metric("Toplam Yatırım", f"{inv_total:,.2f} TL")
        
        st.divider()
        if not df_exp.empty:
            df_exp['amount'] = pd.to_numeric(df_exp['amount'], errors='coerce').fillna(0)
            cat_sum = df_exp.groupby("category")["amount"].sum()
            fig, ax = plt.subplots(figsize=(4, 4))
            ax.pie(cat_sum, labels=cat_sum.index, autopct='%1.1f%%', startangle=90)
            st.pyplot(fig)

    # --- TAB 2: HARCAMA ---
    with tabs[1]:
        st.header("Harcama Yönetimi")
        
        # Giriş Formu
        with st.form("expense_input_form", clear_on_submit=True):
            st.subheader("Yeni Harcama")
            c1, c2, c3 = st.columns(3)
            date_in = c1.date_input("Tarih", datetime.date.today())
            place_in = c2.text_input("Yer")
            amount_in = c3.number_input("Tutar (TL)", min_value=0.0, step=10.0)
            
            c4, c5, c6 = st.columns(3)
            # Harcama Türleri Güncellendi
            cat_in = c4.selectbox("Tür", ["Market", "Yiyecek", "İçecek", "Ulaşım", "Eğlence", "Kasap", "Supplement", "Yatırım", "Diğer"])
            method_in = c5.selectbox("Şekil", ["Kredi Kartı", "Nakit", "Banka Kartı"])
            nec_in = c6.selectbox("Gerekli mi?", ["Evet", "Hayır"])
            desc_in = st.text_area("Açıklama")
            
            if st.form_submit_button("Harcamayı Kaydet"):
                save_to_db("expenses", {
                    "date": datetime.datetime.combine(date_in, datetime.time.min),
                    "place": place_in, "amount": amount_in, "category": cat_in,
                    "method": method_in, "necessity": nec_in, "desc": desc_in
                })
                st.rerun()

        st.divider()
        st.subheader("Harcama Kayıtları")
        
        if not df_exp.empty:
            # 1. Gerekli sütunları belirle
            cols = ['Sil', 'date_str', 'place', 'amount', 'category', 'method', 'necessity', 'desc', 'id']
            for col in cols:
                if col not in df_exp.columns and col != 'Sil': df_exp[col] = None
            
            # 2. Tipleri Zorla
            clean_df = df_exp[cols].copy()
            clean_df['Sil'] = clean_df['Sil'].astype(bool)
            clean_df['date_str'] = pd.to_datetime(clean_df['date_str'], errors='coerce').dt.date
            clean_df['place'] = clean_df['place'].astype(str)
            clean_df['amount'] = pd.to_numeric(clean_df['amount'], errors='coerce').fillna(0.0)
            clean_df['category'] = clean_df['category'].astype(str)
            clean_df['method'] = clean_df['method'].astype(str)
            clean_df['necessity'] = clean_df['necessity'].astype(str)
            clean_df['desc'] = clean_df['desc'].astype(str)
            
            # 3. Data Editor
            edited_df = st.data_editor(
                clean_df,
                column_config={
                    "Sil": st.column_config.CheckboxColumn(default=False, width="small"),
                    "date_str": st.column_config.DateColumn("Tarih", format="YYYY-MM-DD"),
                    "place": "Yer",
                    "amount": st.column_config.NumberColumn("Tutar", format="%.2f TL"),
                    "category": st.column_config.SelectboxColumn("Kategori", options=["Market", "Yiyecek", "İçecek", "Ulaşım", "Eğlence", "Kasap", "Supplement", "Yatırım", "Diğer"]),
                    "method": "Ödeme Şekli",
                    "necessity": st.column_config.SelectboxColumn("Gerekli?", options=["Evet", "Hayır"]),
                    "desc": "Açıklama",
                    "id": None 
                },
                hide_index=True,
                num_rows="dynamic",
                key="exp_editor"
            )

            # Silme İşlemi
            to_delete = edited_df[edited_df['Sil'] == True]['id'].tolist()
            if to_delete:
                if st.button(f"Seçili {len(to_delete)} Harcamayı Sil", type="primary"):
                    delete_multiple_docs("expenses", to_delete)
            
            # Güncelleme Butonu
            if st.button("Tablodaki Değişiklikleri Kaydet (Harcama)"):
                for index, row in edited_df.iterrows():
                    if row['id']:
                        update_data = {
                            "date": datetime.datetime.combine(row['date_str'], datetime.time.min) if row['date_str'] else None,
                            "date_str": str(row['date_str']),
                            "place": str(row['place']),
                            "amount": float(row['amount']),
                            "category": str(row['category']),
                            "method": str(row['method']),
                            "necessity": str(row['necessity']),
                            "desc": str(row['desc'])
                        }
                        update_data = {k: v for k, v in update_data.items() if v is not None}
                        db.collection("expenses").document(row['id']).update(update_data)
                st.success("Güncellendi!")
                time.sleep(1)
                st.rerun()

    # --- TAB 3: ÖDEME ---
    with tabs[2]:
        st.header("Ödeme Takibi")
        
        with st.form("payment_input_form", clear_on_submit=True):
            st.subheader("Ödeme Ekle")
            c1, c2, c3 = st.columns(3)
            p_date = c1.date_input("Tarih")
            p_amount = c2.number_input("Tutar", min_value=0.0, step=10.0)
            # İsim Değişikliği: Yer / Kurum -> Ödeme Yapılan Kurum
            p_place = c3.text_input("Ödeme Yapılan Kurum")
            
            c4, c5 = st.columns(2)
            # Tür Değişikliği: Kredi Kartı -> Kredi Kartı Borcu
            p_type = c4.selectbox("Tür", ["Kredi Kartı Borcu", "Fatura", "Kredi", "Diğer"])
            # İsim Değişikliği: Hesap -> Ödeme Aracı
            p_acc = c5.text_input("Ödeme Aracı", value="Maaş Kartı")
            p_desc = st.text_area("Açıklama")
            
            if st.form_submit_button("Ödemeyi Kaydet"):
                save_to_db("payments", {
                    "date": datetime.datetime.combine(p_date, datetime.time.min),
                    "amount": p_amount, "category": p_type, 
                    "place": p_place, "account": p_acc, "desc": p_desc
                })
                st.rerun()

        st.divider()
        if not df_pay.empty:
            cols_p = ['Sil', 'date_str', 'category', 'amount', 'place', 'account', 'desc', 'id']
            for col in cols_p:
                 if col not in df_pay.columns and col != 'Sil': df_pay[col] = None
            
            clean_df_p = df_pay[cols_p].copy()
            clean_df_p['Sil'] = clean_df_p['Sil'].astype(bool)
            clean_df_p['date_str'] = pd.to_datetime(clean_df_p['date_str'], errors='coerce').dt.date
            clean_df_p['amount'] = pd.to_numeric(clean_df_p['amount'], errors='coerce').fillna(0.0)
            clean_df_p['category'] = clean_df_p['category'].astype(str)
            clean_df_p['place'] = clean_df_p['place'].astype(str)
            clean_df_p['account'] = clean_df_p['account'].astype(str)
            clean_df_p['desc'] = clean_df_p['desc'].astype(str)

            # Dinamik Satır Ekleme Özelliği Eklendi (num_rows="dynamic")
            edited_df_p = st.data_editor(
                clean_df_p,
                column_config={
                    "Sil": st.column_config.CheckboxColumn(default=False),
                    "date_str": st.column_config.DateColumn("Tarih"),
                    "category": st.column_config.SelectboxColumn("Tür", options=["Kredi Kartı Borcu", "Fatura", "Kredi", "Diğer"]),
                    "place": "Ödeme Yapılan Kurum",
                    "account": "Ödeme Aracı",
                    "amount": st.column_config.NumberColumn("Tutar", format="%.2f TL"),
                    "id": None
                },
                hide_index=True,
                num_rows="dynamic", 
                key="pay_editor"
            )
            
            to_del_p = edited_df_p[edited_df_p['Sil'] == True]['id'].tolist()
            if to_del_p:
                if st.button(f"Seçili {len(to_del_p)} Ödemeyi Sil"):
                    delete_multiple_docs("payments", to_del_p)
            
            if st.button("Tablodaki Değişiklikleri Kaydet (Ödeme)"):
                for index, row in edited_df_p.iterrows():
                    if row['id']:
                        db.collection("payments").document(row['id']).update({
                            "date": datetime.datetime.combine(row['date_str'], datetime.time.min) if row['date_str'] else None,
                            "date_str": str(row['date_str']),
                            "place": str(row['place']), 
                            "amount": float(row['amount']), 
                            "desc": str(row['desc']),
                            "category": str(row['category']),
                            "account": str(row['account'])
                        })
                st.success("Güncellendi!")
                time.sleep(1)
                st.rerun()

    # --- TAB 4: BORÇ / ALACAK ---
    with tabs[3]:
        st.header("Borç Defteri")
        debt_mode = st.radio("Yön", ["Verdim (Alacak)", "Aldım (Borç)"], horizontal=True)
        
        with st.form("debt_input_form", clear_on_submit=True):
            d1, d2, d3 = st.columns(3)
            d_person = d1.text_input("Kişi")
            d_amount = d2.number_input("Miktar", min_value=0.0)
            d_curr = d3.selectbox("Birim", ["TL", "USD", "EUR", "Altın"])
            
            d4, d5 = st.columns(2)
            d_date = d4.date_input("Verilme Tarihi")
            d_due = d5.date_input("Vade Tarihi")
            
            if st.form_submit_button("Borç Kaydet"):
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
                 if col not in df_debt.columns and col != 'Sil': df_debt[col] = None

            clean_df_d = df_debt[cols_d].copy()
            clean_df_d['Sil'] = clean_df_d['Sil'].astype(bool)
            clean_df_d['amount'] = pd.to_numeric(clean_df_d['amount'], errors='coerce').fillna(0.0)
            clean_df_d['type'] = clean_df_d['type'].astype(str)
            clean_df_d['person'] = clean_df_d['person'].astype(str)
            clean_df_d['currency'] = clean_df_d['currency'].astype(str)
            clean_df_d['status'] = clean_df_d['status'].astype(str)
            clean_df_d['date_str'] = pd.to_datetime(clean_df_d['date_str'], errors='coerce').dt.date
            clean_df_d['due_date_str'] = pd.to_datetime(clean_df_d['due_date_str'], errors='coerce').dt.date

            edited_df_d = st.data_editor(
                clean_df_d,
                column_config={
                    "Sil": st.column_config.CheckboxColumn(default=False),
                    "type": st.column_config.SelectboxColumn("Tür", options=["Alacak", "Borç"]),
                    "status": st.column_config.SelectboxColumn("Durum", options=["Aktif", "Ödendi"]),
                    "date_str": st.column_config.DateColumn("Tarih"),
                    "due_date_str": st.column_config.DateColumn("Vade"),
                    "id": None
                },
                hide_index=True,
                key="debt_editor"
            )
            
            to_del_d = edited_df_d[edited_df_d['Sil'] == True]['id'].tolist()
            if to_del_d:
                if st.button(f"Seçili {len(to_del_d)} Borç Kaydını Sil"):
                    delete_multiple_docs("debts", to_del_d)
            
            if st.button("Tablodaki Değişiklikleri Kaydet (Borç)"):
                for index, row in edited_df_d.iterrows():
                    if row['id']:
                        db.collection("debts").document(row['id']).update({
                            "person": str(row['person']), 
                            "amount": float(row['amount']), 
                            "status": str(row['status'])
                        })
                st.success("Güncellendi!")
                time.sleep(1)
                st.rerun()

    # --- TAB 5: YATIRIM ---
    with tabs[4]:
        st.header("📈 Akıllı Portföy")
        
        c_i1, c_i2 = st.columns(2)
        
        # Kategori Seçimi (Anlık tepki verir)
        category_options = list(SYMBOL_MAP.keys()) + ["Diğer / Manuel Arama"]
        inv_cat = c_i1.selectbox("Yatırım Türü", category_options)
        
        with st.form("inv_form", clear_on_submit=True):
            c_f1, c_f2 = st.columns(2)
            inv_d = c_f1.date_input("Tarih", datetime.date.today())
            
            selected_symbol = ""
            manual_name = ""
            
            if inv_cat == "Diğer / Manuel Arama":
                selected_symbol = c_f2.text_input("Sembol Gir (Yahoo Kodu)", help="Örn: IBM").strip()
                manual_name = st.text_input("Varlık Adı", placeholder="Örn: Yabancı Fon")
            else:
                current_map = SYMBOL_MAP.get(inv_cat, {})
                if current_map:
                    asset_options = [f"{k} | {v}" for k, v in current_map.items()]
                    selection = c_f2.selectbox("Varlık Seç", asset_options)
                    if selection:
                        selected_symbol = selection.split(" | ")[0]
                        manual_name = selection.split(" | ")[1]

            c_num1, c_num2 = st.columns(2)
            inv_q = c_num1.number_input("Adet", min_value=0.0, format="%.4f")
            inv_c = c_num2.number_input("Toplam Maliyet (TL)", min_value=0.0)

            if st.form_submit_button("Yatırımı Ekle"):
                if inv_cat != "Diğer / Manuel Arama" and not selected_symbol:
                    st.error("Lütfen bir varlık seçin.")
                else:
                    save_to_db("investments", {
                        "date": datetime.datetime.combine(inv_d, datetime.time.min),
                        "symbol": selected_symbol, 
                        "category": inv_cat, 
                        "asset_name": manual_name,
                        "quantity": inv_q, 
                        "amount": inv_c, 
                        "status": "Aktif"
                    })
                    st.rerun()

        st.divider()
        
        if not df_inv.empty:
            st.subheader("Portföy Analizi")
            table_data = []
            total_val = 0
            total_cost = 0
            
            p_bar = st.progress(0)
            
            for idx, row in df_inv.iterrows():
                p_bar.progress((idx + 1) / len(df_inv))
                
                try:
                    qty = float(row.get('quantity', 0))
                    cost = float(row.get('amount', 0))
                except: qty, cost = 0, 0
                
                cur_p = get_asset_current_price(row.get('symbol')) if row.get('symbol') else 0
                
                cur_val = (cur_p * qty) if cur_p > 0 else cost
                total_val += cur_val
                total_cost += cost
                
                table_data.append({
                    "id": row.get('id'),
                    "Sil": False,
                    "Varlık": str(row.get('asset_name', '-')),
                    "Adet": qty,
                    "Maliyet": cost,
                    "Güncel Değer": cur_val,
                    "Fark": cur_val - cost
                })
            
            p_bar.empty()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Toplam Maliyet", f"{total_cost:,.2f} TL")
            k2.metric("Güncel Değer", f"{total_val:,.2f} TL")
            diff = total_val - total_cost
            k3.metric("Kâr/Zarar", f"{diff:,.2f} TL", delta=f"{diff:,.2f}")
            
            inv_df = pd.DataFrame(table_data)
            edited_inv = st.data_editor(
                inv_df,
                column_config={
                    "Sil": st.column_config.CheckboxColumn(default=False),
                    "Adet": st.column_config.NumberColumn(format="%.4f"),
                    "Maliyet": st.column_config.NumberColumn(format="%.2f TL"),
                    "Güncel Değer": st.column_config.NumberColumn(format="%.2f TL"),
                    "Fark": st.column_config.NumberColumn(format="%.2f TL"),
                    "id": None
                },
                hide_index=True,
                key="inv_editor"
            )
            
            to_del_i = edited_inv[edited_inv['Sil'] == True]['id'].tolist()
            if to_del_i:
                 if st.button(f"Seçili {len(to_del_i)} Yatırımı Sil"):
                    delete_multiple_docs("investments", to_del_i)
