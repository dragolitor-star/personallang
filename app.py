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
    data["date_str"] = str(datetime.date.today()) # Kolay sorgulama için string tarih
    db.collection(collection_name).add(data)
    st.toast(f"✅ Kayıt Başarılı: {collection_name}")

def get_data(collection_name):
    """Koleksiyondaki tüm veriyi çeker"""
    docs = db.collection(collection_name).order_by("created_at", direction=firestore.Query.DESCENDING).stream()
    items = []
    for doc in docs:
        item = doc.to_dict()
        item['id'] = doc.id
        items.append(item)
    return pd.DataFrame(items)

def delete_doc(collection_name, doc_id):
    db.collection(collection_name).document(doc_id).delete()
    st.rerun()

# --- 3. DİL MODÜLÜ FONKSİYONLARI (ESKİ KODLAR) ---
def speak(text, lang='en'):
    try:
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp, format='audio/mp3')
    except: pass

# --- 4. ARAYÜZ VE NAVİGASYON ---
st.sidebar.title("🚀 Life OS")
main_module = st.sidebar.selectbox(
    "Modül Seç", 
    ["Dil Asistanı", "Fiziksel Takip", "Kişisel Yönetim"]
)

# ==========================================
# MODÜL 1: DİL ASİSTANI (Eski Özellikler)
# ==========================================
if main_module == "Dil Asistanı":
    st.title("🇩🇪 🇬🇧 Dil Asistanı")
    lang_menu = st.sidebar.radio("İşlemler", ["Kelime Ekle", "Excel Yükle", "Kelime Listesi", "Günlük Test"])
    
    if lang_menu == "Kelime Ekle":
        c1, c2 = st.columns(2)
        en = c1.text_input("Ingilizce")
        de = c2.text_input("Almanca")
        tr = st.text_input("Türkçe")
        sent = st.text_area("Örnek Cümle")
        if st.button("Kaydet"):
            save_to_db("vocabulary", {"en": en, "de": de, "tr": tr, "sentence_source": sent})

    elif lang_menu == "Excel Yükle":
        st.info("Excel formatı: Word, Meaning 1, Phrase sütunları olmalı.")
        up_file = st.file_uploader("Excel Dosyası", type=["xlsx"])
        if up_file and st.button("Yükle"):
            df = pd.read_excel(up_file)
            # Basit excel işleme mantığı (Detaylar önceki kodda mevcuttu, özet geçiyorum)
            count = 0
            for _, row in df.iterrows():
                # Hata toleranslı basit ekleme
                try:
                    w = str(row.get('Word', ''))
                    m = str(row.get('Meaning 1', ''))
                    save_to_db("vocabulary", {"en": w, "tr": m, "source": "excel"})
                    count += 1
                except: continue
            st.success(f"{count} kelime yüklendi.")

    elif lang_menu == "Kelime Listesi":
        df = get_data("vocabulary")
        if not df.empty:
            st.dataframe(df[['en', 'de', 'tr', 'sentence_source']], use_container_width=True)
            sel = st.selectbox("Dinle", df['en'].unique())
            if st.button("🔊 Dinle"): speak(sel)

    elif lang_menu == "Günlük Test":
        st.subheader("Quiz Modu")
        if st.button("Rastgele Kelime Getir"):
            df = get_data("vocabulary")
            if not df.empty:
                word = df.sample(1).iloc[0]
                st.session_state['q_word'] = word
        
        if 'q_word' in st.session_state:
            q = st.session_state['q_word']
            st.markdown(f"## {q.get('en') or q.get('de')}")
            if st.button("Cevabı Gör"):
                st.success(f"{q.get('tr')}")

# ==========================================
# MODÜL 2: FİZİKSEL TAKİP (Spor & Sağlık)
# ==========================================
elif main_module == "Fiziksel Takip":
    st.title("💪 Fiziksel Gelişim Paneli")
    phys_menu = st.sidebar.radio("Alt Menü", ["İdman Takibi", "Ölçü Takibi", "Öğün Takibi"])

    # --- İDMAN TAKİBİ ---
    if phys_menu == "İdman Takibi":
        st.subheader("Bugünkü İdman")
        c1, c2 = st.columns(2)
        w_type = c1.selectbox("İdman Türü", ["Ağırlık (Gym)", "Kardiyo", "Yüzme", "Yoga", "Futbol"])
        duration = c2.number_input("Süre (Dakika)", 15, 180, 45)
        notes = st.text_area("Notlar (Hangi bölgeler, kaç set?)")
        
        if st.button("İdmanı Kaydet"):
            save_to_db("workouts", {"type": w_type, "duration": duration, "notes": notes})

        st.divider()
        st.subheader("İdman Geçmişi")
        df_w = get_data("workouts")
        if not df_w.empty:
            st.dataframe(df_w[['date_str', 'type', 'duration', 'notes']], use_container_width=True)

    # --- ÖLÇÜ TAKİBİ ---
    elif phys_menu == "Ölçü Takibi":
        st.subheader("Vücut Analizi")
        with st.form("body_form"):
            c1, c2, c3 = st.columns(3)
            weight = c1.number_input("Kilo (kg)", format="%.1f")
            fat = c2.number_input("Yağ Oranı (%)", format="%.1f")
            muscle = c3.number_input("Kas Oranı (%)", format="%.1f")
            submitted = st.form_submit_button("Ölçüleri Kaydet")
            if submitted:
                save_to_db("measurements", {"weight": weight, "fat": fat, "muscle": muscle})
        
        st.divider()
        df_m = get_data("measurements")
        if not df_m.empty:
            # Grafik Çizimi
            st.subheader("📉 Kilo Değişimi")
            df_m['created_at'] = pd.to_datetime(df_m['created_at'])
            df_m = df_m.sort_values('created_at')
            st.line_chart(df_m, x='created_at', y='weight')
            
            with st.expander("Tüm Ölçü Verileri"):
                st.dataframe(df_m)

    # --- ÖĞÜN TAKİBİ ---
    elif phys_menu == "Öğün Takibi":
        st.subheader("Beslenme Günlüğü")
        c1, c2 = st.columns([1, 2])
        m_type = c1.selectbox("Öğün", ["Kahvaltı", "Öğle", "Akşam", "Ara Öğün"])
        cal = c1.number_input("Tahmini Kalori", 0, 2000, 500)
        content = c2.text_area("Neler yedin?")
        
        if st.button("Öğün Ekle"):
            save_to_db("meals", {"meal": m_type, "calories": cal, "content": content})
        
        st.divider()
        df_meal = get_data("meals")
        if not df_meal.empty:
            # Bugünün toplam kalorisi
            today_str = str(datetime.date.today())
            today_cals = df_meal[df_meal['date_str'] == today_str]['calories'].sum()
            st.metric("Bugün Alınan Toplam Kalori", f"{today_cals} kcal")
            st.dataframe(df_meal[['date_str', 'meal', 'calories', 'content']])

# ==========================================
# MODÜL 3: KİŞİSEL YÖNETİM (Finans & Hayat)
# ==========================================
elif main_module == "Kişisel Yönetim":
    st.title("📅 Yaşam Yönetimi")
    life_menu = st.sidebar.radio("Alt Menü", ["Harcama Takibi", "Alışkanlıklar", "Hedefler"])

    # --- HARCAMA TAKİBİ ---
    if life_menu == "Harcama Takibi":
        st.subheader("Gider Ekle")
        c1, c2, c3 = st.columns(3)
        cat = c1.selectbox("Kategori", ["Market", "Ulaşım", "Kira/Fatura", "Eğlence", "Eğitim", "Diğer"])
        amount = c2.number_input("Tutar (TL)", 0.0, 100000.0, step=10.0)
        desc = c3.text_input("Açıklama")
        
        if st.button("Harcama Gir"):
            save_to_db("expenses", {"category": cat, "amount": amount, "desc": desc})

        st.divider()
        df_exp = get_data("expenses")
        if not df_exp.empty:
            col_chart, col_data = st.columns(2)
            with col_chart:
                st.subheader("Harcama Dağılımı")
                # Kategori bazlı gruplama
                pie_data = df_exp.groupby("category")["amount"].sum()
                fig, ax = plt.subplots()
                ax.pie(pie_data, labels=pie_data.index, autopct='%1.1f%%', startangle=90)
                st.pyplot(fig)
            with col_data:
                st.dataframe(df_exp[['date_str', 'category', 'amount', 'desc']])

    # --- ALIŞKANLIK TAKİBİ ---
    elif life_menu == "Alışkanlıklar":
        st.subheader("Zinciri Kırma! 🔗")
        habits_list = ["Kitap Okuma (20sf)", "Almanca Çalışma", "İngilizce Çalışma", "3L Su İçme", "Erken Kalkma"]
        
        selected_habit = st.selectbox("Hangi alışkanlığı tamamladın?", habits_list)
        if st.button("Tamamladım Olarak İşaretle"):
            save_to_db("habits", {"name": selected_habit, "status": "Done"})
        
        st.divider()
        df_h = get_data("habits")
        if not df_h.empty:
            st.write("Son 7 Günlük Kayıtlar:")
            st.dataframe(df_h.head(10))

    # --- HEDEF TAKİBİ ---
    elif life_menu == "Hedefler":
        st.subheader("Gelecek Hedefleri")
        with st.form("goal_form"):
            title = st.text_input("Hedef Nedir?")
            deadline = st.date_input("Son Tarih")
            submit_goal = st.form_submit_button("Hedef Ekle")
            if submit_goal:
                save_to_db("goals", {"title": title, "deadline": str(deadline), "status": "Active"})
        
        st.divider()
        df_g = get_data("goals")
        if not df_g.empty:
            for index, row in df_g.iterrows():
                # Kart görünümü
                with st.expander(f"🎯 {row['title']} (Bitiş: {row['deadline']})"):
                    st.write(f"Durum: {row['status']}")
                    if st.button("Hedefi Sil", key=row['id']):
                        delete_doc("goals", row['id'])
