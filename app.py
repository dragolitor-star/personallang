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

# --- 2. YARDIMCI FONKSİYONLAR ---

def save_to_db(collection_name, data):
    """Veriyi belirtilen koleksiyona kaydeder"""
    data["created_at"] = firestore.SERVER_TIMESTAMP
    # Tarih formatlarını string'e çevir (Sorgulama kolaylığı için)
    if "date" in data and isinstance(data["date"], datetime.date):
        data["date_str"] = data["date"].strftime("%Y-%m-%d")
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

# --- 3. FİNANSAL VERİ ÇEKME (YAHOO FINANCE) ---
def get_asset_current_price(symbol):
    """Anlık fiyat çeker"""
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1d")
        if not history.empty:
            return history['Close'].iloc[-1]
        return 0.0
    except: return 0.0

def get_historical_price(symbol, date_obj):
    """Geçmiş kapanış fiyatını çeker"""
    try:
        start_date = date_obj.strftime("%Y-%m-%d")
        end_date = (date_obj + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        data = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if not data.empty:
            # Multi-index dönerse düzelt
            if isinstance(data.columns, pd.MultiIndex):
                return data['Close'].iloc[0].iloc[0] 
            return data['Close'].iloc[0]
        return 0.0
    except: return 0.0

# --- 4. ARAYÜZ VE NAVİGASYON ---
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
        st.info("Sütunlar: 'Word', 'Meaning 1', 'Pharase' (veya Phrase) içermeli.")
        
        lang_type = st.radio("Dil Seçimi", ["🇬🇧 İngilizce", "🇩🇪 Almanca"])
        up_file = st.file_uploader("Excel Dosyası", type=["xlsx", "xls"])
        
        if up_file and st.button("Yüklemeyi Başlat"):
            try:
                df = pd.read_excel(up_file)
                # Sütun isimlerini temizle
                df.columns = df.columns.str.strip()
                count = 0
                
                progress_bar = st.progress(0)
                for idx, row in df.iterrows():
                    word_data = {}
                    
                    # Ortak 'Phrase' bulma (Yazım hatası toleransı)
                    phrase_col = next((c for c in df.columns if "harase" in c.lower() or "hrase" in c.lower()), None)
                    word_data["sentence_source"] = str(row[phrase_col]) if phrase_col and pd.notna(row[phrase_col]) else ""

                    if "İngilizce" in lang_type:
                        word_data["en"] = str(row.get("Word", ""))
                        # Meaning 1 ve 2 birleşimi
                        m1 = str(row.get("Meaning 1", ""))
                        m2 = str(row.get("Meaning 2", ""))
                        word_data["tr"] = f"{m1}, {m2}".strip(", ") if pd.notna(row.get("Meaning 2")) else m1
                        word_data["de"] = ""
                    else:
                        word_data["de"] = str(row.get("Word", ""))
                        # Almanca excelde 'Meaning in Turkish' var
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
                
                st.success(f"{count} kelime başarıyla eklendi!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")

    elif lang_menu == "Kelime Listesi":
        df = get_data("vocabulary")
        if not df.empty:
            search = st.text_input("Kelime Ara")
            if search:
                df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
            
            st.dataframe(df[['en', 'de', 'tr', 'sentence_source']], use_container_width=True)
            
            sel_word = st.selectbox("Dinlemek için seç:", df['tr'].unique())
            if sel_word:
                row = df[df['tr'] == sel_word].iloc[0]
                c1, c2 = st.columns(2)
                if row.get('en'): 
                    if c1.button("🇬🇧 Dinle"): speak(row['en'], 'en')
                if row.get('de'): 
                    if c2.button("🇩🇪 Dinle"): speak(row['de'], 'de')

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
                    st.success(f"Cevap: **{q['tr']}**")
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
                elif st.button("Cevabı Göster"):
                    st.session_state['show'] = True
                    st.rerun()
            else:
                st.balloons()
                st.success(f"Bitti! Skor: {st.session_state['score']}")
                if st.button("Tekrar"): new_quiz()

# ==========================================
# MODÜL 2: FİZİKSEL TAKİP
# ==========================================
elif main_module == "Fiziksel Takip":
    st.title("💪 Fiziksel Gelişim")
    phys_menu = st.sidebar.radio("Alt Menü", ["İdman Takibi", "Ölçü Takibi", "Öğün Takibi"])

    if phys_menu == "İdman Takibi":
        st.subheader("🏋️‍♂️ İdman Kaydı")
        c1, c2 = st.columns(2)
        w_type = c1.selectbox("Tür", ["Fitness", "Kardiyo", "Yüzme", "Yoga"])
        dur = c2.number_input("Süre (dk)", 10, 300, 60)
        note = st.text_area("Notlar (Bölge, set vb.)")
        if st.button("Kaydet"):
            save_to_db("workouts", {"type": w_type, "duration": dur, "notes": note, "date": datetime.date.today()})
        
        st.divider()
        df = get_data("workouts")
        if not df.empty: st.dataframe(df[['date_str', 'type', 'duration', 'notes']], use_container_width=True)

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

    elif phys_menu == "Öğün Takibi":
        st.subheader("🥗 Beslenme")
        c1, c2 = st.columns([1,2])
        cal = c1.number_input("Kalori", 0, 2000)
        meal = c2.text_input("İçerik")
        if st.button("Ekle"):
            save_to_db("meals", {"calories": cal, "content": meal, "date": datetime.date.today()})
        
        st.divider()
        df = get_data("meals")
        if not df.empty:
            tod = str(datetime.date.today())
            total = df[df['date_str'] == tod]['calories'].sum()
            st.metric("Bugün Alınan", f"{total} kcal")
            st.dataframe(df)

# ==========================================
# MODÜL 3: FİNANS MERKEZİ (TAM KOD)
# ==========================================
elif main_module == "Finans Merkezi":
    st.title("💰 Finansal Yönetim Paneli")
    
    tabs = st.tabs(["📊 Genel Bakış", "💸 Harcama", "💳 Ödeme", "🤝 Borç/Alacak", "📈 Yatırım"])
    
    # Genel verileri çek
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
            st.subheader("Kategori Dağılımı")
            cat_sum = df_exp.groupby("category")["amount"].sum()
            fig, ax = plt.subplots(figsize=(5, 5))
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
            st.dataframe(df_exp[['date_str', 'place', 'amount', 'category', 'necessity']], use_container_width=True)

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
            st.dataframe(df_pay[['date_str', 'category', 'amount', 'desc']], use_container_width=True)

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
            st.dataframe(df_debt[['type', 'person', 'amount', 'currency', 'due_date_str']], use_container_width=True)

    # --- TAB 5: YATIRIM (AKILLI MODÜL) ---
    with tabs[4]:
        st.header("📈 Akıllı Portföy")
        with st.expander("ℹ️ Sembol Bilgisi"):
            st.write("Dolar: USDTRY=X | Euro: EURTRY=X | Gram Altın: GLD (veya XAUTRY=X) | BIST: GARAN.IS")

        with st.form("invest_smart"):
            i1, i2, i3 = st.columns(3)
            inv_d = i1.date_input("Tarih")
            inv_sym = i2.text_input("Sembol (Örn: GARAN.IS)", help="Otomatik fiyat için").upper()
            inv_cat = i3.selectbox("Tür", ["Borsa", "Döviz", "Altın", "Kripto", "Fon"])
            
            i4, i5, i6 = st.columns(3)
            inv_n = i4.text_input("Varlık Adı", value="Hisse/Döviz Adı")
            inv_q = i5.number_input("Adet", min_value=0.0, format="%.4f")
            inv_c = i6.number_input("Toplam Maliyet (TL)", min_value=0.0)
            
            if st.form_submit_button("Yatırımı Ekle"):
                save_to_db("investments", {
                    "date": datetime.datetime.combine(inv_d, datetime.time.min),
                    "symbol": inv_sym, "category": inv_cat, "asset_name": inv_n,
                    "quantity": inv_q, "amount": inv_c, "status": "Aktif"
                })

        st.divider()
        if not df_inv.empty:
            st.subheader("Portföy Analizi")
            
            # Tablo verilerini hazırla
            table_data = []
            total_val = 0
            total_cost = 0
            
            p_bar = st.progress(0)
            for idx, row in df_inv.iterrows():
                p_bar.progress((idx + 1) / len(df_inv))
                
                cur_p = get_asset_current_price(row.get('symbol')) if row.get('symbol') else 0
                qty = float(row['quantity'])
                cost = float(row['amount'])
                
                # Eğer anlık fiyat çekilemediyse maliyeti kullan
                cur_val = (cur_p * qty) if cur_p > 0 else cost
                
                total_val += cur_val
                total_cost += cost
                
                table_data.append({
                    "Varlık": row['asset_name'],
                    "Adet": qty,
                    "Maliyet": f"{cost:,.2f}",
                    "Güncel Değer": f"{cur_val:,.2f}",
                    "Kâr/Zarar": f"{(cur_val - cost):,.2f}"
                })
            
            p_bar.empty()
            
            # Metrikler
            k1, k2, k3 = st.columns(3)
            k1.metric("Toplam Maliyet", f"{total_cost:,.2f} TL")
            k2.metric("Güncel Değer", f"{total_val:,.2f} TL")
            diff = total_val - total_cost
            k3.metric("Fark", f"{diff:,.2f} TL", delta=f"{diff:,.2f}")
            
            st.dataframe(pd.DataFrame(table_data), use_container_width=True)
