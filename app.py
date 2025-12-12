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
import calendar

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

# --- 3. EGZERSİZ LİSTESİ (BASE) ---
BASE_EXERCISES = {
    "Göğüs": ["Bench Press", "Incline Dumbell Press", "Cable Chest Fly", "Push Up", "Dips"],
    "Sırt": ["Pull Up", "Lat Pulldown", "Barbell Row", "Deadlift", "Face Pull"],
    "Bacak": ["Squat", "Leg Press", "Leg Extension", "Leg Curl", "Calf Raise"],
    "Omuz": ["Overhead Press", "Lateral Raise", "Front Raise", "Reverse Pec Deck"],
    "Ön Kol": ["Barbell Curl", "Dumbell Curl", "Hammer Curl", "Preacher Curl"],
    "Arka Kol": ["Tricep Pushdown", "Skullcrusher", "Overhead Extension"],
    "Karın": ["Crunch", "Plank", "Leg Raise", "Russian Twist"],
    "Kardiyo": ["Koşu Bandı", "Bisiklet", "Eliptik", "Yüzme", "İnterval Koşu"]
}

# --- 4. YARDIMCI FONKSİYONLAR ---

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
            item['Sil'] = False 
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

def update_liability_balance(liability_id, amount_paid):
    """Ödeme yapıldığında ilgili borç bakiyesini düşer"""
    try:
        doc_ref = db.collection("liabilities").document(liability_id)
        doc = doc_ref.get()
        if doc.exists:
            current_bal = float(doc.to_dict().get('remaining_amount', 0.0))
            new_bal = current_bal - amount_paid
            doc_ref.update({"remaining_amount": new_bal})
            st.toast(f"📉 Borç bakiyesi güncellendi! Yeni kalan: {new_bal:,.2f} TL")
    except Exception as e:
        st.error(f"Bakiye güncelleme hatası: {e}")

def get_full_exercise_map():
    """Standart ve özel hareketleri birleştirir"""
    full_map = {k: v.copy() for k, v in BASE_EXERCISES.items()}
    try:
        custom_docs = db.collection("custom_exercises").stream()
        for doc in custom_docs:
            data = doc.to_dict()
            reg = data.get('region')
            name = data.get('name')
            if reg and name:
                if reg not in full_map:
                    full_map[reg] = []
                full_map[reg].append(name)
    except: pass
    return full_map

def speak(text, lang='en'):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp, format='audio/mp3')
    except: pass

def calculate_totals(df):
    """Toplam hesaplama fonksiyonu"""
    if df.empty: return 0, 0, 0
    if 'date_str' not in df.columns: return 0, 0, 0
    
    try:
        df = df.copy()
        df['date_dt'] = pd.to_datetime(df['date_str'], errors='coerce')
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        
        today = pd.Timestamp.now().normalize()
        start_week = today - pd.Timedelta(days=today.dayofweek)
        start_month = today.replace(day=1)
        
        d_sum = df[df['date_dt'].dt.normalize() == today]['amount'].sum()
        w_sum = df[df['date_dt'].dt.normalize() >= start_week]['amount'].sum()
        m_sum = df[df['date_dt'].dt.normalize() >= start_month]['amount'].sum()
        
        return d_sum, w_sum, m_sum
    except Exception as e:
        st.error(f"Hesaplama Hatası: {e}")
        return 0, 0, 0

@st.cache_data(ttl=600)
def get_asset_current_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1d")
        if not history.empty: return history['Close'].iloc[-1]
        return 0.0
    except: return 0.0

def update_daily_activity_from_table(date_str, field, value):
    """Günlük aktivite tablosunu günceller"""
    try:
        docs = db.collection("daily_activities").where("date_str", "==", date_str).stream()
        doc_list = list(docs)
        data = {field: value, "date_str": date_str}
        if doc_list:
            db.collection("daily_activities").document(doc_list[0].id).update({field: value})
        else:
            data["created_at"] = firestore.SERVER_TIMESTAMP
            db.collection("daily_activities").add(data)
    except: pass

def update_measurement_from_table(date_str, weight_val):
    """Tablodan gelen kilo bilgisini günceller"""
    try:
        docs = db.collection("measurements").where("date_str", "==", date_str).stream()
        doc_list = list(docs)
        if doc_list:
            db.collection("measurements").document(doc_list[0].id).update({"weight": weight_val})
        else:
            db.collection("measurements").add({
                "weight": weight_val, 
                "date_str": date_str, 
                "created_at": firestore.SERVER_TIMESTAMP
            })
    except: pass

def get_monthly_habit_data(year, month):
    """Belirli bir ayın alışkanlık verilerini çeker"""
    doc_id = f"{year}_{month}"
    doc = db.collection("habit_logs").document(doc_id).get()
    if doc.exists:
        return doc.to_dict()
    return {}

def update_monthly_habit_data(year, month, habit_data, sleep_data):
    """Ayın alışkanlık verilerini kaydeder"""
    doc_id = f"{year}_{month}"
    db.collection("habit_logs").document(doc_id).set({
        "habits": habit_data,
        "sleep": sleep_data,
        "updated_at": firestore.SERVER_TIMESTAMP
    }, merge=True)

# --- 5. ARAYÜZ VE MODÜLLER ---
st.sidebar.title("🚀 Life OS")
main_module = st.sidebar.selectbox("Modül Seç", ["Dil Asistanı", "Fiziksel Takip", "Alışkanlık Takibi", "Finans Merkezi"])

# ==========================================
# MODÜL 1: DİL ASİSTANI
# ==========================================
if main_module == "Dil Asistanı":
    st.title("🇩🇪 🇬🇧 Dil Asistanı")
    lang_menu = st.sidebar.radio("İşlemler", ["Kelime Ekle", "Excel'den Yükle", "Kelime Listesi", "Günlük Test"])
    
    if lang_menu == "Kelime Ekle":
        st.subheader("Manuel Ekleme")
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
    st.title("💪 Fiziksel Gelişim Paneli")
    
    FULL_EXERCISE_LIST = get_full_exercise_map()
    
    tabs = st.tabs(["📅 Fiziksel Aktivite Takip Tablosu", "⚡ Canlı İdman Modu", "⚙️ Hareket Tanımla"])

    with tabs[0]:
        st.header("Fiziksel Aktivite Takip Tablosu")
        
        df_meas = get_data("measurements")
        if not df_meas.empty:
            if 'date_str' in df_meas.columns:
                df_meas['date'] = pd.to_datetime(df_meas['date_str'], errors='coerce')
                df_meas = df_meas.sort_values('date')
                st.line_chart(df_meas, x='date', y='weight')
            else:
                df_meas['date'] = pd.to_datetime([])
        else:
            df_meas = pd.DataFrame(columns=['date', 'weight'])

        st.divider()
        st.subheader(f"Aylık Takip Listesi ({datetime.datetime.now().strftime('%B %Y')})")
        
        df_logs = get_data("workout_logs")
        df_daily = get_data("daily_activities")
        
        current_month = datetime.datetime.now().month
        current_year = datetime.datetime.now().year
        days_in_month = calendar.monthrange(current_year, current_month)[1]
        
        cols = [str(d) for d in range(1, days_in_month + 1)]
        rows = ["İdman (Ana Odak)", "Kilo", "15 Şınav", "10 Muscle Up", "10 Barfiks"]
        dashboard_df = pd.DataFrame(index=rows, columns=cols).fillna("")
        
        if not df_logs.empty and 'date_str' in df_logs.columns:
            df_logs['date'] = pd.to_datetime(df_logs['date_str'])
            month_logs = df_logs[(df_logs['date'].dt.month == current_month) & (df_logs['date'].dt.year == current_year)]
            for _, row in month_logs.iterrows():
                day = str(row['date'].day)
                existing = dashboard_df.at["İdman (Ana Odak)", day]
                dashboard_df.at["İdman (Ana Odak)", day] = f"{existing} ✅ {row.get('main_focus', '')}".strip()

        if not df_meas.empty and 'date' in df_meas.columns:
            month_meas = df_meas[(df_meas['date'].dt.month == current_month) & (df_meas['date'].dt.year == current_year)]
            for _, row in month_meas.iterrows():
                day = str(row['date'].day)
                dashboard_df.at["Kilo", day] = str(row['weight'])

        if not df_daily.empty and 'date_str' in df_daily.columns:
            df_daily['date'] = pd.to_datetime(df_daily['date_str'])
            month_daily = df_daily[(df_daily['date'].dt.month == current_month) & (df_daily['date'].dt.year == current_year)]
            for _, row in month_daily.iterrows():
                day = str(row['date'].day)
                if pd.notna(row.get('pushups')): dashboard_df.at["15 Şınav", day] = str(row.get('pushups'))
                if pd.notna(row.get('muscleups')): dashboard_df.at["10 Muscle Up", day] = str(row.get('muscleups'))
                if pd.notna(row.get('pullups')): dashboard_df.at["10 Barfiks", day] = str(row.get('pullups'))

        edited_dashboard = st.data_editor(dashboard_df, use_container_width=True, key="phys_table")
        
        if st.button("Tablodaki Değişiklikleri Kaydet", type="primary"):
            for day in cols:
                try:
                    date_obj = datetime.date(current_year, current_month, int(day))
                    date_str = date_obj.strftime("%Y-%m-%d")
                    
                    w_val = edited_dashboard.at["Kilo", day]
                    if w_val and str(w_val).strip() != "":
                        update_measurement_from_table(date_str, float(w_val))
                    
                    push_val = edited_dashboard.at["15 Şınav", day]
                    musc_val = edited_dashboard.at["10 Muscle Up", day]
                    pull_val = edited_dashboard.at["10 Barfiks", day]
                    
                    if push_val or musc_val or pull_val:
                        docs = db.collection("daily_activities").where("date_str", "==", date_str).stream()
                        doc_list = list(docs)
                        data_update = {}
                        if push_val: data_update["pushups"] = push_val
                        if musc_val: data_update["muscleups"] = musc_val
                        if pull_val: data_update["pullups"] = pull_val
                        
                        if data_update:
                            if doc_list:
                                db.collection("daily_activities").document(doc_list[0].id).update(data_update)
                            else:
                                data_update["date_str"] = date_str
                                data_update["created_at"] = firestore.SERVER_TIMESTAMP
                                db.collection("daily_activities").add(data_update)
                except: pass
            st.success("Tablo başarıyla güncellendi!")
            time.sleep(1)
            st.rerun()

        st.divider()
        st.subheader("Geçmiş İdman Detayları (Liste)")
        if not df_logs.empty:
            for idx, row in df_logs.iterrows():
                log_title = f"📅 {row.get('date_str','-')} - {row.get('main_focus', 'Genel')} (Toplam: {row.get('total_duration', 0)} dk)"
                with st.expander(log_title):
                    sections = row.get('sections', [])
                    if sections:
                        sec_tabs = st.tabs([f"{s['name']} ({s.get('duration',0)} dk)" for s in sections])
                        for i, section in enumerate(sections):
                            with sec_tabs[i]:
                                exercises = section.get('exercises', [])
                                for ex in exercises:
                                    st.markdown(f"#### 🏋️‍♂️ {ex['name']}")
                                    sets_data = []
                                    for s_idx, s in enumerate(ex.get('sets', [])):
                                        if "cardio_duration" in s:
                                            sets_data.append({
                                                "Tip": "Kardiyo",
                                                "Süre": f"{s.get('cardio_duration')} dk",
                                                "Mesafe": f"{s.get('distance')} km",
                                                "Hız": s.get('speed'),
                                                "Eğim": s.get('incline'),
                                                "Kalori": s.get('calories')
                                            })
                                        else:
                                            set_type = "DROP SET 🔻" if s.get('is_dropset') else f"Set {s_idx + 1}"
                                            sets_data.append({
                                                "Set Tipi": set_type,
                                                "Ağırlık": f"{s.get('weight')} KG",
                                                "Tekrar": s.get('reps'),
                                                "ROM": s.get('rom'),
                                                "Zorlanma": s.get('difficulty')
                                            })
                                    if sets_data: st.table(pd.DataFrame(sets_data))
                                    st.divider()
                    if st.button("Bu İdman Kaydını Sil", key=f"del_log_{row['id']}"):
                        delete_from_db("workout_logs", row['id'])

    with tabs[1]:
        st.header("⚡ Canlı İdman Paneli")
        
        if 'live_workout' not in st.session_state:
            st.session_state.live_workout = {
                "active": False, "start_time": None, "sections": [],
                "current_section_start": None, "exercises_temp": [] 
            }

        lw = st.session_state.live_workout

        if not lw["active"]:
            st.subheader("Bugünkü İdman Planı")
            c1, c2, c3, c4 = st.columns(4)
            body_parts = ["Göğüs", "Sırt", "Bacak", "Omuz", "Ön Kol", "Arka Kol", "Yok"]
            main_part = c1.selectbox("Ana Bölge", body_parts, index=0)
            side_part = c2.selectbox("Yan Bölge", body_parts, index=6)
            abs_opt = c3.selectbox("Karın", ["Yok", "Var"], index=0)
            cardio_opt = c4.selectbox("Kardiyo", ["Yok", "Var"], index=0)
            
            if st.button("🚀 İdmanı Başlat", type="primary"):
                focus_parts = []
                if main_part != "Yok": focus_parts.append(main_part)
                if side_part != "Yok": focus_parts.append(side_part)
                if abs_opt == "Var": focus_parts.append("Karın")
                if cardio_opt == "Var": focus_parts.append("Kardiyo")
                
                final_focus = " - ".join(focus_parts) if focus_parts else "Genel İdman"
                
                lw["active"] = True
                lw["start_time"] = datetime.datetime.now()
                lw["main_focus"] = final_focus
                st.rerun()
        
        else:
            elapsed = datetime.datetime.now() - lw["start_time"]
            st.info(f"⏱️ İdman Süresi: {str(elapsed).split('.')[0]} | Odak: {lw['main_focus']}")
            
            with st.container(border=True):
                st.subheader("Bölüm Ekle / Yönet")
                
                if lw["current_section_start"] is None:
                    sec_name = st.selectbox("Bölüm Seç", ["Isınma", "Göğüs", "Sırt", "Bacak", "Omuz", "Ön Kol", "Arka Kol", "Karın", "Kardiyo"])
                    if st.button("▶️ Bölümü Başlat"):
                        lw["current_section_start"] = datetime.datetime.now()
                        lw["current_section_name"] = sec_name
                        lw["exercises_temp"] = []
                        st.rerun()
                else:
                    sec_elapsed = datetime.datetime.now() - lw["current_section_start"]
                    st.success(f"🟢 Şu an çalışılan: **{lw['current_section_name']}** ({str(sec_elapsed).split('.')[0]})")
                    
                    st.markdown("### Hareket Ekle")
                    current_section = lw["current_section_name"]
                    exercise_options = FULL_EXERCISE_LIST.get(current_section, ["Diğer"]) + ["Diğer"]
                    
                    selected_exercise = st.selectbox("Hareket Seç", exercise_options)
                    if selected_exercise == "Diğer":
                        selected_exercise = st.text_input("Hareket Adını Yaz")

                    if 'current_sets' not in st.session_state:
                        st.session_state.current_sets = []

                    if current_section == "Kardiyo":
                        with st.form("cardio_adder"):
                            c1, c2, c3 = st.columns(3)
                            c_dur = c1.number_input("Süre (dk)", min_value=0.0, step=1.0)
                            c_dist = c2.number_input("Mesafe (km)", min_value=0.0, step=0.1)
                            c_cal = c3.number_input("Kalori", min_value=0, step=10)
                            c4, c5 = st.columns(2)
                            c_inc = c4.number_input("Eğim", min_value=0.0, step=0.5)
                            c_spd = c5.number_input("Hız", min_value=0.0, step=0.5)
                            
                            if st.form_submit_button("Kardiyo Ekle"):
                                st.session_state.current_sets.append({
                                    "cardio_duration": c_dur,
                                    "distance": c_dist,
                                    "calories": c_cal,
                                    "incline": c_inc,
                                    "speed": c_spd
                                })
                                st.toast("Kardiyo verisi eklendi")
                    else:
                        with st.form("set_adder"):
                            c1, c2, c3 = st.columns(3)
                            s_weight = c1.number_input("Ağırlık (KG)", min_value=0.0, step=2.5)
                            s_reps = c2.number_input("Tekrar", min_value=0, step=1)
                            s_rom = c3.selectbox("ROM", ["Tam", "Yarım", "Kontrollü"])
                            c4, c5 = st.columns(2)
                            s_rpe = c4.selectbox("Zorlanma (RPE)", ["Düşük", "Orta", "Yüksek", "Tükeniş"])
                            is_drop = c5.checkbox("Bu bir Drop Set mi?")
                            
                            if st.form_submit_button("Seti Ekle"):
                                st.session_state.current_sets.append({
                                    "weight": s_weight, "reps": s_reps, 
                                    "rom": s_rom, "difficulty": s_rpe,
                                    "is_dropset": is_drop
                                })
                                st.toast("Set Eklendi")

                    if st.session_state.current_sets:
                        st.write("Eklenen Setler/Veriler:")
                        st.dataframe(pd.DataFrame(st.session_state.current_sets), use_container_width=True)

                    if st.button("✅ Hareketi Bölüme Kaydet"):
                        if selected_exercise and st.session_state.current_sets:
                            lw["exercises_temp"].append({
                                "name": selected_exercise,
                                "sets": st.session_state.current_sets
                            })
                            st.session_state.current_sets = []
                            st.success(f"{selected_exercise} kaydedildi!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Hareket adı veya veri girilmedi.")

                    if lw["exercises_temp"]:
                        with st.expander(f"Bu Bölümdeki Hareketler ({len(lw['exercises_temp'])})"):
                            for e in lw["exercises_temp"]:
                                st.write(f"- {e['name']} ({len(e['sets'])} veri)")

                    st.divider()
                    if st.button("⏹️ Bölümü Bitir ve Kaydet"):
                        end_time = datetime.datetime.now()
                        duration_mins = int((end_time - lw["current_section_start"]).total_seconds() / 60)
                        lw["sections"].append({
                            "name": lw["current_section_name"],
                            "duration": duration_mins,
                            "exercises": lw["exercises_temp"]
                        })
                        lw["current_section_start"] = None
                        lw["exercises_temp"] = []
                        st.rerun()

            st.divider()
            if lw["sections"]:
                st.subheader("Tamamlanan Bölümler")
                for s in lw["sections"]:
                    st.write(f"✔️ {s['name']} ({s['duration']} dk)")

            if st.button("🏁 İDMANI TAMAMLA VE KAYDET", type="primary"):
                total_dur = int((datetime.datetime.now() - lw["start_time"]).total_seconds() / 60)
                hardest_part = "-"
                max_difficulty = 0
                for sec in lw["sections"]:
                    diff_score = 0
                    for ex in sec['exercises']:
                        for s in ex['sets']:
                            if 'difficulty' in s and s['difficulty'] in ["Yüksek", "Tükeniş"]: 
                                diff_score += 1
                    if diff_score > max_difficulty:
                        max_difficulty = diff_score
                        hardest_part = sec['name']

                log_data = {
                    "date": datetime.datetime.now(),
                    "main_focus": lw["main_focus"],
                    "total_duration": total_dur,
                    "sections": lw["sections"],
                    "hardest_part": hardest_part,
                    "date_str": str(datetime.date.today())
                }
                save_to_db("workout_logs", log_data)
                
                st.balloons()
                st.success(f"İdman Kaydedildi! Süre: {total_dur} dk | En Zor: {hardest_part}")
                st.session_state.live_workout = {
                    "active": False, "start_time": None, "sections": [], 
                    "current_section_start": None, "exercises_temp": []
                }
                time.sleep(3)
                st.rerun()

    with tabs[2]:
        st.header("⚙️ Yeni Hareket Ekle")
        st.info("Listede olmayan hareketleri buraya ekleyerek 'Canlı İdman' modunda kullanabilirsiniz.")
        
        with st.form("add_custom_exercise"):
            ce_region = st.selectbox("Hangi Bölge?", ["Göğüs", "Sırt", "Bacak", "Omuz", "Ön Kol", "Arka Kol", "Karın", "Kardiyo"])
            ce_name = st.text_input("Hareketin Adı (Örn: Reverse Fly)")
            
            if st.form_submit_button("Hareketi Kaydet"):
                if ce_name:
                    save_to_db("custom_exercises", {"region": ce_region, "name": ce_name})
                    st.success(f"{ce_name} ({ce_region}) listeye eklendi!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Hareket ismi giriniz.")
        
        st.divider()
        st.subheader("Eklenen Özel Hareketler")
        try:
            c_docs = db.collection("custom_exercises").stream()
            c_data = [{"Bölge": doc.to_dict().get('region'), "Hareket": doc.to_dict().get('name'), "id": doc.id} for doc in c_docs]
            if c_data:
                c_df = pd.DataFrame(c_data)
                for index, row in c_df.iterrows():
                    c1, c2, c3 = st.columns([2, 4, 1])
                    c1.write(f"**{row['Bölge']}**")
                    c2.write(row['Hareket'])
                    if c3.button("Sil", key=f"del_cust_ex_{row['id']}"):
                        delete_from_db("custom_exercises", row['id'])
            else:
                st.write("Henüz özel hareket eklenmemiş.")
        except:
            st.write("Veri çekilemedi.")

# ==========================================
# MODÜL 3: ALIŞKANLIK TAKİBİ (YENİ)
# ==========================================
elif main_module == "Alışkanlık Takibi":
    st.title("🌱 Alışkanlık Takip Paneli")
    
    current_month = datetime.datetime.now().month
    current_year = datetime.datetime.now().year
    month_name = datetime.datetime.now().strftime('%B %Y')
    
    # Ay ve Yıl Bilgisi
    st.header(f"Takip Listesi: {month_name}")
    
    # 1. Alışkanlık Listesi
    habits_list = [
        "Saat 6:00'da Uyanmak", "1 Saat Ekransız Zaman Geçirmek", 
        "Sabahtan Günün Planını Yapmak", "Sabahtan Haberleri Dinlemek",
        "10 Sayfa Kitap Okumak", "4.5 Litre Su İçmek", 
        "Beslenme Düzenini Tam Takip Etmek", "Antrenman Düzenini Tam Takip Etmek",
        "Kişisel Hedef ve İş Hedeflerini Düzenlemek", "N.F",
        "Sosyal Medya Zamanını 1 Saatin Altında Tutmak", "Her Sabah Tartılmak"
    ]
    
    # 2. Uyku Listesi
    sleep_list = ["8 Saat", "7 Saat", "6 Saat", "5 Saat", "4 Saat", "3 Saat", "2 Saat", "1 Saat", "1 Saatten Az"]
    
    # Ayın günleri
    days_in_month = calendar.monthrange(current_year, current_month)[1]
    cols = [str(d) for d in range(1, days_in_month + 1)]
    
    # Veritabanından Veri Çekme
    current_data = get_monthly_habit_data(current_year, current_month)
    db_habits = current_data.get("habits", {})
    db_sleep = current_data.get("sleep", {})
    
    # --- TABLO 1: ALIŞKANLIKLAR ---
    st.subheader("Günlük Rutin")
    habit_df = pd.DataFrame(index=habits_list, columns=cols)
    # Veritabanındaki veriyi tabloya işle
    for h in habits_list:
        if h in db_habits:
            for day_idx, val in enumerate(db_habits[h]):
                if day_idx < len(cols):
                    habit_df.iat[habits_list.index(h), day_idx] = val
        else:
            habit_df.loc[h] = False # Varsayılan False

    edited_habits = st.data_editor(habit_df, use_container_width=True, key="habit_editor")
    
    st.divider()
    
    # --- TABLO 2: UYKU SÜRESİ ---
    st.subheader("Uyku Süresi / Gün")
    sleep_df = pd.DataFrame(index=sleep_list, columns=cols)
    # Veritabanındaki veriyi tabloya işle
    for s in sleep_list:
        if s in db_sleep:
            for day_idx, val in enumerate(db_sleep[s]):
                if day_idx < len(cols):
                    sleep_df.iat[sleep_list.index(s), day_idx] = val
        else:
            sleep_df.loc[s] = False

    edited_sleep = st.data_editor(sleep_df, use_container_width=True, key="sleep_editor")
    
    # --- KAYDETME ---
    if st.button("Tüm Değişiklikleri Kaydet", type="primary"):
        # Dataframe'leri sözlüğe çevir (DB için)
        # Her satırı {gün_index: bool} listesine çeviriyoruz
        habits_to_save = {}
        for idx, row in edited_habits.iterrows():
            habits_to_save[idx] = row.tolist()
            
        sleep_to_save = {}
        for idx, row in edited_sleep.iterrows():
            sleep_to_save[idx] = row.tolist()
            
        update_monthly_habit_data(current_year, current_month, habits_to_save, sleep_to_save)
        st.success("Alışkanlıklar başarıyla kaydedildi!")
        time.sleep(1)
        st.rerun()

# ==========================================
# MODÜL 4: FİNANS MERKEZİ (FULL + GÜNCEL)
# ==========================================
elif main_module == "Finans Merkezi":
    st.title("💰 Finansal Yönetim Paneli")
    
    tabs = st.tabs(["📊 Genel Bakış", "💸 Harcama", "💳 Ödeme", "🤝 Borç/Alacak", "📈 Yatırım"])
    
    df_exp = get_data("expenses")
    df_pay = get_data("payments")
    df_inv = get_data("investments")
    df_debt = get_data("debts")
    df_lia = get_data("liabilities")

    # --- TAB 1: GENEL BAKIŞ ---
    with tabs[0]:
        st.header("Finansal Durum")
        c1, c2, c3 = st.columns(3)
        with c1:
            if not df_exp.empty:
                d, w, m = calculate_totals(df_exp)
                st.metric("Bu Ay Harcama", f"{m:,.2f} TL", f"Bugün: {d:,.2f} TL")
            else: st.write("-")
        with c2:
            if not df_pay.empty:
                _, _, m_pay = calculate_totals(df_pay)
                st.metric("Bu Ay Ödeme", f"{m_pay:,.2f} TL")
            else: st.write("-")
        with c3:
            total_liabilities = 0
            if not df_lia.empty:
                total_liabilities = pd.to_numeric(df_lia['remaining_amount'], errors='coerce').sum()
            st.metric("Toplam Sabit Borç", f"{total_liabilities:,.2f} TL")
        
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
        
        with st.form("expense_input_form", clear_on_submit=True):
            st.subheader("Yeni Harcama")
            c1, c2, c3 = st.columns(3)
            date_in = c1.date_input("Tarih", datetime.date.today())
            place_in = c2.text_input("Yer")
            amount_in = c3.number_input("Tutar (TL)", min_value=0.0, step=10.0)
            
            c4, c5, c6 = st.columns(3)
            cat_in = c4.selectbox("Tür", ["Market", "Yiyecek", "İçecek", "Ulaşım", "Eğlence", "Kasap", "Supplement", "Yatırım", "MISIR Seyahat Harcaması", "Diğer"])
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
            cols = ['Sil', 'date_str', 'place', 'amount', 'category', 'method', 'necessity', 'desc', 'id']
            for col in cols:
                if col not in df_exp.columns and col != 'Sil': df_exp[col] = None
            
            clean_df = df_exp[cols].copy()
            clean_df['Sil'] = clean_df['Sil'].astype(bool)
            clean_df['date_str'] = pd.to_datetime(clean_df['date_str'], errors='coerce').dt.date
            clean_df['place'] = clean_df['place'].astype(str)
            clean_df['amount'] = pd.to_numeric(clean_df['amount'], errors='coerce').fillna(0.0)
            clean_df['category'] = clean_df['category'].astype(str)
            clean_df['method'] = clean_df['method'].astype(str)
            clean_df['necessity'] = clean_df['necessity'].astype(str)
            clean_df['desc'] = clean_df['desc'].astype(str)
            
            edited_df = st.data_editor(
                clean_df,
                column_config={
                    "Sil": st.column_config.CheckboxColumn(default=False, width="small"),
                    "date_str": st.column_config.DateColumn("Tarih", format="YYYY-MM-DD"),
                    "place": "Yer",
                    "amount": st.column_config.NumberColumn("Tutar", format="%.2f TL"),
                    "category": st.column_config.SelectboxColumn("Kategori", options=["Market", "Yiyecek", "İçecek", "Ulaşım", "Eğlence", "Kasap", "Supplement", "Yatırım", "MISIR Seyahat Harcaması", "Diğer"]),
                    "method": "Ödeme Şekli",
                    "necessity": st.column_config.SelectboxColumn("Gerekli?", options=["Evet", "Hayır"]),
                    "desc": "Açıklama",
                    "id": None 
                },
                hide_index=True,
                num_rows="dynamic",
                key="exp_editor"
            )

            to_delete = edited_df[edited_df['Sil'] == True]['id'].tolist()
            if to_delete:
                if st.button(f"Seçili {len(to_delete)} Harcamayı Sil", type="primary"):
                    delete_multiple_docs("expenses", to_delete)
            
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
                    else:
                         save_to_db("expenses", {
                            "date": datetime.datetime.combine(row['date_str'], datetime.time.min) if row['date_str'] else datetime.datetime.now(),
                            "place": str(row['place']),
                            "amount": float(row['amount']),
                            "category": str(row['category']),
                            "method": str(row['method']),
                            "necessity": str(row['necessity']),
                            "desc": str(row['desc'])
                        })
                st.success("Güncellendi!")
                time.sleep(1)
                st.rerun()

    # --- TAB 3: ÖDEME ---
    with tabs[2]:
        st.header("Ödeme Takibi")
        
        liability_options = {"Yok": None}
        if not df_lia.empty:
            for idx, row in df_lia.iterrows():
                label = f"{row['name']} (Kalan: {row['remaining_amount']:.2f} TL)"
                liability_options[label] = row['id']

        with st.form("payment_input_form", clear_on_submit=True):
            st.subheader("Ödeme Ekle")
            c1, c2, c3 = st.columns(3)
            p_date = c1.date_input("Tarih")
            p_amount = c2.number_input("Tutar", min_value=0.0, step=10.0)
            p_place = c3.text_input("Ödeme Yapılan Kurum")
            
            c4, c5 = st.columns(2)
            p_type = c4.selectbox("Tür", ["Kredi Kartı Borcu", "Fatura", "Kredi", "Diğer"])
            p_acc = c5.text_input("Ödeme Aracı", value="Maaş Kartı")
            
            p_link = st.selectbox("Bu Ödeme Hangi Borçtan Düşülsün?", list(liability_options.keys()))
            p_desc = st.text_area("Açıklama")
            
            if st.form_submit_button("Ödemeyi Kaydet"):
                save_to_db("payments", {
                    "date": datetime.datetime.combine(p_date, datetime.time.min),
                    "amount": p_amount, "category": p_type, 
                    "place": p_place, "account": p_acc, "desc": p_desc
                })
                
                selected_lia_id = liability_options[p_link]
                if selected_lia_id:
                    update_liability_balance(selected_lia_id, p_amount)
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

            edited_df_p = st.data_editor(
                clean_df_p,
                column_config={
                    "Sil": st.column_config.CheckboxColumn(default=False),
                    "date_str": st.column_config.DateColumn("Tarih"),
                    "amount": st.column_config.NumberColumn("Tutar", format="%.2f TL"),
                    "place": "Ödeme Yapılan Kurum",
                    "account": "Ödeme Aracı",
                    "category": st.column_config.SelectboxColumn("Tür", options=["Kredi Kartı Borcu", "Fatura", "Kredi", "Diğer"]),
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
                            "place": str(row['place']), 
                            "amount": float(row['amount']), 
                            "desc": str(row['desc']),
                            "account": str(row['account']),
                            "category": str(row['category']),
                            "date": datetime.datetime.combine(row['date_str'], datetime.time.min) if row['date_str'] else None,
                            "date_str": str(row['date_str'])
                        })
                    else:
                        save_to_db("payments", {
                            "date": datetime.datetime.combine(row['date_str'], datetime.time.min) if row['date_str'] else datetime.datetime.now(),
                            "amount": float(row['amount']), 
                            "category": str(row['category']), 
                            "place": str(row['place']), 
                            "account": str(row['account']), 
                            "desc": str(row['desc'])
                        })
                st.success("Güncellendi!")
                time.sleep(1)
                st.rerun()

    # --- TAB 4: BORÇ / ALACAK ---
    with tabs[3]:
        st.header("Borç Defteri")
        
        st.subheader("🏦 Kalan Sabit Borç Bakiyeleri (Kredi, KYK vb.)")
        
        with st.form("liability_form", clear_on_submit=True):
            l1, l2 = st.columns(2)
            l_name = l1.text_input("Borç Adı (Örn: KYK, Garanti Kredi)")
            l_amount = l2.number_input("Kalan Toplam Tutar", min_value=0.0)
            if st.form_submit_button("Borç Hesabı Ekle"):
                save_to_db("liabilities", {"name": l_name, "remaining_amount": l_amount})
                st.rerun()
        
        if not df_lia.empty:
            cols_l = ['Sil', 'name', 'remaining_amount', 'id']
            for col in cols_l:
                if col not in df_lia.columns and col != 'Sil': df_lia[col] = None
            
            clean_df_l = df_lia[cols_l].copy()
            clean_df_l['Sil'] = clean_df_l['Sil'].astype(bool)
            clean_df_l['name'] = clean_df_l['name'].astype(str)
            clean_df_l['remaining_amount'] = pd.to_numeric(clean_df_l['remaining_amount'], errors='coerce').fillna(0.0)
            
            edited_lia = st.data_editor(
                clean_df_l,
                column_config={
                    "Sil": st.column_config.CheckboxColumn(default=False),
                    "name": "Borç Adı",
                    "remaining_amount": st.column_config.NumberColumn("Kalan Bakiye", format="%.2f TL"),
                    "id": None
                },
                hide_index=True,
                key="lia_editor"
            )
            
            to_del_l = edited_lia[edited_lia['Sil'] == True]['id'].tolist()
            if to_del_l:
                if st.button(f"Seçili Borç Hesabını Sil"):
                    delete_multiple_docs("liabilities", to_del_l)

        st.divider()
        st.subheader("🤝 Şahıs Borç/Alacak Kayıtları")
        debt_mode = st.radio("Yön", ["Verdim (Alacak)", "Aldım (Borç)"], horizontal=True)
        
        with st.form("debt_input_form", clear_on_submit=True):
            d1, d2, d3 = st.columns(3)
            d_person = d1.text_input("Kişi")
            d_amount = d2.number_input("Miktar", min_value=0.0)
            d_curr = d3.selectbox("Birim", ["TL", "USD", "EUR", "Altın"])
            
            d4, d5 = st.columns(2)
            d_date = d4.date_input("Verilme Tarihi")
            d_due = d5.date_input("Vade Tarihi")
            
            if st.form_submit_button("Kayıt Ekle"):
                save_to_db("debts", {
                    "type": "Alacak" if "Verdim" in debt_mode else "Borç",
                    "person": d_person, "amount": d_amount, "currency": d_curr,
                    "date": datetime.datetime.combine(d_date, datetime.time.min),
                    "due_date": datetime.datetime.combine(d_due, datetime.time.min),
                    "status": "Aktif"
                })
                st.rerun()

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
