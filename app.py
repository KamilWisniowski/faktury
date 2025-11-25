import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import os
import time
from datetime import datetime
from pdf2image import convert_from_bytes # Nowa biblioteka

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="AI Księgowy - PDF & Foto", layout="wide")

# --- KONFIGURACJA AI ---
api_key = st.secrets.get("GOOGLE_API_KEY", None)

def analyze_invoice(image):
    if not api_key:
        return None
    
    genai.configure(api_key=api_key)
    # Używamy sprawdzonego modelu
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
        return {"sprzedawca": "BŁĄD ODCZYTU", "data_wystawienia": str(e), "kwota_brutto": 0.0}

# --- INTERFEJS UŻYTKOWNIKA ---
st.title("📄 Masowy Rejestr Faktur (PDF + Foto)")
st.markdown("Wgraj faktury (PDF lub zdjęcia). System automatycznie je przetworzy.")

# Obsługa API Key
if not api_key:
    temp_key = st.sidebar.text_input("Podaj klucz Google API", type="password")
    if temp_key:
        os.environ["GOOGLE_API_KEY"] = temp_key
        api_key = temp_key
    else:
        st.warning("Musisz podać klucz API.")
        st.stop()

if 'analysed_data' not in st.session_state:
    st.session_state['analysed_data'] = pd.DataFrame(columns=["Nazwa pliku", "Sprzedawca", "Data wystawienia", "Kwota"])

# 1. Okno uploadu - dodano "pdf" do typów
uploaded_files = st.file_uploader(
    "Wybierz pliki", 
    type=["jpg", "jpeg", "png", "pdf"], 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button(f"🚀 Przeanalizuj {len(uploaded_files)} plików"):
        
        progress_bar = st.progress(0)
        results = []
        
        for i, file in enumerate(uploaded_files):
            try:
                # --- LOGIKA ROZPOZNAWANIA PLIKU ---
                image_to_process = None
                
                # Jeśli to PDF
                if file.type == "application/pdf":
                    # Konwertuj PDF na listę obrazów (bierzemy pierwszą stronę)
                    images = convert_from_bytes(file.read())
                    if images:
                        image_to_process = images[0] # Pierwsza strona faktury
                
                # Jeśli to Zdjęcie
                else:
                    image_to_process = Image.open(file)
                
                # --- WYSYŁKA DO AI ---
                if image_to_process:
                    data = analyze_invoice(image_to_process)
                    
                    if data:
                        results.append({
                            "Nazwa pliku": file.name,
                            "Sprzedawca": data.get('sprzedawca'),
                            "Data wystawienia": data.get('data_wystawienia'),
                            "Kwota": float(data.get('kwota_brutto', 0.0) or 0.0)
                        })
                else:
                    st.error(f"Nie udało się otworzyć pliku: {file.name}")

            except Exception as e:
                st.error(f"Błąd przy pliku {file.name}: {e}")

            # Aktualizacja paska
            progress_bar.progress((i + 1) / len(uploaded_files))
            time.sleep(1)
            
        # Zapisz wyniki do sesji
        new_results = pd.DataFrame(results)
        # Jeśli są nowe wyniki, połącz je z tymi, które już były w tabeli (opcjonalne)
        st.session_state['analysed_data'] = new_results
        
        st.success("Gotowe! Sprawdź tabelę poniżej.")

# 2. Edycja i Zapis
if not st.session_state['analysed_data'].empty:
    st.divider()
    st.subheader("✏️ Zweryfikuj dane")
    
    edited_df = st.data_editor(
        st.session_state['analysed_data'], 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Kwota": st.column_config.NumberColumn(format="%.2f zł")
        }
    )
    
    if st.button("💾 Zapisz do Bazy CSV"):
        edited_df["Data dodania"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        csv_file = 'baza_faktur.csv'
        if os.path.exists(csv_file):
            old_df = pd.read_csv(csv_file)
            final_df = pd.concat([old_df, edited_df], ignore_index=True)
        else:
            final_df = edited_df
            
        final_df.to_csv(csv_file, index=False)
        st.toast(f"Zapisano pomyślnie!", icon="✅")

# --- HISTORIA ---
st.divider()
with st.expander("📂 Pokaż historię zapisanych faktur"):
    if os.path.exists('baza_faktur.csv'):
        df_history = pd.read_csv('baza_faktur.csv')
        st.dataframe(df_history.sort_values(by="Data dodania", ascending=False), use_container_width=True)
    else:
        st.text("Brak danych.")
