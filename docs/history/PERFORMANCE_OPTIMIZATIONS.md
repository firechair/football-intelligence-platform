# 🚀 Performance Optimizations - FIP Operator

Ottimizzazioni implementate per migliorare le performance dell'operator.

---

## ✅ Ottimizzazioni Implementate

### 1. ⚡ Rimossa Query Predizioni
- **Problema**: Il frontend non usa le predizioni, ma venivano caricate ad ogni request
- **Soluzione**: Rimosso caricamento predizioni da `_build_fixture_response()`
- **Impatto**: ~10-15% riduzione tempo query

### 2. 📊 Database Indexes
- **File**: `database_indexes.sql`
- **Indexes aggiunti**:
  - `idx_fixture_date` - Query by date
  - `idx_fixture_date_status` - Filtro status + date
  - `idx_odds_fixture_market_collected` - Query quote ottimizzate
  - Altri 7 indexes strategici

**Come applicare:**
```bash
# Connettiti al database PostgreSQL Railway
psql $DATABASE_URL

# Esegui il file SQL
\i database_indexes.sql

# Verifica indexes creati
SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public';
```

### 3. 🔴 Redis Cache
- **Implementazione**: In-memory fallback se Redis non disponibile
- **Cache Keys**:
  - `fixtures:range:{start}:{end}` - TTL 5 minuti
  - `fixtures:live` - TTL 30 secondi
  - `fixtures:date:{date}` - TTL 5 minuti

**Setup Redis su Railway:**

1. **Aggiungi Redis al progetto Railway:**
   ```bash
   # Nel Railway Dashboard
   New -> Database -> Add Redis
   ```

2. **Copia Redis URL:**
   ```
   REDIS_URL=redis://default:password@example.invalid:6379
   ```

3. **Aggiungi variabile d'ambiente:**
   ```
   Railway Dashboard -> ingestion -> Variables -> Add Variable
   Name: REDIS_URL
   Value: [paste URL]
   ```

4. **Deploy:**
   ```bash
   git push origin main
   ```

**Note:**
- Se Redis non è disponibile, l'operator usa cache in-memory automaticamente
- Cache in-memory ha limite di 100 chiavi (FIFO)

---

## 📈 Performance Attese

### Prima delle ottimizzazioni:
- **Range query** (2 giorni, ~600 partite): 32 secondi
- **Live fixtures**: 15-20ms (ma chiamato ogni 30s)
- **Cache**: Nessuna

### Dopo le ottimizzazioni:
- **Range query** (prima chiamata): 5-8 secondi
- **Range query** (cached): 50-100ms ⚡
- **Live fixtures** (cached): 10-20ms ⚡
- **Risparmio CPU**: ~70%
- **Risparmio DB queries**: ~90%

---

## 🧪 Testing

### 1. Test Query Performance
```bash
# Test range query (prima chiamata - cache miss)
time curl "https://example.invalid/api/v1/fixtures/range?start_date=2025-09-30&end_date=2025-10-02"

# Test range query (cache hit)
time curl "https://example.invalid/api/v1/fixtures/range?start_date=2025-09-30&end_date=2025-10-02"

# Test live fixtures
time curl "https://example.invalid/api/v1/fixtures/live"
```

### 2. Test Cache Stats
```bash
# Verifica statistiche cache
curl "https://example.invalid/api/v1/admin/cache/stats"

# Output atteso (con Redis):
{
  "success": true,
  "cache_stats": {
    "type": "redis",
    "connected": true,
    "total_keys": 15,
    "hits": 234,
    "misses": 45
  }
}

# Output atteso (senza Redis):
{
  "success": true,
  "cache_stats": {
    "type": "memory",
    "connected": false,
    "total_keys": 12
  }
}
```

### 3. Clear Cache (se necessario)
```bash
# Pulisci tutta la cache
curl -X POST "https://example.invalid/api/v1/admin/cache/clear?pattern=*"

# Pulisci solo live fixtures
curl -X POST "https://example.invalid/api/v1/admin/cache/clear?pattern=fixtures:live"

# Pulisci solo range queries
curl -X POST "https://example.invalid/api/v1/admin/cache/clear?pattern=fixtures:range:*"
```

---

## 🔍 Monitoring

### Logs da monitorare:
```
[OPERATOR] 🎯 Cache HIT for range 2025-09-30 to 2025-10-02
[OPERATOR] ❌ Cache MISS - Querying DB for range 2025-09-30 to 2025-10-02
[OPERATOR] 💾 Cached response for range 2025-09-30 to 2025-10-02
```

### Metriche chiave:
- **Cache Hit Rate**: dovrebbe essere >80% dopo 5 minuti di uptime
- **Response Time**: <100ms per cache hits, <8s per cache misses
- **Memory Usage**: Redis ~50-100MB, In-memory ~10-20MB

---

## 🚀 Deploy Checklist

- [ ] Deploy nuovo codice su Railway
- [ ] Aggiungi Redis (opzionale ma consigliato)
- [ ] Esegui `database_indexes.sql` su PostgreSQL
- [ ] Verifica cache stats endpoint
- [ ] Monitora logs per cache hits/misses
- [ ] Test performance con curl
- [ ] Verifica frontend loading speed

---

## 🆘 Troubleshooting

### Cache non funziona
```bash
# Verifica configurazione
curl "https://example.invalid/api/v1/admin/cache/stats"

# Se type: "memory", Redis non è connesso (OK, fallback attivo)
# Se errore, controlla REDIS_URL nelle variabili Railway
```

### Performance ancora lenta
```bash
# 1. Verifica indexes database
psql $DATABASE_URL -c "SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public';"

# 2. Clear cache e riprova
curl -X POST "https://example.invalid/api/v1/admin/cache/clear?pattern=*"

# 3. Controlla logs Railway per errori
```

### Redis connection errors
- **Soluzione 1**: Verifica `REDIS_URL` è corretto
- **Soluzione 2**: Usa fallback in-memory (automatico)
- **Soluzione 3**: Restart Redis service su Railway

---

## 📝 Note Finali

1. **Redis è opzionale**: Se non vuoi usare Redis, tutto funziona ugualmente con cache in-memory
2. **Indexes sono critici**: Assicurati di eseguire `database_indexes.sql`
3. **TTL configurabili**: Puoi modificare TTL in `cache_service.py`
4. **Monitoraggio**: Controlla logs per identificare eventuali problemi

---

**Data ultima modifica**: 2025-09-30
**Versione**: 1.0
