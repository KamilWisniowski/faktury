import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import os
from datetime import datetime

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="AI Księgowy", layout="wide")

# --- KONFIGURACJA AI ---
# W wersji produkcyjnej klucz trzymamy w "Secrets", nie w kodzie!
# Instrukcja niżej wyjaśni jak to zrobić bezpiecznie.
api_key = st.secrets.get("GOOGLE_API_KEY", None)

def analyze_invoice(image):
    """Wysyła obraz do Gemini i prosi o JSON"""
    if not api_key:
        return None
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

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
        # Czyszczenie odpowiedzi z potencjalnych znaczników markdown ```json
        text_response = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text_response)
    except Exception as e:
        st.error(f"Błąd przetwarzania AI: {e}")
        return None

# --- INTERFEJS UŻYTKOWNIKA ---
st.title("📄 Inteligentny Rejestr Faktur")
st.markdown("Wgraj fakturę (JPG/PNG), a AI wyciągnie z niej dane.")

# Sekcja boczna - API Key (dla testów lokalnych)
if not api_key:
    temp_key = st.sidebar.text_input("Podaj klucz Google API", type="password")
    if temp_key:
        os.environ["GOOGLE_API_KEY"] = temp_key
        api_key = temp_key
    else:
        st.warning("Musisz podać klucz API, aby aplikacja działała.")
        st.stop()

# 1. Okno uploadu
uploaded_file = st.file_uploader("Wybierz plik faktury", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Wyświetl obraz
    image = Image.open(uploaded_file)
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.image(image, caption='Podgląd faktury', use_container_width=True)

    with col2:
        if st.button("🔍 Przeanalizuj fakturę"):
            with st.spinner('AI analizuje dokument...'):
                data = analyze_invoice(image)
                
                if data:
                    st.success("Analiza zakończona!")
                    
                    # Edycja danych przed zapisem (gdyby AI się pomyliło)
                    with st.form("edit_data"):
                        sprzedawca = st.text_input("Sprzedawca", value=data.get('sprzedawca'))
                        data_wyst = st.text_input("Data wystawienia", value=data.get('data_wystawienia'))
                        kwota = st.number_input("Kwota Brutto", value=float(data.get('kwota_brutto', 0.0)))
                        
                        submitted = st.form_submit_button("💾 Zapisz do Bazy")
                        
                        if submitted:
                            # --- ZAPIS DO BAZY (Tutaj CSV) ---
                            new_entry = {
                                "Data dodania": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "Sprzedawca": sprzedawca,
                                "Data wystawienia": data_wyst,
                                "Kwota": kwota
                            }
                            
                            # Wczytaj istniejącą bazę lub stwórz nową
                            csv_file = 'baza_faktur.csv'
                            if os.path.exists(csv_file):
                                df = pd.read_csv(csv_file)
                                df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                            else:
                                df = pd.DataFrame([new_entry])
                            
                            df.to_csv(csv_file, index=False)
                            st.toast("Faktura zapisana pomyślnie!", icon="✅")

# --- WIDOK BAZY DANYCH ---
st.divider()
st.subheader("📂 Twoja Baza Faktur")
if os.path.exists('baza_faktur.csv'):
    df = pd.read_csv('baza_faktur.csv')
    st.dataframe(df, use_container_width=True)
    
    # Przycisk pobierania Excela
    st.download_button(
        label="Pobierz dane jako CSV",
        data=df.to_csv(index=False).encode('utf-8'),
        file_name='faktury.csv',
        mime='text/csv',
    )
else:

    st.info("Baza jest pusta.")
# --- DIAGNOSTYKA (Wklej na końcu pliku app.py) ---
st.divider()
if st.button("🛠️ Pokaż dostępne modele AI"):
    try:
        genai.configure(api_key=api_key)
        st.write("Dostępne modele dla Twojego klucza:")
        for m in genai.list_models():
            # Pokaż tylko te, które potrafią generować treść
            if 'generateContent' in m.supported_generation_methods:
                st.code(m.name)
    except Exception as e:
        st.error(f"Błąd połączenia: {e}")
