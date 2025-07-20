import streamlit as st
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import pandas as pd

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(
    page_title="Valutazione Aziendale da XBRL",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.title("📊 Valutazione Aziendale - Estrazione dati da file XBRL")
st.markdown("Carica il file .xbrl per ottenere i dati di base per la valutazione dell'azienda.")

# --- FUNZIONI HELPER ---

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


# --- FUNZIONE DI ESTRAZIONE DATI RIVISTA E POTENZIATA ---
def estrai_dati_xbrl(file):
    """
    Estrae i dati principali da un file XBRL in modo robusto, identificando prima
    il contesto temporale corretto e poi estraendo i dati associati a quel contesto.
    """
    try:
        file.seek(0)
        tree = ET.parse(file)
        root = tree.getroot()

        # 1. Mappare i contesti temporali (contextRef) alle loro date di fine
        contesti = {}
        # Usiamo il wildcard {*} per la massima compatibilità con i namespace
        for context in root.findall('.//{*}context'):
            context_id = context.get('id')
            end_date_element = context.find('.//{*}endDate')
            if context_id and end_date_element is not None and end_date_element.text:
                try:
                    # Memorizza la data come oggetto datetime per un facile confronto
                    contesti[context_id] = datetime.strptime(end_date_element.text.strip(), '%Y-%m-%d')
                except ValueError:
                    continue # Ignora contesti con formati data non validi

        if not contesti:
            st.error("❌ Impossibile trovare contesti temporali validi nel file XBRL.")
            return None

        # 2. Identificare il contesto dell'anno più recente (il bilancio corrente)
        context_recente_id = max(contesti, key=contesti.get)
        anno_riferimento = contesti[context_recente_id].year

        # 3. Funzione helper per estrarre un valore dato un elenco di tag e un contesto
        def trova_valore_nel_contesto(possibili_tag, context_id):
            for tag in possibili_tag:
                # Query XPath che cerca il tag E il suo specifico contextRef
                xpath_query = f".//{{*}}{tag}[@contextRef='{context_id}']"
                elemento = root.find(xpath_query)
                if elemento is not None and elemento.text and elemento.text.strip():
                    return elemento.text
            return None

        # 4. Mappatura dei tag (con più alias per maggiore compatibilità)
        tag_mapping = {
            'ricavi': ['ValoreProduzioneRicaviVenditePrestazioni', 'RicaviDelleVenditeEDellePrestazioni', 'itcc-ci_RicaviVenditePrestazioni'],
            'utile': ['UtilePerditaEsercizio', 'PatrimonioNettoUtilePerditaEsercizio', 'itcc-ci_UtilePerditaEsercizio'],
            'attivo': ['TotaleAttivo', 'AttivoTotaleStatoPatrimoniale', 'itcc-sp-a_TotaleAttivo'],
            'patrimonio_netto': ['TotalePatrimonioNetto', 'PatrimonioNetto', 'itcc-sp-p_PatrimonioNetto'],
            'debiti_breve': ['DebitiDebitiVersoBancheEsigibiliEntroEsercizioSuccessivo', 'itcc-sp-p_DebitiVersoBancheEntroEsercizio'],
            'debiti_mlt': ['DebitiDebitiVersoBancheEsigibiliOltreEsercizioSuccessivo', 'itcc-sp-p_DebitiVersoBancheOltreEsercizio'],
            'denominazione': ['DatiAnagraficiDenominazione', 'Denominazione'],
            'codice_fiscale': ['DatiAnagraficiCodiceFiscale', 'CodiceFiscale']
        }
        
        # 5. Estrazione dei dati usando la nuova logica "context-aware"
        dati_estratti = {}
        for chiave, tags in tag_mapping.items():
            if 'denominazione' in chiave or 'codice_fiscale' in chiave:
                # I dati anagrafici non hanno contesto, li cerchiamo globalmente
                # Usiamo una query che cerca il primo tag disponibile dalla lista
                for tag in tags:
                    elem = root.find(f".//{{*}}{tag}")
                    if elem is not None and elem.text:
                        dati_estratti[chiave] = elem.text.strip()
                        break # Trovato, esci dal loop interno
                if chiave not in dati_estratti:
                     dati_estratti[chiave] = None # Se non trova nulla
            else:
                # Per i dati finanziari, usiamo il contesto dell'anno più recente
                valore_testo = trova_valore_nel_contesto(tags, context_recente_id)
                dati_estratti[chiave] = pulisci_valore_numerico(valore_testo)

        # 6. Preparazione del dizionario finale con calcoli aggiuntivi
        ricavi = dati_estratti.get('ricavi')
        utile = dati_estratti.get('utile')
        attivo = dati_estratti.get('attivo')
        patrimonio_netto = dati_estratti.get('patrimonio_netto')
        debiti_breve = dati_estratti.get('debiti_breve')
        debiti_mlt = dati_estratti.get('debiti_mlt')
        
        debiti_totali = None
        if debiti_breve is not None or debiti_mlt is not None:
            debiti_totali = (debiti_breve or 0) + (debiti_mlt or 0)

        roe = (utile / patrimonio_netto * 100) if utile is not None and patrimonio_netto not in [0, None] else None
        roa = (utile / attivo * 100) if utile is not None and attivo not in [0, None] else None
        debt_to_equity = (debiti_totali / patrimonio_netto) if debiti_totali is not None and patrimonio_netto not in [0, None] else None

        return {
            "denominazione": dati_estratti.get('denominazione'),
            "codice_fiscale": dati_estratti.get('codice_fiscale'),
            "anno": anno_riferimento,
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


# --- INTERFACCIA PRINCIPALE ---

# File uploader
uploaded_file = st.file_uploader(
    "📎 Carica file .xbrl",
    type=["xbrl", "xml"],
    help="Accetta file con estensione .xbrl o .xml contenenti dati XBRL"
)

if uploaded_file is not None:
    st.write("✅ File ricevuto! Inizio elaborazione...")
    
    with st.spinner("📄 Sto leggendo il bilancio e analizzando i dati..."):
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

            # Dati per export in tabella
            st.subheader("📋 Riepilogo Dati per Elaborazioni Future")
            dati_puliti = {k.replace("_", " ").title(): v for k, v in dati.items() if v is not None}
            df_dati = pd.DataFrame(dati_puliti.items(), columns=["Voce", "Valore"])
            st.dataframe(df_dati, use_container_width=True, hide_index=True)
            
            # Expander con i dati in formato JSON, come richiesto
            with st.expander("🤖 Dati formattati per GPT/LLM (formato JSON)"):
                st.json({k: v for k, v in dati.items() if v is not None})
        else:
            st.warning("⚠️ Non è stato possibile estrarre dati finanziari significativi dal file.")
            st.info("Questo può accadere se la tassonomia XBRL del file è molto diversa da quella standard italiana o se i dati sono mancanti.")
    
else:
    st.info("👆 Carica un file .xbrl per iniziare l'analisi")
