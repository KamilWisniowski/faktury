import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import os
import time
from datetime import datetime

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="AI Księgowy - Masowy", layout="wide")

# --- KONFIGURACJA AI ---
api_key = st.secrets.get("GOOGLE_API_KEY", None)

# Funkcja analizy (bez zmian, tylko drobne usprawnienie błędów)
def analyze_invoice(image):
    if not api_key:
        return None
    
    # Używamy modelu, który u Ciebie zadziałał
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash') 

    prompt = """
    Jesteś asystentem księgowym. Przeanalizuj ten obraz faktury.
    Wyciągnij następujące dane i zwróć je TYLKO w formacie JSON (bez markdown):
    1. 'sprzedawca': pełna nazwa firmy sprzedającej.
    2. 'data_wystawienia': data w formacie YYYY-MM-DD.
    3. 'kwota_brutto': łączna kwota do zapłaty (jako liczba, kropka jako separator dziesiętny).
    
    Jeśli nie możesz znaleźć danej informacji, wpisz null.
    """
    
    try:
        response = model.generate_content([prompt, image])
        text_response = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text_response)
    except Exception as e:
        # Zwracamy pusty słownik w razie błędu, żeby nie wysypać całej pętli
        return {"sprzedawca": "BŁĄD ODCZYTU", "data_wystawienia": "", "kwota_brutto": 0.0}

# --- INTERFEJS UŻYTKOWNIKA ---
st.title("📄 Masowy Rejestr Faktur")
st.markdown("Wgraj jedną lub wiele faktur naraz. AI przetworzy je kolejno.")

# API Key w sidebarze (jeśli nie ma w secrets)
if not api_key:
    temp_key = st.sidebar.text_input("Podaj klucz Google API", type="password")
    if temp_key:
        os.environ["GOOGLE_API_KEY"] = temp_key
        api_key = temp_key
    else:
        st.warning("Musisz podać klucz API.")
        st.stop()

# Inicjalizacja stanu (żeby dane nie znikały po kliknięciu)
if 'analysed_data' not in st.session_state:
    st.session_state['analysed_data'] = pd.DataFrame(columns=["Sprzedawca", "Data wystawienia", "Kwota"])

# 1. Okno uploadu (accept_multiple_files=True)
uploaded_files = st.file_uploader("Wybierz pliki faktur (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

# Przycisk startu analizy
if uploaded_files:
    if st.button(f"🚀 Przeanalizuj {len(uploaded_files)} faktur"):
        
        progress_bar = st.progress(0)
        results = []
        
        for i, file in enumerate(uploaded_files):
            # Otwórz obraz
            image = Image.open(file)
            
            # Zapytaj AI
            data = analyze_invoice(image)
            
            if data:
                # Dodajemy wynik do listy
                results.append({
                    "Nazwa pliku": file.name,
                    "Sprzedawca": data.get('sprzedawca'),
                    "Data wystawienia": data.get('data_wystawienia'),
                    "Kwota": float(data.get('kwota_brutto', 0.0) or 0.0) # Zabezpieczenie przed None
                })
            
            # Aktualizacja paska postępu
            progress_bar.progress((i + 1) / len(uploaded_files))
            # Mała przerwa, żeby nie "zajechać" API (Rate Limit)
            time.sleep(1) 
            
        st.session_state['analysed_data'] = pd.DataFrame(results)
        st.success("Analiza zakończona! Sprawdź tabelę poniżej.")

# 2. Edycja i Zapis
if not st.session_state['analysed_data'].empty:
    st.divider()
    st.subheader("✏️ Zweryfikuj dane przed zapisem")
    st.info("Możesz klikać w komórki tabeli i poprawiać dane ręcznie.")
    
    # Wyświetlamy edytowalną tabelę (Data Editor)
    edited_df = st.data_editor(st.session_state['analysed_data'], num_rows="dynamic", use_container_width=True)
    
    # Przycisk zapisu
    if st.button("💾 Zapisz wszystko do Bazy CSV"):
        # Dodajemy datę dodania rekordu
        edited_df["Data dodania"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        csv_file = 'baza_faktur.csv'
        if os.path.exists(csv_file):
            old_df = pd.read_csv(csv_file)
            final_df = pd.concat([old_df, edited_df], ignore_index=True)
        else:
            final_df = edited_df
            
        final_df.to_csv(csv_file, index=False)
        st.toast(f"Zapisano {len(edited_df)} faktur!", icon="✅")
        
        # Opcjonalnie: wyczyść widok po zapisie
        # st.session_state['analysed_data'] = pd.DataFrame() 
        # st.rerun()

# --- WIDOK ISTNIEJĄCEJ BAZY ---
st.divider()
st.subheader("📂 Historia (Baza Danych)")
if os.path.exists('baza_faktur.csv'):
    df_history = pd.read_csv('baza_faktur.csv')
    # Sortowanie od najnowszych
    if "Data dodania" in df_history.columns:
        df_history = df_history.sort_values(by="Data dodania", ascending=False)
        
    st.dataframe(df_history, use_container_width=True)
else:
    st.text("Baza jest jeszcze pusta.")
