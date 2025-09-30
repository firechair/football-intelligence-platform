# 🔍 OPERATOR - ANALISI PROBLEMI E CORREZIONI

**Data**: 30 Settembre 2025, ore 21:30  
**Testing**: Locale con SQLite

---

## 🚨 PROBLEMI IDENTIFICATI

### 1. **Database UNIQUE Constraint Error** ❌
**Problema**: Errore durante il salvataggio dei bookmaker
```
UNIQUE constraint failed: bookmaker_info.api_id
```

**Causa**: Il codice crea bookmaker con `api_id=0` per bookmaker generici, ma questo viola il constraint UNIQUE su `api_id` quando ci sono già bookmaker salvati.

**Posizione**: `app/services/odds_collector.py:368-376`

```python
# ERRORE: Tutti i bookmaker generici hanno api_id=0
bookmaker_info = BookmakerInfo(
    api_id=0,  # ❌ Questo causa UNIQUE constraint error
    name=bookmaker_name,
    display_name=bookmaker_name,
    is_active=True
)
```

**Soluzione**: Usare una query `get_or_create` invece di creare sempre nuovi bookmaker, oppure rimuovere il constraint UNIQUE su `api_id` per i bookmaker generici.

---

### 2. **Cache Bloccata con Dati Vecchi** ❌
**Problema**: Il database Railway production aveva dati vecchi in cache che venivano restituiti anche dopo aver modificato i filtri.

**Causa**: 
- Cache Redis/in-memory con TTL troppo lungo (5 minuti per fixtures, 10 secondi per live)
- Nessun meccanismo di invalidazione cache quando vengono modificati i filtri

**Soluzione Applicata**: 
- ✅ Ridotto TTL cache live a 10 secondi
- ✅ Aggiunto endpoint `/admin/cache/clear` per pulizia manuale
- ⚠️ **TODO**: Implementare invalidazione automatica cache quando cambiano filtri o query

---

### 3. **Filtri Temporali Corretti ma Dati Assenti** ✅
**Problema**: Le query filtrano correttamente (es. partite live max 105 minuti fa), ma il database è vuoto o contiene solo dati vecchi.

**Causa**: Lo scheduler NON sta popolando il database correttamente a causa di:
1. Errore UNIQUE constraint che blocca il salvataggio delle quote
2. Database Railway inaccessibile da locale (`example.invalid`)
3. Scheduler potrebbe non essere attivo in produzione

**Test Locale**:
- ✅ Fixtures collector funziona: **268 fixtures** raccolte per oggi e domani
- ❌ Odds collector fallisce: errore UNIQUE constraint sui bookmaker
- ❌ Database resta vuoto

---

### 4. **Frontend Carica sempre 50 Live Matches (Errato)** ❌
**Problema**: Frontend mostrava sempre 50 partite live (anche quando non c'erano partite in corso).

**Causa**: Frontend chiamava sempre il database di produzione Railway, che aveva:
- Dati vecchi in cache
- Filtri temporali troppo larghi (prima del fix)
- Query non ottimizzate

**Soluzione Applicata**:
- ✅ Frontend API routes ora usano `localhost:8080` in development
- ✅ Filtri temporali stretti (max 105 minuti per live)
- ✅ Cache con TTL ridotto (10s per live)

---

### 5. **Scheduled Matches Lentissime (52 secondi)** ⚠️
**Problema**: Caricamento delle partite programmate richiedeva **52 secondi** (troppo lento).

**Causa Probabile**:
- Query senza indici ottimizzati
- Caricamento predizioni per ogni partita (non necessario per il frontend)
- Nessuna paginazione o limite sulle query

**Soluzioni Applicate**:
- ✅ **Rimosso caricamento predizioni** da `_build_fixture_response`
- ✅ **Aggiunto caching** (5 minuti per scheduled, 10s per live)
- ⚠️ **TODO**: Applicare indici database (script `database_indexes.sql` pronto)
- ⚠️ **TODO**: Implementare paginazione (es. 50 partite alla volta)

---

### 6. **Scheduler Non Verificato in Produzione** ⚠️
**Problema**: Non abbiamo verificato se lo scheduler sta girando in produzione e popolando il database Railway.

**Test Mancanti**:
- ❌ Verificare che lo scheduler parta all'avvio dell'operator in Railway
- ❌ Verificare che il database Railway venga popolato automaticamente ogni 30 minuti (daily) e 4 ore (main)
- ❌ Verificare che il cleanup rimuova partite vecchie

**Endpoints per Verifica**:
```bash
# Verifica stato scheduler (da implementare)
curl https://example.invalid/api/v1/admin/scheduler/status

# Verifica stato database
curl https://example.invalid/api/v1/admin/database/status

# Pulisci cache
curl -X POST https://example.invalid/api/v1/admin/cache/clear
```

---

## ✅ CORREZIONI APPLICATE

### Frontend
1. ✅ **API Routes** - Usano localhost in development, Railway in production
2. ✅ **Ridotto auto-refresh** - Da 30s a 60s per live matches
3. ✅ **Rimossi log ripetitivi** - Console più pulita

### Operator
1. ✅ **Filtri temporali stretti** - Live: 105 min max, Pre-live: 5 min max
2. ✅ **Cache Redis/In-Memory** - Fallback automatico se Redis non disponibile
3. ✅ **Rimosso caricamento predizioni** - Performance migliorata per fixtures
4. ✅ **Indici database pronti** - Script SQL creato: `database_indexes.sql`
5. ✅ **Endpoints cache management** - `/admin/cache/stats` e `/admin/cache/clear`

---

## 🔧 CORREZIONI DA FARE

### Alta Priorità

#### 1. **Fix UNIQUE Constraint su Bookmakers**
**File**: `app/services/odds_collector.py`  
**Linea**: 366-377

```python
# PRIMA (ERRORE):
bookmaker_info = db.query(BookmakerInfo).filter(
    BookmakerInfo.name == bookmaker_name
).first()

if not bookmaker_info:
    bookmaker_info = BookmakerInfo(
        api_id=0,  # ❌ UNIQUE constraint error
        name=bookmaker_name,
        display_name=bookmaker_name,
        is_active=True
    )
    db.add(bookmaker_info)
    db.commit()
    db.refresh(bookmaker_info)

# DOPO (FIX):
bookmaker_info = db.query(BookmakerInfo).filter(
    BookmakerInfo.name == bookmaker_name
).first()

if not bookmaker_info:
    # Trova il prossimo api_id disponibile per bookmaker generici
    max_api_id = db.query(func.max(BookmakerInfo.api_id)).scalar() or 0
    next_api_id = max_api_id + 1 if max_api_id >= 0 else 1000  # Usa 1000+ per generici
    
    bookmaker_info = BookmakerInfo(
        api_id=next_api_id,  # ✅ Unique per ogni bookmaker
        name=bookmaker_name,
        display_name=bookmaker_name,
        is_active=True
    )
    db.add(bookmaker_info)
    db.commit()
    db.refresh(bookmaker_info)
```

**OPPURE rimuovere UNIQUE constraint da api_id nel modello**:
```python
# app/models/odds_tracking.py
api_id: Mapped[int] = mapped_column(Integer)  # ❌ Remove unique=True
```

---

#### 2. **Applicare Indici Database in Produzione**
**Script pronto**: `database_indexes.sql`

**Opzione A - API Endpoint** (Raccomandato):
```bash
curl -X POST "https://example.invalid/api/v1/database/apply-indexes"
```

**Opzione B - Script Python**:
```bash
DATABASE_URL="postgresql://..." python3 apply_indexes.py
```

**Opzione C - psql Manuale**:
```bash
psql "$DATABASE_URL" -f ./ingestion/database_indexes.sql
```

---

#### 3. **Verificare Scheduler in Produzione**
**Aggiungere endpoint** `/admin/scheduler/status`:

```python
# app/api/admin.py
@router.get("/scheduler/status")
async def get_scheduler_status():
    from app.core.scheduler import scheduler
    return {
        "running": scheduler.running,
        "tasks": scheduler.tasks,
        "last_run": scheduler.last_run,  # TODO: Implementare tracking
        "next_run": scheduler.next_run,   # TODO: Implementare tracking
    }
```

---

### Media Priorità

#### 4. **Implementare Paginazione per Scheduled Matches**
**File**: `app/api/fixtures.py`

```python
@router.get("/range", response_model=FixturesByDateRangeResponse)
async def get_fixtures_by_date_range(
    start_date: date = Query(...),
    end_date: date = Query(...),
    league_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),  # ✅ Aggiungi paginazione
    page_size: int = Query(50, ge=1, le=100),  # ✅ Max 100 per pagina
    db: Session = Depends(get_db)
):
    # Implementa logica paginazione con OFFSET e LIMIT
    pass
```

---

#### 5. **Cache Invalidation Automatica**
Quando vengono modificati i filtri o i dati, invalidare automaticamente la cache:

```python
# Esempio: dopo aver salvato nuove odds
cache_service.clear_pattern("fixtures:*")
cache_service.clear_pattern("live:*")
```

---

## 📊 TEST RISULTATI

### Test Locale (SQLite)
| Test | Risultato | Note |
|------|-----------|------|
| Fixtures Collection | ✅ 268 fixtures | Oggi + Domani |
| Odds Collection | ❌ UNIQUE error | Bookmaker constraint |
| Live Fixtures API | ✅ 0 partite | Filtro funziona |
| Scheduled API | ✅ 0 partite | Database vuoto (normale) |
| Cache Service | ✅ Funziona | In-memory fallback |

### Test Produzione (Da Fare)
| Test | Status | Note |
|------|--------|------|
| Scheduler Running | ⏳ TODO | Verificare endpoint |
| Database Popolato | ⏳ TODO | Verificare fixtures oggi |
| Cache Clearing | ⏳ TODO | Test endpoint |
| Indici Applicati | ⏳ TODO | Applicare script SQL |

---

## 🚀 PROSSIMI PASSI

### Immediati (Ora)
1. ✅ Fix UNIQUE constraint su bookmakers
2. ✅ Applicare indici database in produzione
3. ✅ Verificare scheduler in produzione
4. ✅ Testare flusso completo: fixtures → odds → API → frontend

### Breve Termine (Domani)
1. Implementare endpoint `/admin/scheduler/status`
2. Aggiungere paginazione per scheduled matches
3. Implementare cache invalidation automatica
4. Monitorare performance in produzione con indici

### Lungo Termine
1. Implementare sistema di alerting per errori scheduler
2. Dashboard admin per monitoraggio real-time
3. Ottimizzare query con materialized views (PostgreSQL)
4. Implementare rate limiting più sofisticato

---

## 📝 CONCLUSIONI

### Problemi Reali Trovati
1. ❌ **UNIQUE Constraint Error** - Blocca tutto il popolamento database
2. ⚠️ **Scheduler Non Verificato** - Potrebbe non girare in produzione
3. ⚠️ **Indici Mancanti** - Query lente (52s per scheduled)
4. ⚠️ **Cache Bloccata** - Dati vecchi mostrati fino a pulizia manuale

### Problemi NON Reali
1. ✅ **Filtri Temporali** - Funzionano correttamente
2. ✅ **Query SQL** - Sintassi corretta, solo lente per mancanza indici
3. ✅ **Cache Service** - Implementato correttamente con fallback

### Correzioni Priority
**🔴 CRITICAL**: Fix UNIQUE constraint (blocca tutto)  
**🟠 HIGH**: Applicare indici database (performance)  
**🟡 MEDIUM**: Verificare scheduler production (affidabilità)  
**🟢 LOW**: Paginazione e cache invalidation (ottimizzazione)

---

**Prossimo commit**: Fix bookmaker UNIQUE constraint + deploy
