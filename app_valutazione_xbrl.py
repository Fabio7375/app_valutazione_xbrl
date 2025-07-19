# app_valutazione_xbrl.py
import streamlit as st
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Valutazione Aziendale da XBRL", layout="centered")

st.title("📊 Valutazione Aziendale - Estrazione dati da file XBRL")
st.markdown("Carica il file .xbrl per ottenere i dati di base per la valutazione dell'azienda.")

uploaded_file = st.file_uploader("📎 Carica file .xbrl", type="xbrl")

def estrai_dati_xbrl(file):
    tree = ET.parse(file)
    root = tree.getroot()

    def trova_valore(tag):
        for elem in root.iter():
            if elem.tag.endswith(tag):
                try:
                    return float(elem.text.replace(",", "."))
                except:
                    continue
        return None

    def trova_testo(tag):
        for elem in root.iter():
            if elem.tag.endswith(tag):
                return elem.text
        return None

    ricavi = trova_valore('ValoreProduzioneRicaviVenditePrestazioni')
    utile = trova_valore('PatrimonioNettoUtilePerditaEsercizio')
    attivo = trova_valore('TotaleAttivo')
    pn = trova_valore('TotalePatrimonioNetto')
    deb_breve = trova_valore('DebitiDebitiVersoBancheEsigibiliEntroEsercizioSuccessivo')
    deb_mlt = trova_valore('DebitiDebitiVersoBancheEsigibiliOltreEsercizioSuccessivo')
    denominazione = trova_testo('DatiAnagraficiDenominazione')
    codice_fiscale = trova_testo('DatiAnagraficiCodiceFiscale')

    anno = None
    for elem in root.iter():
        if elem.tag.endswith("instant"):
            try:
                anno = int(elem.text[:4])
                break
            except:
                continue

    return {
        "denominazione": denominazione,
        "codice_fiscale": codice_fiscale,
        "anno": anno,
        "ricavi": ricavi,
        "utile_netto": utile,
        "attivo": attivo,
        "patrimonio_netto": pn,
        "debiti_finanziari_breve": deb_breve,
        "debiti_finanziari_medio_lungo": deb_mlt,
        "debiti_finanziari_totale": (deb_breve or 0) + (deb_mlt or 0)
    }

if uploaded_file:
    try:
        dati = estrai_dati_xbrl(uploaded_file)
        st.success("✅ Dati estratti correttamente!")
        st.json(dati)
        st.markdown("Copia il seguente blocco per il tuo GPT:")
        st.code(dati, language="python")
    except Exception as e:
        st.error(f"Errore durante l'elaborazione del file: {e}")
