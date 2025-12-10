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
        "THYAO.IS": "Türk Hava Yolları",
        "GARAN.IS": "Garanti BBVA",
        "ASELS.IS": "Aselsan",
        "EREGL.IS": "Erdemir",
        "KCHOL.IS": "Koç Holding",
        "SASA.IS": "SASA Polyester",
        "AKBNK.IS": "Akbank",
        "YKBNK.IS": "Yapı Kredi",
        "SISE.IS": "Şişecam",
        "BIMAS.IS": "BİM Mağazaları",
        "TUPRS.IS": "Tüpraş",
        "FROTO.IS": "Ford Otosan",
        "ISCTR.IS": "İş Bankası (C)",
        "PETKM.IS": "Petkim",
        "HEKTS.IS": "Hektaş"
    },
    "Döviz (TL Karşılığı)": {
        "USDTRY=X": "Dolar / TL",
        "EURTRY=X": "Euro / TL",
        "GBPTRY=X": "Sterlin / TL",
        "CHFTRY=X": "İsviçre Frangı / TL",
        "EURUSD=X": "Euro / Dolar Paritesi"
    },
    "Altın & Emtia": {
        "XAUTRY=X": "Gram Altın (TL)",
        "GC=F": "Ons Altın (Dolar)",
        "XAGTRY=X": "Gümüş (TL)",
        "SI=F": "Ons Gümüş (Dolar)",
        "BZ=F": "Brent Petrol (Dolar)"
    },
    "Kripto Para (TL)": {
        "BTC-TRY": "Bitcoin (TL)",
        "ETH-TRY": "Ethereum (TL)",
        "SOL-TRY": "Solana (TL)",
        "AVAX-TRY": "Avalanche (TL)",
        "XRP-TRY": "Ripple (TL)",
        "USDT-TRY": "Tether (TL)",
        "DOGE-TRY": "Dogecoin (TL)"
    },
    "ABD Borsaları (Dolar)": {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "TSLA": "Tesla",
        "NVDA": "NVIDIA",
        "AMZN": "Amazon",
        "GOOG": "Google"
    }
}

# --- 3. YARDIMCI FONKSİYONLAR ---

def save_to_db(collection_name, data):
    """Veriyi belirtilen koleksiyona kaydeder"""
    data["created_at"] = firestore.SERVER_TIMESTAMP
    if "date" in data and isinstance(data["date"], datetime.date):
        data["date_str"] = data["date"].strftime("%Y-%m-%d")
    if "due_date" in data and isinstance(data["due_date"], datetime.date):
        data["due_date_str"] = data["due_date"].strftime("%Y-%m-%d")
    
    db.collection(collection_name).add(data)
    st.toast(f"✅ Kayıt Başarılı: {collection_name}")

def delete_from_db(collection_name, doc_id):
    """Verilen ID'ye sahip dökümanı siler"""
    try:
        db.collection(collection_name).document(doc_id).delete()
        st.toast("🗑️ Kayıt Silindi!")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Silme hatası: {e}")

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
    """Metni sese çevirir"""
    try:
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp, format='audio/mp3')
    except: pass

def calculate_totals(df):
    """Günlük, Haftalık, Aylık toplam hesaplar"""
    if df.empty: return 0, 0, 0
    df['date_dt'] = pd.to_datetime(df['date_str'])
    today = pd.Timestamp.now().normalize()
    start_week = today - pd.Timedelta(days=today.dayofweek)
    start_month = today.replace(day=1)
    
    d_sum = df[df['date_dt'] == today]['amount'].sum()
    w_sum = df[df['date_dt'] >= start_week]['amount'].sum()
    m_sum = df[df['date_dt'] >= start_month]['amount'].sum()
    return d_sum, w_sum, m_sum

# --- 4. FİNANSAL VERİ ÇEKME (CACHE İLE HIZLANDIRILDI) ---
@st.cache_data(ttl=600) # 10 dakikada bir güncelle
def get_asset_current_price(symbol):
    """Anlık fiyat çeker"""
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1d")
        if not history.empty:
            return history['Close'].iloc[-1]
        return 0.0
    except: return 0.0

# --- 5. ARAYÜZ VE NAVİGASYON ---
st.sidebar.title("🚀 Life OS")
main_module = st.sidebar.selectbox(
    "Modül Seç", 
    ["Dil Asistanı", "Fiziksel Takip", "Finans Merkezi"]
)

# ==========================================
# MODÜL 1: DİL ASİSTANI
# ==========================================
if main_module == "Dil Asistanı":
    st.title("🇩🇪 🇬🇧 Dil Asistanı")
    lang_menu = st.sidebar.radio("İşlemler", ["Kelime Ekle", "Excel'den Yükle", "Kelime Listesi", "Günlük Test"])
    
    if lang_menu == "Kelime Ekle":
        st.subheader("Manuel Ekleme")
        c1, c2, c3 = st.columns(3)
        en = c1.text_input("🇬🇧 İngilizce")
        de = c2.text_input("🇩🇪 Almanca")
        tr = c3.text_input("🇹🇷 Türkçe")
        sent = st.text_area("Örnek Cümle")
        if st.button("Kaydet"):
            save_to_db("vocabulary", {"en": en, "de": de, "tr": tr, "sentence_source": sent, "learned_count": 0})

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
            
            # Liste görünümü ve silme
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
        with st.form("workout_form"):
            c1, c2 = st.columns(2)
            w_type = c1.selectbox("Tür", ["Fitness", "Kardiyo", "Yüzme", "Yoga"])
            dur = c2.number_input("Süre (dk)", 10, 300, 60)
            note = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"):
                save_to_db("workouts", {"type": w_type, "duration": dur, "notes": note, "date": datetime.date.today()})
        
        st.divider()
        df = get_data("workouts")
        if not df.empty:
            st.write("Geçmiş İdmanlar (Silmek için sağdaki butonu kullan)")
            for idx, row in df.iterrows():
                cl1, cl2, cl3, cl4 = st.columns([2, 2, 4, 1])
                cl1.write(f"📅 {row['date_str']}")
                cl2.write(f"🏃 {row['type']} ({row['duration']} dk)")
                cl3.write(f"📝 {row['notes']}")
                if cl4.button("Sil", key=f"del_wrk_{row['id']}"):
                    delete_from_db("workouts", row['id'])

    elif phys_menu == "Ölçü Takibi":
        st.subheader("📏 Vücut Analizi")
        with st.form("body"):
            c1, c2, c3 = st.columns(3)
            w = c1.number_input("Kilo", format="%.1f")
            f = c2.number_input("Yağ %", format="%.1f")
            m = c3.number_input("Kas %", format="%.1f")
            if st.form_submit_button("Kaydet"):
                save_to_db("measurements", {"weight": w, "fat": f, "muscle": m, "date": datetime.date.today()})
        st.divider()
        df = get_data("measurements")
        if not df.empty:
            df['date'] = pd.to_datetime(df['date_str'])
            st.line_chart(df.sort_values('date'), x='date', y='weight')
            
            with st.expander("Kayıtları Düzenle"):
                for idx, row in df.iterrows():
                    c1, c2, c3 = st.columns([2, 2, 1])
                    c1.write(f"{row['date_str']}")
                    c2.write(f"{row['weight']} kg")
                    if c3.button("Sil", key=f"del_meas_{row['id']}"):
                        delete_from_db("measurements", row['id'])

    elif phys_menu == "Öğün Takibi":
        st.subheader("🥗 Beslenme")
        with st.form("meal_form"):
            c1, c2 = st.columns([1,2])
            cal = c1.number_input("Kalori", 0, 2000)
            meal = c2.text_input("İçerik")
            if st.form_submit_button("Ekle"):
                save_to_db("meals", {"calories": cal, "content": meal, "date": datetime.date.today()})
        
        st.divider()
        df = get_data("meals")
        if not df.empty:
            tod = str(datetime.date.today())
            total = df[df['date_str'] == tod]['calories'].sum()
            st.metric("Bugün Alınan", f"{total} kcal")
            
            st.write("Öğün Listesi")
            for idx, row in df.iterrows():
                c1, c2, c3, c4 = st.columns([2, 2, 4, 1])
                c1.write(row['date_str'])
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
    
    df_exp = get_data("expenses")
    df_pay = get_data("payments")
    df_inv = get_data("investments")

    # --- TAB 1: GENEL BAKIŞ ---
    with tabs[0]:
        st.header("Finansal Özet")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader("Harcamalar")
            if not df_exp.empty:
                d, w, m = calculate_totals(df_exp)
                st.metric("Bu Ay", f"{m:,.2f} TL", f"Bugün: {d:,.2f} TL")
            else: st.write("-")
        with c2:
            st.subheader("Yatırımlar")
            if not df_inv.empty:
                total_inv = df_inv['amount'].sum()
                st.metric("Toplam Maliyet", f"{total_inv:,.2f} TL")
            else: st.write("-")
        with c3:
            st.subheader("Ödemeler")
            if not df_pay.empty:
                _, _, m_pay = calculate_totals(df_pay)
                st.metric("Bu Ay Ödenen", f"{m_pay:,.2f} TL")
            else: st.write("-")
        st.divider()
        if not df_exp.empty:
            cat_sum = df_exp.groupby("category")["amount"].sum()
            fig, ax = plt.subplots(figsize=(4, 4))
            ax.pie(cat_sum, labels=cat_sum.index, autopct='%1.1f%%', startangle=90)
            st.pyplot(fig)

    # --- TAB 2: HARCAMA ---
    with tabs[1]:
        st.header("Yeni Harcama Ekle")
        with st.form("expense_form_full"):
            col1, col2, col3 = st.columns(3)
            date_in = col1.date_input("Tarih", datetime.date.today())
            place_in = col2.text_input("Yer")
            amount_in = col3.number_input("Tutar (TL)", min_value=0.0, step=10.0)
            col4, col5, col6 = st.columns(3)
            cat_in = col4.selectbox("Tür", ["Market", "Yiyecek", "İçecek", "Ulaşım", "Eğlence", "Diğer"])
            method_in = col5.selectbox("Şekil", ["Kredi Kartı", "Nakit", "Banka Kartı"])
            nec_in = col6.selectbox("Gerekli mi?", ["Evet", "Hayır"])
            desc_in = st.text_area("Açıklama")
            if st.form_submit_button("Harcamayı Kaydet"):
                save_to_db("expenses", {
                    "date": datetime.datetime.combine(date_in, datetime.time.min),
                    "place": place_in, "amount": amount_in, "category": cat_in,
                    "method": method_in, "necessity": nec_in, "desc": desc_in
                })

        st.divider()
        st.subheader("Son Harcamalar")
        if not df_exp.empty:
            for idx, row in df_exp.iterrows():
                c1, c2, c3, c4 = st.columns([2, 4, 2, 1])
                c1.write(f"📅 {row['date_str']}")
                c2.write(f"{row['place']} ({row['category']})")
                c3.write(f"{row['amount']} TL")
                if c4.button("Sil", key=f"del_exp_{row['id']}"):
                    delete_from_db("expenses", row['id'])

    # --- TAB 3: ÖDEME ---
    with tabs[2]:
        st.header("Ödeme / Borç Kapatma")
        with st.form("payment_form_full"):
            c1, c2, c3 = st.columns(3)
            p_date = c1.date_input("Tarih", datetime.date.today())
            p_amount = c2.number_input("Tutar (TL)", min_value=0.0)
            p_place = c3.text_input("Yer / Kanal")
            c4, c5 = st.columns(2)
            p_type = c4.selectbox("Ödeme Türü", ["Kredi Kartı Borcu", "Fatura", "Kredi", "Diğer"])
            p_acc = c5.text_input("Hangi Hesaptan?", value="Maaş Kartı")
            p_desc = st.text_area("Açıklama")
            if st.form_submit_button("Ödemeyi Kaydet"):
                save_to_db("payments", {
                    "date": datetime.datetime.combine(p_date, datetime.time.min),
                    "amount": p_amount, "category": p_type, 
                    "place": p_place, "account": p_acc, "desc": p_desc
                })
        st.divider()
        st.subheader("Son Ödemeler")
        if not df_pay.empty:
            for idx, row in df_pay.iterrows():
                c1, c2, c3, c4 = st.columns([2, 4, 2, 1])
                c1.write(row['date_str'])
                c2.write(f"{row['category']} - {row['place']}")
                c3.write(f"{row['amount']} TL")
                if c4.button("Sil", key=f"del_pay_{row['id']}"):
                    delete_from_db("payments", row['id'])

    # --- TAB 4: BORÇ / ALACAK ---
    with tabs[3]:
        st.header("🤝 Borç Defteri")
        debt_type = st.radio("Yön", ["🟢 Borç Verdim (Alacak)", "🔴 Borç Aldım (Borç)"], horizontal=True)
        with st.form("debt_form_full"):
            d1, d2, d3 = st.columns(3)
            person = d1.text_input("Kişi Adı")
            amount = d2.number_input("Miktar", min_value=0.0)
            curr = d3.selectbox("Birim", ["TL", "USD", "EUR", "Altın"])
            d4, d5 = st.columns(2)
            d_given = d4.date_input("Tarih")
            d_due = d5.date_input("Vade (Geri Ödeme)")
            if st.form_submit_button("Kaydet"):
                save_to_db("debts", {
                    "type": "Alacak" if "Verdim" in debt_type else "Borç",
                    "person": person, "amount": amount, "currency": curr,
                    "date": datetime.datetime.combine(d_given, datetime.time.min),
                    "due_date": datetime.datetime.combine(d_due, datetime.time.min),
                    "status": "Aktif"
                })
        st.divider()
        df_debt = get_data("debts")
        if not df_debt.empty:
            st.write("Kayıtlar")
            for idx, row in df_debt.iterrows():
                c1, c2, c3, c4 = st.columns([1, 3, 2, 1])
                c1.write("🟢" if row['type'] == "Alacak" else "🔴")
                c2.write(f"{row['person']} ({row['amount']} {row['currency']})")
                c3.write(f"Vade: {row.get('due_date_str', '-')}")
                if c4.button("Sil", key=f"del_debt_{row['id']}"):
                    delete_from_db("debts", row['id'])

    # --- TAB 5: YATIRIM (DÜZELTİLMİŞ & FORM KALDIRILMIŞ) ---
    with tabs[4]:
        st.header("📈 Akıllı Portföy")
        
        # DİKKAT: Burada st.form KULLANMIYORUZ. 
        # Böylece kategori değişince sayfa yenileniyor ve liste güncelleniyor.
        
        c_i1, c_i2 = st.columns(2)
        inv_d = c_i1.date_input("Tarih", datetime.date.today())
        
        # Kategori Seçimi (Form dışında olduğu için anlık tetiklenir)
        category_options = list(SYMBOL_MAP.keys()) + ["Diğer / Manuel Arama"]
        inv_cat = c_i2.selectbox("Yatırım Türü", category_options)
        
        c_i3, c_i4 = st.columns(2)
        selected_symbol = ""
        manual_name = ""
        
        # Dinamik Liste Mantığı
        with c_i3:
            if inv_cat == "Diğer / Manuel Arama":
                selected_symbol = st.text_input("Sembol Gir (Yahoo Kodu)", help="Örn: IBM").strip()
                manual_name = st.text_input("Varlık Adı", placeholder="Örn: Yabancı Fon")
            else:
                current_map = SYMBOL_MAP.get(inv_cat, {})
                if current_map:
                    asset_options = [f"{k} | {v}" for k, v in current_map.items()]
                    selection = st.selectbox("Varlık Seç", asset_options)
                    if selection:
                        selected_symbol = selection.split(" | ")[0]
                        manual_name = selection.split(" | ")[1]
        
        with c_i4:
            inv_q = st.number_input("Adet", min_value=0.0, format="%.4f")
            inv_c = st.number_input("Toplam Maliyet (TL)", min_value=0.0)

        # Kaydet Butonu (Normal buton, form submit değil)
        if st.button("Yatırımı Ekle", type="primary"):
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
                # Butona basınca sayfa yenilensin ki form temizlensin
                time.sleep(0.5)
                st.rerun()

        st.divider()
        if not df_inv.empty:
            st.subheader("Portföy Analizi")
            
            # Tablo verilerini hazırla
            table_data = []
            total_val = 0
            total_cost = 0
            
            p_bar = st.progress(0)
            
            # Veri listeleme döngüsü
            for idx, row in df_inv.iterrows():
                p_bar.progress((idx + 1) / len(df_inv))
                
                # Fiyatı çek (Cache kullanır)
                cur_p = get_asset_current_price(row.get('symbol')) if row.get('symbol') else 0
                qty = float(row['quantity'])
                cost = float(row['amount'])
                
                cur_val = (cur_p * qty) if cur_p > 0 else cost
                total_val += cur_val
                total_cost += cost
                
                # Satır Gösterimi
                col_1, col_2, col_3, col_4, col_5 = st.columns([3, 2, 2, 2, 1])
                col_1.write(f"**{row['asset_name']}**")
                col_2.write(f"Adet: {qty}")
                col_3.write(f"Maliyet: {cost:,.0f} TL")
                
                # Kar/Zarar Rengi
                profit = cur_val - cost
                color = "green" if profit >= 0 else "red"
                col_4.markdown(f":{color}[{cur_val:,.0f} TL]")
                
                if col_5.button("Sil", key=f"del_inv_{row['id']}"):
                    delete_from_db("investments", row['id'])
            
            p_bar.empty()
            
            # Özet
            k1, k2, k3 = st.columns(3)
            k1.metric("Toplam Maliyet", f"{total_cost:,.2f} TL")
            k2.metric("Güncel Değer", f"{total_val:,.2f} TL")
            diff = total_val - total_cost
            k3.metric("Fark", f"{diff:,.2f} TL", delta=f"{diff:,.2f}")
