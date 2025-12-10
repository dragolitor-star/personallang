import streamlit as st
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from gtts import gTTS
import io
import pandas as pd
import time

# --- 1. SAYFA VE BAŞLIK AYARLARI ---
st.set_page_config(
    page_title="My Polyglot Vocabulary", 
    page_icon="📚", 
    layout="wide"
)

st.title("🇩🇪 🇬🇧 Kişisel Kelime Deposu 🇹🇷")

# --- 2. FIREBASE BAĞLANTISI (SECRETS İLE) ---
if not firebase_admin._apps:
    try:
        # st.secrets üzerinden config'i al
        key_dict = dict(st.secrets["firebase"])
        
        # Private key satır sonlarını düzelt
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")

        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase bağlantı hatası: {e}")
        st.stop()

db = firestore.client()

# --- 3. YARDIMCI FONKSİYONLAR ---

def add_word_to_db(data):
    """Tek bir kelimeyi veritabanına ekler"""
    # Boş alanları temizle
    data = {k: v for k, v in data.items() if v is not None}
    
    # Zorunlu alan kontrolü (En azından TR ve bir yabancı dil olmalı)
    if "tr" in data and ("en" in data or "de" in data):
        data["created_at"] = firestore.SERVER_TIMESTAMP
        data["learned_count"] = 0
        db.collection("vocabulary").add(data)
        return True
    return False

def get_all_words():
    """Tüm kelimeleri çeker"""
    try:
        docs = db.collection("vocabulary").stream()
        items = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            items.append(item)
        return pd.DataFrame(items)
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return pd.DataFrame()

def speak(text, lang='en'):
    """Metni sese çevirir"""
    if text:
        try:
            tts = gTTS(text=text, lang=lang)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            st.audio(fp, format='audio/mp3')
        except Exception as e:
            st.error(f"Ses oluşturma hatası: {e}")

# --- 4. EXCEL İŞLEME MANTIĞI ---
def process_excel(file, lang_type):
    """Excel dosyasını okur ve DB formatına çevirir"""
    try:
        df = pd.read_excel(file)
        # Sütun isimlerini küçük harfe çevirip boşlukları temizleyelim (Hata payını azaltmak için)
        df.columns = df.columns.str.strip()
        
        added_count = 0
        progress_bar = st.progress(0)
        
        for index, row in df.iterrows():
            word_data = {}
            
            # --- ORTAK ALANLAR ---
            # Excel'deki "Pharase" veya "Phrase" sütununu bul
            phrase_col = next((col for col in df.columns if "pharase" in col.lower() or "phrase" in col.lower()), None)
            word_data["sentence_source"] = str(row[phrase_col]) if phrase_col and pd.notna(row[phrase_col]) else ""
            
            # Meaning 1 ve Meaning 2 birleştirme
            m1 = str(row["Meaning 1"]) if "Meaning 1" in df.columns and pd.notna(row["Meaning 1"]) else ""
            m2 = str(row["Meaning 2"]) if "Meaning 2" in df.columns and pd.notna(row["Meaning 2"]) else ""
            word_data["tr"] = f"{m1}, {m2}".strip(", ") if m2 else m1

            # --- DİLE ÖZEL ALANLAR ---
            if lang_type == "en":
                # İngilizce Excel Mantığı
                word_data["en"] = str(row["Word"]) if pd.notna(row["Word"]) else ""
                word_data["de"] = "" # Almanca boş
                word_data["type"] = "General" # Excel'de tür yoksa varsayılan
                word_data["sentence_tr"] = "" # İngilizce excelinde TR cümle yok
                
            elif lang_type == "de":
                # Almanca Excel Mantığı
                word_data["de"] = str(row["Word"]) if pd.notna(row["Word"]) else ""
                word_data["en"] = "" # İngilizce boş
                
                # Almanca Excel'inde "Meaning in Turkish" var
                tr_sent_col = next((col for col in df.columns if "turkish" in col.lower() and "meaning" in col.lower()), None)
                word_data["sentence_tr"] = str(row[tr_sent_col]) if tr_sent_col and pd.notna(row[tr_sent_col]) else ""
                
                # Artikel tespiti (Basit bir mantık)
                if str(word_data["de"]).lower().startswith("der "): word_data["type"] = "İsim (Der)"
                elif str(word_data["de"]).lower().startswith("die "): word_data["type"] = "İsim (Die)"
                elif str(word_data["de"]).lower().startswith("das "): word_data["type"] = "İsim (Das)"
                else: word_data["type"] = "General"

            # Veritabanına Ekle
            if add_word_to_db(word_data):
                added_count += 1
            
            # Progress bar güncelle
            progress_bar.progress((index + 1) / len(df))
            
        st.success(f"🎉 İşlem Tamamlandı! Toplam {added_count} kelime veritabanına eklendi.")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"Excel işlenirken hata oluştu: {e}")

# --- 5. ARAYÜZ ---

menu = ["Kelime Ekle", "Excel'den Yükle", "Kelime Listesi", "Günlük Test"]
choice = st.sidebar.selectbox("Menü", menu)

# --- A. TEK KELİME EKLEME ---
if choice == "Kelime Ekle":
    st.header("Yeni Kelime Ekle")
    col1, col2, col3 = st.columns(3)
    with col1:
        en_in = st.text_input("🇬🇧 İngilizce")
        de_in = st.text_input("🇩🇪 Almanca")
    with col2:
        tr_in = st.text_input("🇹🇷 Türkçe Karşılığı")
        type_in = st.selectbox("Tür", ["İsim", "Fiil", "Sıfat", "Zarf", "Deyim", "Diğer"])
    with col3:
        img_in = st.text_input("🖼️ Görsel Linki")
    
    st.markdown("---")
    c_s1, c_s2 = st.columns(2)
    with c_s1: sent_src = st.text_area("Örnek Cümle (Yabancı Dil)")
    with c_s2: sent_tr = st.text_area("Örnek Cümle (Türkçe)")
    
    if st.button("Kaydet", type="primary"):
        add_word_to_db({
            "en": en_in, "de": de_in, "tr": tr_in,
            "sentence_source": sent_src, "sentence_tr": sent_tr,
            "type": type_in, "img_url": img_in
        })
        st.success("Kaydedildi!")

# --- B. EXCEL YÜKLEME ---
elif choice == "Excel'den Yükle":
    st.header("📤 Toplu Kelime Yükleme")
    st.info("Excel dosyandaki sütun başlıkları: 'Word', 'Meaning 1', 'Pharase' (veya Phrase) şeklinde olmalıdır.")
    
    upload_type = st.radio("Dosya Dili Nedir?", ["🇬🇧 İngilizce Listesi", "🇩🇪 Almanca Listesi"])
    uploaded_file = st.file_uploader("Excel Dosyasını Sürükle", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        if st.button("Yüklemeyi Başlat"):
            lang_code = "en" if "İngilizce" in upload_type else "de"
            process_excel(uploaded_file, lang_code)

# --- C. LİSTELEME ---
elif choice == "Kelime Listesi":
    st.header("🗂️ Kelimelerim")
    df = get_all_words()
    if not df.empty:
        search = st.text_input("Ara...")
        if search:
            df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        
        st.dataframe(df[['en', 'de', 'tr', 'sentence_source']], use_container_width=True)
        
        st.divider()
        st.subheader("🔊 Telaffuz & Detay")
        words = df['tr'].unique().tolist()
        sel_word = st.selectbox("Detay için seç:", words)
        
        if sel_word:
            row = df[df['tr'] == sel_word].iloc[0]
            c1, c2 = st.columns([1,2])
            with c1:
                 if row.get('img_url'): st.image(row['img_url'])
            with c2:
                if row.get('en'):
                    st.write(f"🇬🇧 **{row['en']}**")
                    if st.button("Dinle (EN)", key="l_en"): speak(row['en'], 'en')
                if row.get('de'):
                    st.write(f"🇩🇪 **{row['de']}**")
                    if st.button("Dinle (DE)", key="l_de"): speak(row['de'], 'de')
                st.info(f"📝 {row.get('sentence_source')}")

# --- D. TEST ---
elif choice == "Günlük Test":
    st.header("🧠 Test Zamanı")
    if 'quiz_started' not in st.session_state:
        st.session_state.update({'quiz_started': False, 'score': 0, 'idx': 0, 'data': []})
    
    def new_quiz():
        df = get_all_words()
        if len(df) < 5: 
            st.warning("Yeterli kelime yok.")
            return
        st.session_state['data'] = df.sample(min(15, len(df))).to_dict('records')
        st.session_state.update({'quiz_started': True, 'score': 0, 'idx': 0, 'show': False})

    if not st.session_state['quiz_started']:
        if st.button("Başla"): new_quiz()
    else:
        q_data = st.session_state['data']
        idx = st.session_state['idx']
        
        if idx < len(q_data):
            q = q_data[idx]
            st.progress((idx)/len(q_data))
            st.write(f"Soru {idx+1}/{len(q_data)}")
            
            st.markdown(f"### {q.get('en') or q.get('de')}")
            
            if st.session_state.get('show'):
                st.success(f"Anlamı: **{q['tr']}**")
                st.write(f"Cümle: {q.get('sentence_source')}")
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
            st.write(f"Bitti! Skor: {st.session_state['score']}")
            if st.button("Tekrar"): new_quiz()
