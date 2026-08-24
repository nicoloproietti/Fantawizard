# FantaWizard — Specifica Funzionale

## 1. Setup Asta

### 1.1 Dati Lega
- Nome asta (testo libero)
- Numero squadre (2–20)
- Crediti iniziali per squadra (default 500)
- Modalità: Classic | Mantra
- Tipo asta: Chiamata classica | Busta chiusa
- Numero giornate campionato (default 38)

### 1.2 Composizione Rosa
Modulare per ruolo. In Classic i ruoli sono P/D/C/A.
In Mantra: Por/Dc/Dd/Ds/E/M/C/T/W/A/Pc.

L'utente definisce quanti slot per ogni ruolo (es. P=3, D=8, C=8, A=6 → 25).

### 1.3 Bonus / Malus
Ogni evento ha: attivo (bool) + valore (float, editabile).
Valori di default = standard Leghe FC.

#### Bonus/Malus base
| Codice           | Evento                     | Default | Ruoli applicabili |
|------------------|----------------------------|---------|-------------------|
| GOL              | Gol segnato                | +3      | Tutti             |
| GOL_SUBITO       | Gol subito                 | −1      | P                 |
| ASSIST           | Assist                     | +1      | Tutti             |
| ASSIST_FERMO     | Assist da fermo            | +1      | Tutti             |
| RIGORE_SEGNATO   | Rigore segnato             | +3      | Tutti             |
| RIGORE_SBAGLIATO | Rigore sbagliato           | −3      | Tutti             |
| RIGORE_PARATO    | Rigore parato              | +3      | P                 |
| AMMONIZIONE      | Ammonizione                | −0.5    | Tutti             |
| ESPULSIONE       | Espulsione                 | −1      | Tutti             |
| AUTOGOL          | Autogol                    | −2      | Tutti             |

#### Bonus/Malus avanzati (default OFF = 0)
| Codice              | Evento                      | Default | Ruoli applicabili |
|---------------------|------------------------------|---------|-------------------|
| PORTA_INVIOLATA     | Clean sheet 90 min           | 0       | P                 |
| GOL_VITTORIA        | Gol vittoria                 | 0       | Tutti             |
| GOL_PAREGGIO        | Gol pareggio                 | 0       | Tutti             |
| PALO_TRAVERSA       | Palo / traversa              | 0       | Tutti             |
| RIGORE_CONQUISTATO  | Rigore conquistato           | 0       | Tutti             |
| RIGORE_CAUSATO      | Rigore causato (fallo)       | 0       | Tutti             |
| SALVATAGGIO         | Salvataggio decisivo         | 0       | D, C              |
| ERRORE_DECISIVO     | Errore che porta al gol      | 0       | Tutti             |
| GOL_FUORI_AREA      | Gol da fuori area            | 0       | Tutti             |

### 1.4 Modificatori (on/off + parametri)
| Codice       | Modificatore          | Default | Note                                   |
|--------------|-----------------------|---------|----------------------------------------|
| MOD_DIFESA   | Modificatore difesa   | OFF     | Media voto P+3D migliori → bonus/malus |
| MOD_PORTIERE | Modificatore portiere | OFF     | Voto portiere → malus a squadra avv.   |
| MOD_CC       | Modificatore C.campo  | OFF     | Media voto centrocampisti               |
| MOD_FAIRPLAY | Modificatore fairplay | OFF     | Ammonizioni/espulsioni come mod.       |
| MOD_CAPITANO | Capitano              | OFF     | Bonus x2 su un giocatore designato     |

### 1.5 Ripartizione Budget per Reparto
Proporzione % dei crediti iniziali che l'utente vuole destinare a ogni reparto.
Default suggerito (Classic): P=8% / D=20% / C=27% / A=45%.
Modificabile liberamente; il sistema avvisa se la somma ≠ 100%.

### 1.6 Dati Squadre Partecipanti
Nome delle squadre/fantallenatori (opzionale, per tracciare le rose avversarie).

---

## 2. Dati Giocatori

### 2.1 Fonti
- **Quotazioni ufficiali**: file Excel/CSV da Fantacalcio.it (listone).
  Campi: nome, squadra, ruolo_classic, ruolo_mantra, quotazione_iniziale, quotazione_attuale.
- **Statistiche stagionali** (ultime 3 stagioni, peso 50/30/20):
  media_voto, fantamedia, presenze, gol, assist, rigori_tirati, rigori_segnati,
  rigori_parati, ammonizioni, espulsioni, autogol, clean_sheet (portieri),
  minuti_giocati, titolarità%.
- **Flag speciali**: rigorista, tiratore punizioni, capitano_reale.

### 2.2 Proiezione FantaMedia Attesa
```
FMA = media_voto_attesa + Σ (valore_bonus_lega × frequenza_evento_per90 × presenze_attese / 90)
```
Calcolata con i pesi bonus/malus specifici della lega dell'utente.
Utilizzata per tier list, prezzo atteso e indice di convenienza.

### 2.3 Prezzo Atteso Base
```
prezzo_base = f(FMA, ruolo, slot_disponibili_lega, crediti_medi_per_slot)
```
Calibrato sulle quotazioni ufficiali, scalato per crediti iniziali della lega.

---

## 3. Dashboard Asta Live

### 3.1 Flusso Rapido (ottimizzato per velocità)
1. Autocomplete: digiti 2-3 lettere → appare il giocatore
2. Inserisci prezzo + chi l'ha comprato (te / nome avversario)
3. Invio → salvato, aggiornamento istantaneo di tutto

### 3.2 Scheda Giocatore (popup o pannello laterale)
- Ruolo(i), squadra, età
- Quotazione ufficiale
- FMA attesa (calcolata con i bonus della tua lega)
- Stats ultime 3 stagioni: gol, assist, presenze, media voto, fantamedia
- Flag: rigorista, tiratore punizioni
- Prezzo consigliato attuale (aggiornato live)
- Indice di convenienza: prezzo_consigliato / prezzo_chiamato

### 3.3 Prezzo Consigliato Dinamico
Il motore ricalcola ad ogni acquisto:
- **Inflazione asta**: rapporto tra somma prezzi pagati e somma prezzi attesi
  per i giocatori già venduti, per ruolo.
- **Scarsità**: quanti giocatori di quel tier/ruolo restano liberi.
- **Budget residuo medio**: quanti crediti hanno mediamente le altre squadre
  per gli slot rimanenti.
```
prezzo_consigliato = prezzo_base × indice_inflazione × indice_scarsità
```
Clampato a [1, budget_max_spendibile].

### 3.4 Max Bid
Crediti massimi spendibili su questo giocatore senza compromettere
il completamento della rosa ai minimi per reparto.
```
max_bid = budget_residuo − (slot_rimanenti − 1) × 1
```
Più un calcolo intelligente: tiene conto dei target minimi per reparto
(almeno 1 giocatore di fascia 2+ per slot chiave).

### 3.5 Indice di Convenienza
```
convenienza = prezzo_consigliato / prezzo_attuale_chiamata
```
- > 1.2 → OTTIMO (verde)
- 0.9–1.2 → FAIR (giallo)
- < 0.9 → CARO (rosso)

### 3.6 Tier List per Ruolo
Fasce 1–4 calcolate per quantili di FMA dentro ogni ruolo:
- Fascia 1: top 15% → "titolari top"
- Fascia 2: 15–40% → "titolari solidi"
- Fascia 3: 40–70% → "rotazione / scommesse"
- Fascia 4: 70–100% → "panchinari / riempitivi"

Il tier si aggiorna live: un giocatore venduto esce, le soglie si ricalcolano
sui rimanenti.

### 3.7 Watchlist
Target pre-asta organizzati per ruolo e fascia.
Alert visivo quando un target viene chiamato.
Alert quando il reparto si svuota ("restano 2 attaccanti fascia 1").

### 3.8 Rose Avversarie
Tabella per avversario: giocatori presi, crediti spesi, budget residuo,
slot rimanenti per ruolo. Serve a stimare chi può ancora rilanciare.

---

## 4. Motore Pricing — Dettaglio Algoritmo

### 4.1 Proiezione punti
Per ogni giocatore g, con la config bonus della lega:
```
punti_attesi(g) = presenze_attese(g) × (
    media_voto_attesa(g)
    + gol_per90(g)     × presenze_attese(g)/90 × BONUS_GOL
    + assist_per90(g)  × presenze_attese(g)/90 × BONUS_ASSIST
    + ...per ogni evento con frequenza > 0
)
```
Stagioni pesate: ultima 50%, penultima 30%, terzultima 20%.
Se un giocatore ha solo 1 stagione, 100% su quella.

### 4.2 Prezzo base
Regressione lineare punti_attesi → quotazione ufficiale,
poi scalata per crediti_iniziali / crediti_standard (500).

### 4.3 Aggiornamento live
Ad ogni acquisto registrato:
1. Ricalcola inflazione per ruolo
2. Ricalcola scarsità per tier/ruolo
3. Ricalcola budget residuo medio avversari
4. Aggiorna prezzo_consigliato di tutti i giocatori liberi

### 4.4 Impatto dei modificatori
Se MOD_DIFESA attivo → bonus valore per portieri e difensori con media voto
alta (anche senza gol/assist, la media voto pura conta di più).
Se MOD_CAPITANO attivo → il sistema segnala chi sono i migliori candidati
capitano (FMA più alta in rosa).

---

## 5. Persistenza e Export
- Salvataggio automatico SQLite ad ogni operazione
- Ripresa asta multi-serata
- Export Excel rosa finale + storico acquisti
- Undo/correzione rapida (Ctrl+Z o edit inline)
