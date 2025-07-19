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

# File uploader con validazione più specifica
uploaded_file = st.file_uploader(
    "📎 Carica file .xbrl", 
    type=["xbrl", "xml"],
    help="Accetta file con estensione .xbrl o .xml contenenti dati XBRL"
)

def pulisci_valore_numerico(text):
    """
    Pulisce e converte il testo in numero, gestendo vari formati.
    """
    if not text:
        return None
    
    try:
        # Rimuove spazi e caratteri non numerici tranne punto, virgola e segno meno
        text = str(text).strip()
        # Gestisce il formato europeo (virgola come decimale)
        text = text.replace(".", "").replace(",", ".")
        # Rimuove eventuali caratteri non numerici rimanenti
        text = re.sub(r'[^\d\.-]', '', text)
        return float(text) if text else None
    except (ValueError, AttributeError):
        return None

def estrai_dati_xbrl(file):
    """
    Estrae i dati principali da un file XBRL con gestione migliorata degli errori
    e ricerca più robusta degli elementi.
    """
    try:
        # Reset del puntatore del file
        file.seek(0)
        tree = ET.parse(file)
        root = tree.getroot()
        
        # Definisce i namespace comuni per XBRL italiani
        namespaces = {}
        for event, elem in ET.iterparse(file, events=['start-ns']):
            prefix, uri = event
            if prefix:
                namespaces[prefix] = uri
        
        # Reset per il parsing
        file.seek(0)
        tree = ET.parse(file)
        root = tree.getroot()

        def trova_valore_con_namespace(possibili_tag):
            """
            Cerca un valore usando multiple possibilità di tag e namespace.
            """
            for tag_pattern in possibili_tag:
                # Cerca prima con il tag esatto
                for elem in root.iter():
                    if elem.tag.endswith(tag_pattern) or tag_pattern in elem.tag:
                        valore = pulisci_valore_numerico(elem.text)
                        if valore is not None:
                            return valore
            return None

        def trova_testo_con_namespace(possibili_tag):
            """
            Cerca un testo usando multiple possibilità di tag.
            """
            for tag_pattern in possibili_tag:
                for elem in root.iter():
                    if elem.tag.endswith(tag_pattern) or tag_pattern in elem.tag:
                        if elem.text and elem.text.strip():
                            return elem.text.strip()
            return None

        # Definisce i possibili tag per ogni dato (più robusto)
        tag_mapping = {
            'ricavi': [
                'ValoreProduzioneRicaviVenditePrestazioni',
                'RicaviVenditePrestazioniValoreProduzioneAnno',
                'RicaviVendite',
                'Ricavi'
            ],
            'utile': [
                'PatrimonioNettoUtilePerditaEsercizio',
                'UtilePerditaEsercizio',
                'RisultatoEsercizio',
                'UtileNetto'
            ],
            'attivo': [
                'TotaleAttivo',
                'AttivoTotale',
                'TotaleStato',
                'Attivo'
            ],
            'patrimonio_netto': [
                'TotalePatrimonioNetto',
                'PatrimonioNettoTotale',
                'PatrimonioNetto'
            ],
            'debiti_breve': [
                'DebitiDebitiVersoBancheEsigibiliEntroEsercizioSuccessivo',
                'DebitiBancariBreveTermine',
                'DebitiFinanziariBreve'
            ],
            'debiti_mlt': [
                'DebitiDebitiVersoBancheEsigibiliOltreEsercizioSuccessivo',
                'DebitiBancariMedioLungoTermine',
                'DebitiFinanziariMedioLungo'
            ],
            'denominazione': [
                'DatiAnagraficiDenominazione',
                'Denominazione',
                'RagioneSociale'
            ],
            'codice_fiscale': [
                'DatiAnagraficiCodiceFiscale',
                'CodiceFiscale',
                'CF'
            ]
        }

        # Estrazione dati usando i mapping
        ricavi = trova_valore_con_namespace(tag_mapping['ricavi'])
        utile = trova_valore_con_namespace(tag_mapping['utile'])
        attivo = trova_valore_con_namespace(tag_mapping['attivo'])
        patrimonio_netto = trova_valore_con_namespace(tag_mapping['patrimonio_netto'])
        debiti_breve = trova_valore_con_namespace(tag_mapping['debiti_breve'])
        debiti_mlt = trova_valore_con_namespace(tag_mapping['debiti_mlt'])
        
        denominazione = trova_testo_con_namespace(tag_mapping['denominazione'])
        codice_fiscale = trova_testo_con_namespace(tag_mapping['codice_fiscale'])

        # Estrazione anno con logica migliorata
        anno = None
        for elem in root.iter():
            # Cerca negli attributi instant o endDate
            if 'instant' in elem.attrib:
                try:
                    anno = int(elem.attrib['instant'][:4])
                    break
                except:
                    pass
            elif 'endDate' in elem.attrib:
                try:
                    anno = int(elem.attrib['endDate'][:4])
                    break
                except:
                    pass
            # Cerca nel testo degli elementi che finiscono con instant o date
            elif elem.tag.endswith('instant') or elem.tag.endswith('endDate'):
                try:
                    if elem.text:
                        anno = int(elem.text[:4])
                        break
                except:
                    continue

        # Calcolo debiti finanziari totali con gestione None
        debiti_totali = None
        if debiti_breve is not None or debiti_mlt is not None:
            debiti_totali = (debiti_breve or 0) + (debiti_mlt or 0)

        # Calcoli di indicatori aggiuntivi
        roe = None
        roa = None
        debt_to_equity = None
        
        if utile is not None and patrimonio_netto is not None and patrimonio_netto != 0:
            roe = (utile / patrimonio_netto) * 100
            
        if utile is not None and attivo is not None and attivo != 0:
            roa = (utile / attivo) * 100
            
        if debiti_totali is not None and patrimonio_netto is not None and patrimonio_netto != 0:
            debt_to_equity = debiti_totali / patrimonio_netto

        return {
            "denominazione": denominazione,
            "codice_fiscale": codice_fiscale,
            "anno": anno,
            "ricavi": ricavi,
            "utile_netto": utile,
            "attivo": attivo,
            "patrimonio_netto": patrimonio_netto,
            "debiti_finanziari_breve": debiti_breve,
            "debiti_finanziari_medio_lungo": debiti_mlt,
            "debiti_finanziari_totale": debiti_totali,
            # Indicatori calcolati
            "roe_percentuale": roe,
            "roa_percentuale": roa,
            "debt_to_equity_ratio": debt_to_equity
        }

    except ET.ParseError as e:
        st.error(f"❌ Errore nel parsing XML: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Errore durante l'elaborazione del file: {e}")
        return None

def formatta_valore_monetario(valore):
    """
    Formatta un valore monetario per la visualizzazione.
    """
    if valore is None:
        return "N/D"
    
    if abs(valore) >= 1_000_000:
        return f"€ {valore/1_000_000:.2f}M"
    elif abs(valore) >= 1_000:
        return f"€ {valore/1_000:.1f}K"
    else:
        return f"€ {valore:,.2f}"

def formatta_percentuale(valore):
    """
    Formatta una percentuale per la visualizzazione.
    """
    if valore is None:
        return "N/D"
    return f"{valore:.2f}%"

# Interfaccia principale
if uploaded_file:
    with st.spinner("📄 Elaborazione del file in corso..."):
        dati = estrai_dati_xbrl(uploaded_file)
    
    if dati and any(v is not None for k, v in dati.items() if k not in ['denominazione', 'codice_fiscale']):
        st.success("✅ Dati estratti correttamente!")
        
        # Visualizzazione dati aziendali
        st.subheader("🏢 Informazioni Aziendali")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Denominazione", dati.get('denominazione', 'N/D'))
        with col2:
            st.metric("Anno di riferimento", dati.get('anno', 'N/D'))
        
        if dati.get('codice_fiscale'):
            st.metric("Codice Fiscale", dati['codice_fiscale'])

        # Visualizzazione dati finanziari
        st.subheader("💰 Dati Finanziari Principali")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Ricavi", 
                formatta_valore_monetario(dati.get('ricavi'))
            )
            st.metric(
                "Utile Netto", 
                formatta_valore_monetario(dati.get('utile_netto'))
            )
        
        with col2:
            st.metric(
                "Totale Attivo", 
                formatta_valore_monetario(dati.get('attivo'))
            )
            st.metric(
                "Patrimonio Netto", 
                formatta_valore_monetario(dati.get('patrimonio_netto'))
            )
        
        with col3:
            st.metric(
                "Debiti Finanziari Totali", 
                formatta_valore_monetario(dati.get('debiti_finanziari_totale'))
            )

        # Indicatori di performance
        if any(dati.get(k) is not None for k in ['roe_percentuale', 'roa_percentuale', 'debt_to_equity_ratio']):
            st.subheader("📈 Indicatori di Performance")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                roe = dati.get('roe_percentuale')
                st.metric(
                    "ROE", 
                    formatta_percentuale(roe),
                    help="Return on Equity - Redditività del capitale proprio"
                )
            
            with col2:
                roa = dati.get('roa_percentuale')
                st.metric(
                    "ROA", 
                    formatta_percentuale(roa),
                    help="Return on Assets - Redditività degli asset"
                )
            
            with col3:
                debt_ratio = dati.get('debt_to_equity_ratio')
                if debt_ratio is not None:
                    st.metric(
                        "Debt/Equity", 
                        f"{debt_ratio:.2f}",
                        help="Rapporto tra debiti finanziari e patrimonio netto"
                    )

        # Dati per export
        st.subheader("📋 Dati per Elaborazione")
        
        # Creazione DataFrame per visualizzazione tabellare
        df_dati = pd.DataFrame([
            {"Voce": k.replace("_", " ").title(), "Valore": v} 
            for k, v in dati.items() 
            if v is not None
        ])
        
        st.dataframe(df_dati, use_container_width=True)
        
        # Export per GPT
        with st.expander("🤖 Dati formattati per GPT/LLM"):
            st.markdown("**Copia il seguente blocco per il tuo assistente AI:**")
            st.code(str(dati), language="python")
            
            # JSON formattato
            st.markdown("**Formato JSON:**")
            st.json(dati)

    else:
        st.warning("⚠️ Nessun dato utile estratto dal file. Possibili cause:")
        st.markdown("""
        - Il file non è un XBRL valido
        - La struttura del file non corrisponde agli standard italiani
        - I tag degli elementi finanziari sono diversi da quelli attesi
        - Il file potrebbe essere corrotto
        """)
        
        # Debug info
        if st.checkbox("🔍 Mostra informazioni di debug"):
            try:
                file.seek(0)
                tree = ET.parse(uploaded_file)
                root = tree.getroot()
                
                st.write("**Namespace trovati:**")
                namespaces = {}
                file.seek(0)
                for event, elem in ET.iterparse(uploaded_file, events=['start-ns']):
                    namespaces[event[0]] = event[1]
                st.json(namespaces)
                
                st.write("**Primi 20 tag trovati:**")
                file.seek(0)
                tree = ET.parse(uploaded_file)
                root = tree.getroot()
                tags = [elem.tag for elem in root.iter()][:20]
                st.write(tags)
                
            except Exception as e:
                st.error(f"Errore nel debug: {e}")

else:
    st.info("👆 Carica un file .xbrl per iniziare l'analisi")
    
    # Informazioni sui tipi di file supportati
    with st.expander("ℹ️ Informazioni sui file XBRL"):
        st.markdown("""
        **Tipi di file supportati:**
        - File .xbrl (formato standard)
        - File .xml con contenuto XBRL
        
        **Fonti comuni:**
        - Bilanci depositati al Registro Imprese
        - File scaricati da Telemaco
        - Bilanci in formato XBRL da software contabili
        
        **Dati estratti:**
        - Informazioni anagrafiche aziendali
        - Ricavi e risultato d'esercizio
        - Stato patrimoniale (attivo, patrimonio netto, debiti)
        - Indicatori di performance calcolati automaticamente
        """)
