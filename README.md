---
title: Smart Working Dashboard
emoji: 💼
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "4.0.0"
app_file: app.py
pinned: false
license: apache-2.0
---

# 💼 Smart Working Dashboard

Quantifica l'impatto reale del lavoro sul singolo dipendente lungo tre dimensioni: **economica**, **temporale** e **ambientale**.

## ✨ Cosa fa

La dashboard permette di confrontare tutti gli scenari possibili di smart working (da 0 a N giorni a settimana) e identificare:

- 📍 il **costo annuo netto** — la configurazione da cui lo smart working genera risparmio netto o la minor perdita economica
- ⏱️ le **ore di pendolarismo risparmiate** per anno
- 🌱 le **emissioni CO₂ evitate** per anno
- 🧠 l'**indice di remotizzabilità** della propria mansione (0–100)

## 📋 Sezioni

| Sezione | Descrizione |
|---|---|
| 💼 Profilo Lavorativo | Giorni lavorativi, policy aziendale e indice di remotizzabilità tramite 5 slider |
| 🗺️ Spostamenti | Fino a 4 tratte (andata), routing reale via OpenStreetMap o Google Maps |
| 🍽️ Ristorazione | Break, pranzo, buoni pasto e modalità di assegnazione |
| 🌍 Costi Remoto | Extra utenze e costo del pasto in casa nelle giornate da remoto |
| 📈 Risultati | Tabella scenari, riepilogo costi e analisi degli scenari (auto-aggiornamento) |
| ⚙️ Parametri | Tabella costi/consumo per mezzo e settimane lavorative annue |

## 🚗 Mezzi supportati

Auto benzina · Auto diesel · Auto GPL · Auto hybrid · Auto elettrica · Moto · Trasporto Pubblico · Monopattino · Bicicletta · Piedi

## 🗺️ Provider di routing

- **OpenStreetMap / OSRM** — gratuito, nessuna API key richiesta
- **Google Maps Directions API** — richiede API key, supporta traffico in tempo reale e orario di partenza

## 🔒 Privacy

I dati inseriti non vengono memorizzati né trasmessi a terzi. Le uniche chiamate esterne riguardano il geocoding degli indirizzi (Nominatim / Google Maps).

## 📐 Metodologia

> Questa analisi non esprime un giudizio di valore sulla presenza in ufficio o sullo smart working. L'obiettivo è esclusivamente rendere visibili i **costi nascosti del lavoro** e identificare la configurazione che **minimizza l'impatto economico personale** nel rispetto della policy aziendale.

### Indice di Remotizzabilità

Calcolato come media pesata di 5 driver:

| Driver | Peso | Direzione |
|---|---|---|
| Digital readiness | 30% | ↑ positivo |
| Autonomia operativa | 20% | ↑ positivo |
| Allineamento in presenza | 20% | ↓ limitante |
| Dipendenza hardware | 15% | ↓ limitante |
| Sincronia collaborativa | 15% | ↓ limitante |

### Calcolo costi trasporto

- **Auto e moto**: costo = distanza (km) × costo/km
- **Autobus urbano**: costo = n° biglietti × tariffa (1 biglietto ogni 100 minuti)
- **Bicicletta / Piedi**: costo = 0

## 🛠️ Stack tecnico

- [Gradio](https://gradio.app) — interfaccia web
- [Pandas](https://pandas.pydata.org) — gestione dati tabellari
- [OSRM](http://project-osrm.org) — routing OpenStreetMap
- [Nominatim](https://nominatim.org) — geocoding OpenStreetMap
- [Google Maps Directions API](https://developers.google.com/maps/documentation/directions) — routing opzionale

## 🚀 Avvio

### Da GitHub

```bash
# 1. Clona il repository
git clone https://github.com/andreacapozio/smart-working-dashboard.git
cd smart-working-dashboard

# 2. Installa le dipendenze
pip install -r requirements.txt

# 3. Avvia l'applicazione
python app.py
```

L'app si aprirà automaticamente nel browser su `http://localhost:7860`.

### Su Hugging Face Spaces

La versione pubblica è disponibile direttamente su [Hugging Face Spaces](https://huggingface.co/spaces) senza alcuna installazione.

## 📁 Struttura del progetto

```
.
├── app.py            # Applicazione principale
├── requirements.txt  # Dipendenze Python
├── README.md         # Questo file
├── LICENSE           # Licenza Apache 2.0
└── logo.png          # Logo (sidebar)
```

---

## 🔭 Sviluppi Futuri

L'applicazione può essere ulteriormente evoluta lungo diverse direttrici funzionali e analitiche. Di seguito le macro-aree di sviluppo previste:

### 🤖 Intelligenza Artificiale & Raccomandazioni

| Feature | Descrizione |
|---|---|
| **AI Insights & Sintesi** | Integrazione di moduli di intelligenza artificiale generativa per produrre insight personalizzati, sintesi automatiche e spiegazioni dei risultati. |
| **Motore di Raccomandazione** | Algoritmo per suggerire la configurazione ottimale presenza/remoto in base a costi, tempi, emissioni, policy aziendale e caratteristiche del ruolo. |
| **Ottimizzazione Percorsi** | Suggerimento di percorsi e combinazioni di trasporto ottimali per minimizzare tempi di percorrenza, costo economico o impatto ambientale. |

### 👥 Analisi Organizzativa e Supporto HR

| Feature | Descrizione |
|---|---|
| **Confronto Multi-Dipendente** | Funzionalità di confronto simultaneo tra più dipendenti per agevolare l'analisi comparativa e strategica. |
| **Aggregazione Dati (Team/Area)** | Aggregazione e comparazione di dati a livello di team, area organizzativa, funzione o cluster omogenei. |
| **Simulazione Scenari Aziendali** | Simulazione di scenari organizzativi su popolazioni aziendali, con analisi degli impatti economici, ambientali e di sostenibilità. |
| **Integrazioni Dati HR e Survey** | Integrazione diretta con survey interne, basi dati HR o sistemi aziendali per condurre analisi più aderenti al contesto reale. |
| **Supporto Decisionale HR** | Evoluzione della piattaforma verso uno strumento di supporto decisionale HR a 360 gradi per politiche di flessibilità, sostenibilità e organizzazione del lavoro. |

### 🌍 Benessere, ESG & Personalizzazione Avanzata

| Feature | Descrizione |
|---|---|
| **Indicatori Work-Life Balance** | Introduzione di indicatori aggiuntivi relativi a benessere, work-life balance e impatto del pendolarismo sulla qualità della vita. |
| **Analisi Retention e Churn** | Mappatura e studio dei dati raccolti per supportare l'azienda nelle analisi sui trend di retention e il rischio di churn. |
| **Personalizzazione di Contesto** | Personalizzazione avanzata e dinamica dei parametri base di calcolo per singola città, Paese, sede aziendale specifica o contesto contrattuale. |

---

## 👤 Autore

**Andrea Capozio**

| | |
|---|---|
| 🔗 LinkedIn | [linkedin.com/in/andreacapozio](https://www.linkedin.com/in/andreacapozio/) |
| 🐙 GitHub | [github.com/andreacapozio](https://github.com/andreacapozio) |
| 🤗 Hugging Face | [huggingface.co/andreacapozio](https://huggingface.co/andreacapozio) |

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Andrea%20Capozio-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/andreacapozio/)
[![GitHub](https://img.shields.io/badge/GitHub-andreacapozio-181717?logo=github&logoColor=white)](https://github.com/andreacapozio)

---

## 📄 Licenza

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Questo progetto è distribuito sotto la **Apache License 2.0**.

Puoi liberamente usare, modificare e distribuire questo software, anche per uso commerciale, a condizione di:
- mantenere il **copyright notice** originale;
- includere una copia della licenza in ogni distribuzione;
- indicare eventuali modifiche apportate ai file originali.

Vedi il file [`LICENSE`](./LICENSE) per il testo completo.

---

## 📬 Contatti

Hai trovato un refuso, un bug o vuoi suggerire un miglioramento?

Apri una [Issue su GitHub](https://github.com/andreacapozio/smart-working-dashboard/issues) oppure scrivimi direttamente tramite [LinkedIn](https://www.linkedin.com/in/andreacapozio/).

Ogni contributo è benvenuto!
