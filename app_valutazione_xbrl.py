# app_valutazione_xbrl.py
import streamlit as st
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import pandas as pd

# Configurazione pagina
st.set_page_config(
    page_title="Valutazione Aziendale da XBRL",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.title("📊 Valutazione Aziendale - Estrazione dati da file XBRL")
st.markdown("Carica il file .xbrl per ottenere i dati di base per la valutazione dell'azienda.")

# File uploader
uploaded_file = st.file_uploader(
    "📎 Carica file .xbrl",
    type=["xbrl", "xml"],
    help="Accetta file con estensione .xbrl o .xml contenenti dati XBRL"
)

def pulisci_valore_numerico(text):
    """Pulisce e converte il testo in numero, gestendo vari formati italiani."""
    if not text:
        return None
    try:
        text = str(text).strip()
        # Gestisce il formato europeo (virgola come decimale, punto come separatore migliaia)
        text = text.replace(".", "").replace(",", ".")
        text = re.sub(r'[^\d\.-]', '', text)
        return float(text) if text and text != '-' else None
    except (ValueError, AttributeError):
        return None

# --- FUNZIONE DI ESTRAZIONE DATI COMPLETAMENTE RIVISTA ---
def estrai_dati_xbrl(file):
    """
    Estrae i dati principali da un file XBRL usando XPath per una maggiore robustezza ed efficienza.
    """
    try:
        file.seek(0)
        tree = ET.parse(file)
        root = tree.getroot()

        # Funzione helper per trovare un elemento usando una lista di possibili tag
        def trova_elemento(possibili_tag):
            for tag in possibili_tag:
                # Usa una wildcard {*} per il namespace: è il modo più robusto
                xpath_query = f".//{{*}}{tag}"
                elementi = root.findall(xpath_query)
                # I file XBRL spesso contengono valori per più anni (contesti diversi).
                # Prendiamo il primo elemento che contiene un testo valido,
                # che di solito corrisponde all'anno corrente.
                for elem in elementi:
                    if elem.text and elem.text.strip():
                        return elem
            return None

        # Definisce i possibili tag per ogni dato (più robusto)
        tag_mapping = {
            'ricavi': ['ValoreProduzioneRicaviVenditePrestazioni', 'RicaviDelleVenditeEDellePrestazioni'],
            'utile': ['UtilePerditaEsercizio', 'PatrimonioNettoUtilePerditaEsercizio'],
            'attivo': ['TotaleAttivo', 'AttivoTotaleStatoPatrimoniale'],
            'patrimonio_netto': ['TotalePatrimonioNetto', 'PatrimonioNetto'],
            'debiti_breve': ['DebitiDebitiVersoBancheEsigibiliEntroEsercizioSuccessivo'],
            'debiti_mlt': ['DebitiDebitiVersoBancheEsigibiliOltreEsercizioSuccessivo'],
            'denominazione': ['DatiAnagraficiDenominazione', 'Denominazione'],
            'codice_fiscale': ['DatiAnagraficiCodiceFiscale', 'CodiceFiscale']
        }
        
        # Estrazione dei dati utilizzando la nuova funzione di ricerca
        dati_estratti = {}
        for chiave, tags in tag_mapping.items():
            elemento = trova_elemento(tags)
            if elemento is not None:
                if 'denominazione' in chiave or 'codice_fiscale' in chiave:
                    dati_estratti[chiave] = elemento.text.strip()
                else:
                    dati_estratti[chiave] = pulisci_valore_numerico(elemento.text)
            else:
                dati_estratti[chiave] = None

        # Estrazione anno di riferimento dal contesto XBRL (modo più affidabile)
        anno = None
        # Cerca il tag 'endDate' che definisce il periodo di riferimento del bilancio
        for elem in root.findall(".//{*}endDate"):
            if elem.text:
                try:
                    # Prende l'anno e lo confronta per trovare il più recente
                    anno_corrente = int(elem.text[:4])
                    if anno is None or anno_corrente > anno:
                        anno = anno_corrente
                except (ValueError, IndexError):
                    continue
        
        # Unisce i dati estratti con il dizionario finale
        ricavi = dati_estratti.get('ricavi')
        utile = dati_estratti.get('utile')
        attivo = dati_estratti.get('attivo')
        patrimonio_netto = dati_estratti.get('patrimonio_netto')
        debiti_breve = dati_estratti.get('debiti_breve')
        debiti_mlt = dati_estratti.get('debiti_mlt')
        
        # Calcolo debiti finanziari totali con gestione None
        debiti_totali = None
        if debiti_breve is not None or debiti_mlt is not None:
            debiti_totali = (debiti_breve or 0) + (debiti_mlt or 0)

        # Calcoli di indicatori aggiuntivi
        roe = (utile / patrimonio_netto * 100) if utile is not None and patrimonio_netto not in [0, None] else None
        roa = (utile / attivo * 100) if utile is not None and attivo not in [0, None] else None
        debt_to_equity = (debiti_totali / patrimonio_netto) if debiti_totali is not None and patrimonio_netto not in [0, None] else None

        return {
            "denominazione": dati_estratti.get('denominazione'),
            "codice_fiscale": dati_estratti.get('codice_fiscale'),
            "anno": anno,
            "ricavi": ricavi,
            "utile_netto": utile,
            "attivo": attivo,
            "patrimonio_netto": patrimonio_netto,
            "debiti_finanziari_breve": debiti_breve,
            "debiti_finanziari_medio_lungo": debiti_mlt,
            "debiti_finanziari_totale": debiti_totali,
            "roe_percentuale": roe,
            "roa_percentuale": roa,
            "debt_to_equity_ratio": debt_to_equity
        }

    except ET.ParseError as e:
        st.error(f"❌ Errore nel parsing del file XML/XBRL. Il file potrebbe essere corrotto o non valido. Dettagli: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Si è verificato un errore imprevisto durante l'elaborazione: {e}")
        return None

def formatta_valore_monetario(valore):
    """Formatta un valore monetario per la visualizzazione."""
    if valore is None:
        return "N/D"
    return f"€ {valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatta_percentuale(valore):
    """Formatta una percentuale per la visualizzazione."""
    if valore is None:
        return "N/D"
    return f"{valore:.2f}%"

# --- INTERFACCIA PRINCIPALE (con logica di visualizzazione migliorata) ---
if uploaded_file is not None:
    st.write("✅ File ricevuto! Inizio elaborazione...")
    
    with st.spinner("📄 Sto leggendo il bilancio..."):
        dati = estrai_dati_xbrl(uploaded_file)
    
    if dati:
        # Controlliamo se abbiamo estratto almeno un dato numerico fondamentale
        dati_numerici = [dati.get(k) for k in ['ricavi', 'utile_netto', 'attivo', 'patrimonio_netto']]
        if any(d is not None for d in dati_numerici):
            st.success("✅ Dati estratti con successo!")
            
            # Visualizzazione dati aziendali
            st.subheader("🏢 Informazioni Aziendali")
            col1, col2 = st.columns(2)
            col1.metric("Denominazione", dati.get('denominazione', 'N/D'))
            col2.metric("Anno di riferimento", str(dati.get('anno', 'N/D')))
            if dati.get('codice_fiscale'):
                st.metric("Codice Fiscale", dati['codice_fiscale'])

            # Dati Finanziari
            st.subheader("💰 Dati Finanziari Principali")
            col1, col2, col3 = st.columns(3)
            col1.metric("Ricavi", formatta_valore_monetario(dati.get('ricavi')))
            col1.metric("Utile Netto", formatta_valore_monetario(dati.get('utile_netto')))
            col2.metric("Totale Attivo", formatta_valore_monetario(dati.get('attivo')))
            col2.metric("Patrimonio Netto", formatta_valore_monetario(dati.get('patrimonio_netto')))
            col3.metric("Debiti Finanziari Totali", formatta_valore_monetario(dati.get('debiti_finanziari_totale')))
            
            # Indicatori
            st.subheader("📈 Indicatori di Performance")
            col1, col2, col3 = st.columns(3)
            col1.metric("ROE", formatta_percentuale(dati.get('roe_percentuale')), help="Return on Equity - Redditività del capitale proprio")
            col2.metric("ROA", formatta_percentuale(dati.get('roa_percentuale')), help="Return on Assets - Redditività degli asset")
            debt_ratio = dati.get('debt_to_equity_ratio')
            col3.metric("Debt/Equity", f"{debt_ratio:.2f}" if debt_ratio is not None else "N/D", help="Rapporto tra debiti finanziari e patrimonio netto")

            # Dati per export
            st.subheader("📋 Riepilogo Dati per Elaborazioni Future")
            dati_puliti = {k.replace("_", " ").title(): v for k, v in dati.items() if v is not None}
            df_dati = pd.DataFrame(dati_puliti.items(), columns=["Voce", "Valore"])
            st.dataframe(df_dati, use_container_width=True, hide_index=True)
            
            with st.expander("🤖 Dati formattati per GPT/LLM (formato JSON)"):
                st.json({k: v for k, v in dati.items() if v is not None})
        else:
            st.warning("⚠️ Non è stato possibile estrarre dati finanziari significativi dal file.")
            st.info("Questo può accadere se la tassonomia XBRL del file è molto diversa da quella standard italiana o se i dati sono mancanti.")
    # La gestione dell'errore è già dentro estrai_dati_xbrl, quindi non serve un else qui

else:
    st.info("👆 Carica un file .xbrl per iniziare l'analisi")
