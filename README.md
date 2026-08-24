# FantaWizard 🧙⚽

App locale per gestire l'asta del fantacalcio con prezzi consigliati dinamici,
tier list per ruolo e gestione budget in tempo reale.

## Funzionalità

- **Setup asta modulabile**: nome, modalità (Classic/Mantra), crediti, rosa per
  ruolo, numero giornate, partecipanti, bonus/malus (preset Leghe FC,
  personalizzabili), ripartizione budget per reparto.
- **Pipeline dati**: import quotazioni ufficiali Fantacalcio.it (Excel/CSV) e
  statistiche giocatori (ultime 3 stagioni), con matching automatico dei nomi
  tra fonti diverse e pulizia outlier. Aggiornamento giornaliero automatico
  (quando possibile) o import manuale con un click.
- **Dashboard asta live**: registri i giocatori chiamati, il prezzo di
  aggiudicazione e chi li ha presi. Per ogni giocatore vedi ruolo/posizione,
  quotazione/valore di mercato, statistiche ultime 3 stagioni.
- **Prezzo consigliato dinamico**: ricalcolato in base all'inflazione reale
  della tua asta (quanto stanno pagando gli altri rispetto al valore atteso).
- **Tier list e suggerimenti**: giocatori divisi in fasce per ruolo (prezzo +
  statistiche), suggerimenti d'acquisto in base a budget residuo e slot da
  riempire.

## Avvio rapido

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Apri http://127.0.0.1:8017 nel browser.

Al primo avvio l'app carica un dataset di esempio così puoi provarla subito.
Per i dati reali: sezione **Dati** → carica l'Excel delle quotazioni di
Fantacalcio.it (e le statistiche stagionali).

## Struttura

```
app/
  main.py            # API FastAPI + serve il frontend
  models.py          # SQLite (SQLAlchemy): aste, giocatori, stats, acquisti
  services/
    pricing.py       # prezzo atteso, inflazione, prezzo consigliato, max bid
    tiers.py         # tier per ruolo (quantili su valore+rendimento)
    matcher.py       # fuzzy matching nomi tra fonti diverse
  importers/
    quotazioni.py    # parser Excel/CSV listone Fantacalcio.it
    stats.py         # parser Excel/CSV statistiche stagionali
    sample_data.py   # dataset demo
  scheduler.py       # aggiornamento giornaliero automatico
static/              # frontend (nessun build step)
```
