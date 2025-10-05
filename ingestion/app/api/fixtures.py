from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date, time
from pydantic import BaseModel

from app.core.database import get_db
from app.models.odds_tracking import FixtureTrackingStatus, ExtendedOddsHistory, BookmakerInfo
# MatchPredictions non più usato per performance
from app.services.cache_service import (
    cache_service,
    get_fixtures_cache_key,
    get_fixtures_range_cache_key,
    get_live_fixtures_cache_key
)

router = APIRouter(prefix="/fixtures", tags=["fixtures"])

class FixtureResponse(BaseModel):
    fixture_id: int
    home_team: str
    away_team: str
    home_team_logo: Optional[str] = None  # 🆕 Logo squadra casa
    away_team_logo: Optional[str] = None  # 🆕 Logo squadra ospite
    fixture_date: datetime
    league_id: Optional[int]
    league_name: str
    country_name: Optional[str] = None    # 🆕 Paese della lega
    league_logo: Optional[str] = None     # 🆕 Logo lega
    
    # Quote migliori per tutti i mercati
    best_odds: Dict[str, Dict[str, float]] = {}  # {"1": {"Bookmaker A": 2.10, "Bookmaker B": 2.05}, ...}
    
    # Predizioni
    prediction: Optional[Dict[str, Any]] = None

class FixturesByDateResponse(BaseModel):
    date: str
    total_matches: int
    matches: List[FixtureResponse]

class FixturesByDateRangeResponse(BaseModel):
    start_date: str
    end_date: str
    total_matches: int
    daily_fixtures: List[FixturesByDateResponse]

# 🆕 MAPPATURA LOGHI SQUADRE (da espandere) - URL funzionanti da Wikipedia
TEAM_LOGOS = {
    "Manchester United": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7a/Manchester_United_FC_crest.svg/1200px-Manchester_United_FC_crest.svg.png",
    "Liverpool": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0c/Liverpool_FC.svg/1200px-Liverpool_FC.svg.png",
    "Arsenal": "https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/1200px-Arsenal_FC.svg.png",
    "Chelsea": "https://upload.wikimedia.org/wikipedia/en/thumb/c/cc/Chelsea_FC.svg/1200px-Chelsea_FC.svg.png",
    "Manchester City": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/1200px-Manchester_City_FC_badge.svg.png",
    "Tottenham": "https://upload.wikimedia.org/wikipedia/en/thumb/b/b4/Tottenham_Hotspur.svg/1200px-Tottenham_Hotspur.svg.png",
    "Real Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Real_Madrid_CF.svg/1200px-Real_Madrid_CF.svg.png",
    "Barcelona": "https://upload.wikimedia.org/wikipedia/en/thumb/4/47/FC_Barcelona_%28crest%29.svg/1200px-FC_Barcelona_%28crest%29.svg.png",
    "Atletico Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/c/c1/Atletico_Madrid_logo.svg/1200px-Atletico_Madrid_logo.svg.png",
    "Bayern Munich": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/FC_Bayern_M%C3%BCnchen_logo_%282017%29.svg/1200px-FC_Bayern_M%C3%BCnchen_logo_%282017%29.svg.png",
    "Borussia Dortmund": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Borussia_Dortmund_logo.svg/1200px-Borussia_Dortmund_logo.svg.png",
    "Juventus": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/Juventus_FC_logo_%282017%29.svg/1200px-Juventus_FC_logo_%282017%29.svg.png",
    "AC Milan": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Logo_of_AC_Milan.svg/1200px-Logo_of_AC_Milan.svg.png",
    "Inter Milan": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/FC_Internazionale_Milano_2021.svg/1200px-FC_Internazionale_Milano_2021.svg.png",
    "Napoli": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/SSC_Neapel.svg/1200px-SSC_Neapel.svg.png",
    "PSG": "https://upload.wikimedia.org/wikipedia/en/thumb/a/a7/Paris_Saint-Germain_F.C..svg/1200px-Paris_Saint-Germain_F.C..svg.png",
    "Marseille": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Olympique_Marseille_logo.svg/1200px-Olympique_Marseille_logo.svg.png",
    "Lyon": "https://upload.wikimedia.org/wikipedia/en/thumb/e/e2/Olympique_Lyonnais_logo.svg/1200px-Olympique_Lyonnais_logo.svg.png",
    # Squadre brasiliane e altre
    "Figueirense": "https://upload.wikimedia.org/wikipedia/en/thumb/6/6c/Figueirense_FC_logo.svg/1200px-Figueirense_FC_logo.svg.png",
    "Flamengo": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Flamengo-RJ_%28BRA%29.png/1200px-Flamengo-RJ_%28BRA%29.png",
    "Palmeiras": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Palmeiras_logo.svg/1200px-Palmeiras_logo.svg.png",
    "Santos": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Santos_logo.svg/1200px-Santos_logo.svg.png",
    # Fix per Juventus U21 - usa lo stesso logo della Juventus
    "Juventus U21": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/Juventus_FC_logo_%282017%29.svg/1200px-Juventus_FC_logo_%282017%29.svg.png",
}

LEAGUE_LOGOS = {
    "Premier League": "https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/Premier_League_Logo.svg/1200px-Premier_League_Logo.svg.png",
    "La Liga": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/LaLiga.svg/1200px-LaLiga.svg.png",
    "Serie A": "https://upload.wikimedia.org/wikipedia/en/thumb/e/e1/Serie_A_logo_2019.svg/1200px-Serie_A_logo_2019.svg.png",
    "Bundesliga": "https://upload.wikimedia.org/wikipedia/en/thumb/d/df/Bundesliga_logo_%282017%29.svg/1200px-Bundesliga_logo_%282017%29.svg.png",
    "Ligue 1": "https://upload.wikimedia.org/wikipedia/en/thumb/b/ba/Ligue_1_logo.svg/1200px-Ligue_1_logo.svg.png",
    "Champions League": "https://upload.wikimedia.org/wikipedia/en/thumb/b/bf/UEFA_Champions_League_logo_2.svg/1200px-UEFA_Champions_League_logo_2.svg.png",
    "Europa League": "https://upload.wikimedia.org/wikipedia/en/thumb/c/c5/UEFA_Europa_League_logo.svg/1200px-UEFA_Europa_League_logo.svg.png",
    "Serie B": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/38/Serie_B_logo_2022.svg/1200px-Serie_B_logo_2022.svg.png",
}

def get_team_logo_url(team_name: str, api_logo_url: Optional[str] = None) -> Optional[str]:
    """Genera URL proxy per logo squadra usando prima API-Football, poi fallback"""
    if not team_name:
        return None
    
    from urllib.parse import quote_plus
    
    # 1. Usa logo da API-Football se disponibile
    if api_logo_url and api_logo_url.strip():
        qp_url = quote_plus(api_logo_url)
        qp_name = quote_plus(team_name)
        return f"/api/v1/assets/logo?url={qp_url}&name={qp_name}&type=team"
    
    # 2. Cerca logo diretto nella mappatura
    direct_url = TEAM_LOGOS.get(team_name)
    if direct_url:
        qp_url = quote_plus(direct_url)
        qp_name = quote_plus(team_name)
        return f"/api/v1/assets/logo?url={qp_url}&name={qp_name}&type=team"
    
    # 3. Nessun logo disponibile
    return None

def get_league_logo_url(league_name: str, api_logo_url: Optional[str] = None) -> Optional[str]:
    """Genera URL proxy per logo lega usando prima API-Football, poi fallback"""
    if not league_name:
        return None
    
    from urllib.parse import quote_plus
    
    # 1. Usa logo da API-Football se disponibile
    if api_logo_url and api_logo_url.strip():
        qp_url = quote_plus(api_logo_url)
        qp_name = quote_plus(league_name)
        return f"/api/v1/assets/logo?url={qp_url}&name={qp_name}&type=league"
    
    # 2. Cerca logo diretto nella mappatura
    direct_url = LEAGUE_LOGOS.get(league_name)
    if direct_url:
        qp_url = quote_plus(direct_url)
        qp_name = quote_plus(league_name)
        return f"/api/v1/assets/logo?url={qp_url}&name={qp_name}&type=league"
    
    # 3. Nessun logo disponibile
    return None

# 🆕 MERCATI SUPPORTATI
SUPPORTED_MARKETS = [
    # 1X2
    "1", "X", "2", "1X", "12", "X2",
    # Goal/NoGoal  
    "Goal", "NoGoal",
    # Over/Under
    "Over1.5", "Under1.5", "Over2.5", "Under2.5", "Over3.5", "Under3.5",
    # Combinati (se disponibili)
    "1+Over2.5", "2+Over2.5", "X+Under2.5", "1+Goal", "2+Goal"
]

@router.get("", response_model=FixturesByDateResponse)
async def get_fixtures_main(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    limit: int = Query(500, description="Max fixtures to return"),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 ENDPOINT PRINCIPALE - Partite per data specifica o oggi se non specificata"""
    try:
        if date:
            # Parse date string to date object
            target_date = datetime.fromisoformat(date).date()
        else:
            # Default to today if no date specified
            target_date = datetime.now().date()
        
        fixtures_response = await _get_fixtures_by_date(target_date, league_id, db)
        
        # Apply limit to matches if specified
        if limit and limit < len(fixtures_response.matches):
            fixtures_response.matches = fixtures_response.matches[:limit]
            fixtures_response.total_matches = len(fixtures_response.matches)
        
        return fixtures_response
        
    except Exception as e:
        print(f"Error in get_fixtures_main: {str(e)}")
        return FixturesByDateResponse(
            date=date or datetime.now().date().isoformat(),
            total_matches=0,
            matches=[]
        )

@router.get("/today", response_model=FixturesByDateResponse)
async def get_today_fixtures(
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 Partite di oggi con quote migliori e loghi"""
    today = datetime.now().date()
    return await _get_fixtures_by_date(today, league_id, db)

@router.get("/tomorrow", response_model=FixturesByDateResponse)
async def get_tomorrow_fixtures(
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 Partite di domani con quote migliori e loghi"""
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    return await _get_fixtures_by_date(tomorrow, league_id, db)

@router.get("/date/{target_date}", response_model=FixturesByDateResponse)
async def get_fixtures_by_date(
    target_date: date,
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 Partite per una data specifica (YYYY-MM-DD)"""
    return await _get_fixtures_by_date(target_date, league_id, db)

@router.get("/range", response_model=FixturesByDateRangeResponse)
async def get_fixtures_by_date_range(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    important_only: bool = Query(False, description="Return only important leagues (Serie A, Premier League, etc.)"),
    db: Session = Depends(get_db)
):
    """🎯 FIXED con CACHE: Rispetta i parametri start_date e end_date per il range richiesto"""
    
    # 🔴 CACHE: Prova a recuperare dalla cache
    cache_key = f"fixtures_range_{start_date.isoformat()}_{end_date.isoformat()}_{league_id}_{important_only}"
    cached_response = cache_service.get(cache_key)
    if cached_response:
        print(f"[OPERATOR] 🎯 Cache HIT for range {start_date} to {end_date} (important_only={important_only})")
        return FixturesByDateRangeResponse(**cached_response)

    print(f"[OPERATOR] ❌ Cache MISS - Querying DB for range {start_date} to {end_date} (important_only={important_only})")

    # Determina i campionati da includere
    important_league_ids = []
    if important_only:
        # Campionati importanti (stessa logica del backend)
        important_league_ids = [
            135, 136, 137, 138,  # Serie A, B, C, D (Italia)
            39,  # Premier League (Inghilterra)
            140,  # La Liga (Spagna)
            78,   # Bundesliga (Germania)
            61,   # Ligue 1 (Francia)
            88,   # Eredivisie (Olanda)
            144,  # Pro League (Belgio)
            2, 3, # Champions League, Europa League
            5, 960, 10  # Nations League, Euro Qualifiers, World Cup Qualifiers
        ]
        print(f"[OPERATOR] Filtering for {len(important_league_ids)} important leagues")

    # Raccogli partite per ogni giorno nel range (solo future)
    daily_fixtures = []
    current_date = start_date
    total_matches = 0

    while current_date <= end_date:
        if important_only:
            # Per ogni campionato importante, ottieni le partite del giorno
            day_fixtures = await _get_important_fixtures_by_date(current_date, important_league_ids, db)
        else:
            day_fixtures = await _get_fixtures_by_date(current_date, league_id, db)

        if day_fixtures.total_matches > 0:
            daily_fixtures.append(day_fixtures)
            total_matches += day_fixtures.total_matches
        current_date += timedelta(days=1)
    
    print(f"[OPERATOR] Returning {total_matches} upcoming matches (past matches filtered out)")
    
    response = FixturesByDateRangeResponse(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_matches=total_matches,
        daily_fixtures=daily_fixtures
    )
    
    # 🔴 CACHE: Salva in cache per 5 minuti (300 secondi)
    cache_service.set(cache_key, response.model_dump(), ttl_seconds=300)
    print(f"[OPERATOR] 💾 Cached response for range {start_date} to {end_date}")
    
    return response

@router.get("/live", response_model=List[FixtureResponse])
async def get_live_fixtures(
    limit: int = Query(50, ge=1, le=100, description="Max live fixtures to return"),
    force_refresh: bool = Query(False, description="Force cache refresh"),
    db: Session = Depends(get_db)
):
    """🔴 Partite REALMENTE LIVE - versione di emergenza"""
    print(f"[OPERATOR] 🚨 Emergency live fixtures endpoint called")

    try:
        # Test minimo: restituisci lista vuota per verificare che l'endpoint risponde
        print(f"[OPERATOR] 🚨 Returning empty list")
        return []

    except Exception as e:
        print(f"[OPERATOR] ❌ Emergency endpoint failed: {str(e)}")
        return []

async def _convert_api_fixture_to_frontend(api_fixture: Dict[str, Any], db: Session) -> FixtureResponse:
    """Converte dati fixture dall'API direttamente in formato frontend"""
    fixture_data = api_fixture.get('fixture', {})
    league_data = api_fixture.get('league', {})
    teams_data = api_fixture.get('teams', {})
    goals_data = api_fixture.get('goals', {})
    score_data = api_fixture.get('score', {})

    # Converti data
    fixture_date = datetime.fromisoformat(fixture_data.get('date', '').replace('Z', '+00:00'))

    # Loghi squadre
    home_logo = get_team_logo_url(teams_data.get('home', {}).get('name'), teams_data.get('home', {}).get('logo'))
    away_logo = get_team_logo_url(teams_data.get('away', {}).get('name'), teams_data.get('away', {}).get('logo'))
    league_logo = get_league_logo_url(league_data.get('name'), league_data.get('logo'))

    # Per ora saltiamo le quote per debug - restituiamo partite senza quote
    best_odds = {}
    # TODO: Riaggiungere quote dopo aver risolto il problema di timeout

    return FixtureResponse(
        fixture_id=fixture_id,
        home_team=teams_data.get('home', {}).get('name', 'Unknown'),
        away_team=teams_data.get('away', {}).get('name', 'Unknown'),
        home_team_logo=home_logo,
        away_team_logo=away_logo,
        fixture_date=fixture_date,
        league_id=league_data.get('id'),
        league_name=league_data.get('name', 'Unknown League'),
        country_name=league_data.get('country'),
        league_logo=league_logo,
        best_odds=best_odds,
        prediction=None  # Non carichiamo predizioni per live matches
    )

@router.get("/upcoming", response_model=List[FixtureResponse])
async def get_upcoming_fixtures(
    days_ahead: int = Query(10, ge=1, le=10, description="Days ahead to look (ignored, returns today until 6am tomorrow)"),
    limit: int = Query(100, ge=1, le=500, description="Max fixtures to return"),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """📅 Partite programmate SOLO OGGI fino mezzanotte con quote 1X2"""
    now = datetime.now()
    
    # CORREZIONE: Solo oggi fino mezzanotte (non fino alle 6 del mattino dopo)
    today_start = datetime.combine(now.date(), datetime.min.time())
    today_midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    
    query = db.query(FixtureTrackingStatus).filter(
        and_(
            FixtureTrackingStatus.fixture_date >= today_start,
            FixtureTrackingStatus.fixture_date < today_midnight,  # Fino mezzanotte
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        )
    )
    
    if league_id:
        query = query.filter(FixtureTrackingStatus.league_id == league_id)
    
    fixtures = query.order_by(FixtureTrackingStatus.fixture_date).limit(limit).all()
    
    result = []
    for fixture in fixtures:
        fixture_data = await _build_fixture_response(fixture, db)
        
        # FILTRO: Solo partite con quote 1X2 (per programmate)
        odds = fixture_data.best_odds
        has_1x2_odds = any(odds.get(market) and len(odds.get(market, {})) > 0 for market in ["1", "X", "2"])
        
        if has_1x2_odds:
            result.append(fixture_data)
    
    print(f"Upcoming: {len(result)} matches with 1X2 odds from {len(fixtures)} total today fixtures")
    return result

async def _get_fixtures_by_date(target_date: date, league_id: Optional[int], db: Session) -> FixturesByDateResponse:
    """Helper per ottenere partite per una data specifica (solo future e non completate)"""
    try:
        from datetime import timezone
        # Usa UTC per coerenza con il database
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        # Filtra le partite finite più di 1 ora fa per tutti i giorni
        # Questo è coerente con il frontend che marca come "Finished" le partite > 1 ora fa
        if target_date == now_utc.date():
            # Per oggi: solo partite future (iniziate max 1 ora fa) o non ancora iniziate
            start_datetime = now_utc - timedelta(hours=1)  # Include partite iniziate max 1 ora fa
            end_datetime = datetime.combine(target_date, time(23, 59, 59))
        else:
            # Per altri giorni: tutte le partite del giorno (il frontend filtrerà quelle finite)
            start_datetime = datetime.combine(target_date, time(0, 0, 0))
            end_datetime = datetime.combine(target_date, time(23, 59, 59))

        # ✅ FILTRO MIGLIORATO: Escludi esplicitamente le partite "completed"
        query = db.query(FixtureTrackingStatus).filter(
            and_(
                FixtureTrackingStatus.fixture_date >= start_datetime,
                FixtureTrackingStatus.fixture_date <= end_datetime,
                FixtureTrackingStatus.tracking_status.in_(["pending", "active"]),
                FixtureTrackingStatus.tracking_status != "completed"  # Escludi completate
            )
        )

        if league_id:
            query = query.filter(FixtureTrackingStatus.league_id == league_id)

        fixtures = query.order_by(FixtureTrackingStatus.fixture_date).all()

        # 🚀 OTTIMIZZAZIONE: Recupera TUTTE le quote per TUTTE le partite in una sola query
        fixture_ids = [f.fixture_id for f in fixtures]
        all_odds = {}

        if fixture_ids:
            # Query unica per recuperare tutte le quote più recenti per tutti i fixture
            from sqlalchemy import desc
            odds_query = db.query(ExtendedOddsHistory).filter(
                and_(
                    ExtendedOddsHistory.fixture_id.in_(fixture_ids),
                    ExtendedOddsHistory.market_name.in_(["1", "X", "2"])  # Solo mercati principali per performance
                )
            ).order_by(ExtendedOddsHistory.fixture_id, desc(ExtendedOddsHistory.collected_at))

            odds_results = odds_query.all()

            # Raggruppa le quote per fixture_id e market - prendi la quota più recente per ogni bookmaker
            odds_dict = {}
            for odd in odds_results:
                key = (odd.fixture_id, odd.market_name, odd.bookmaker_name)
                if key not in odds_dict or odds_dict[key].collected_at < odd.collected_at:
                    odds_dict[key] = odd

            # Costruisci il dizionario finale delle quote
            for odd in odds_dict.values():
                if odd.fixture_id not in all_odds:
                    all_odds[odd.fixture_id] = {}

                if odd.market_name not in all_odds[odd.fixture_id]:
                    all_odds[odd.fixture_id][odd.market_name] = {}

                all_odds[odd.fixture_id][odd.market_name][odd.bookmaker_name] = float(odd.odd_value)

        matches = []
        successful_count = 0
        error_count = 0

        for fixture in fixtures:
            try:
                # 🚀 USA LE QUOTE PRECARICATE invece di chiamare _get_best_odds_for_market
                fixture_odds = all_odds.get(fixture.fixture_id, {})

                fixture_data = await _build_fixture_response_optimized(fixture, fixture_odds, db)

                # TEMPORANEO: Mostra tutte le partite per testing, anche senza quote
                # TODO: Ripristinare il filtro quote 1X2 quando il processo di collezione funziona
                odds = fixture_data.best_odds
                has_1x2_odds = any(odds.get(market) and len(odds.get(market, {})) > 0 for market in ["1", "X", "2"])

                # Per ora, includi sempre le partite (con o senza quote)
                matches.append(fixture_data)
                successful_count += 1

                if not has_1x2_odds:
                    # Log partite senza quote per debug
                    print(f"DEBUG: Fixture {fixture.fixture_id} has no 1X2 odds but included for testing")
            except Exception as e:
                # Log error but continue with other fixtures
                print(f"Error building fixture response for {fixture.fixture_id}: {str(e)}")
                error_count += 1
                continue

        print(f"Processed {len(fixtures)} fixtures: {successful_count} with 1X2 odds included, {error_count} without odds (filtered out)")

        return FixturesByDateResponse(
            date=target_date.isoformat(),
            total_matches=len(matches),
            matches=matches
        )
    except Exception as e:
        # Return empty response if there's any error
        print(f"Error in _get_fixtures_by_date: {str(e)}")
        return FixturesByDateResponse(
            date=target_date.isoformat(),
            total_matches=0,
            matches=[]
        )

async def _get_important_fixtures_by_date(target_date: date, important_league_ids: List[int], db: Session) -> FixturesByDateResponse:
    """Helper per ottenere partite importanti per una data specifica"""
    try:
        from datetime import timezone
        # Usa UTC per coerenza con il database
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        # Filtra le partite finite più di 1 ora fa per oggi
        if target_date == now_utc.date():
            # Per oggi: solo partite future (iniziate max 1 ora fa) o non ancora iniziate
            start_datetime = now_utc - timedelta(hours=1)
            end_datetime = datetime.combine(target_date, time(23, 59, 59))
        else:
            # Per altri giorni: tutte le partite del giorno
            start_datetime = datetime.combine(target_date, time(0, 0, 0))
            end_datetime = datetime.combine(target_date, time(23, 59, 59))

        # ✅ FILTRO per campionati importanti E escludi partite completate
        query = db.query(FixtureTrackingStatus).filter(
            and_(
                FixtureTrackingStatus.fixture_date >= start_datetime,
                FixtureTrackingStatus.fixture_date <= end_datetime,
                FixtureTrackingStatus.league_id.in_(important_league_ids),
                FixtureTrackingStatus.tracking_status.in_(["pending", "active"]),
                FixtureTrackingStatus.tracking_status != "completed"
            )
        )

        fixtures = query.order_by(FixtureTrackingStatus.fixture_date).all()

        matches = []
        successful_count = 0
        error_count = 0

        for fixture in fixtures:
            try:
                fixture_data = await _build_fixture_response(fixture, db)
                matches.append(fixture_data)
                successful_count += 1
            except Exception as e:
                print(f"Error building fixture response for {fixture.fixture_id}: {str(e)}")
                error_count += 1
                continue

        print(f"Processed {len(fixtures)} important fixtures: {successful_count} successful, {error_count} errors")

        return FixturesByDateResponse(
            date=target_date.isoformat(),
            total_matches=len(matches),
            matches=matches
        )
    except Exception as e:
        print(f"Error in _get_important_fixtures_by_date: {str(e)}")
        return FixturesByDateResponse(
            date=target_date.isoformat(),
            total_matches=0,
            matches=[]
        )

async def _build_fixture_response_optimized(fixture: FixtureTrackingStatus, preloaded_odds: Dict[str, Dict[str, float]], db: Session) -> FixtureResponse:
    """Helper ottimizzato per costruire risposta fixture con quote pre-caricate"""

    # 🆕 Loghi squadre tramite proxy (prima API-Football, poi fallback)
    home_logo = get_team_logo_url(fixture.home_team, fixture.home_team_logo)
    away_logo = get_team_logo_url(fixture.away_team, fixture.away_team_logo)
    league_logo = get_league_logo_url(fixture.league_name, fixture.league_logo)

    # 🚀 USA LE QUOTE PRECARICATE invece di query database
    best_odds = preloaded_odds

    return FixtureResponse(
        fixture_id=fixture.fixture_id,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        home_team_logo=home_logo,
        away_team_logo=away_logo,
        fixture_date=fixture.fixture_date,
        league_id=fixture.league_id,
        league_name=fixture.league_name,
        country_name=getattr(fixture, 'country_name', None),  # Paese della lega
        league_logo=league_logo,
        best_odds=best_odds,
        prediction=None  # Non caricato per performance
    )

async def _build_fixture_response(fixture: FixtureTrackingStatus, db: Session) -> FixtureResponse:
    """Helper per costruire risposta fixture completa con quote migliori"""
    
    # 🆕 Loghi squadre tramite proxy (prima API-Football, poi fallback)
    home_logo = get_team_logo_url(fixture.home_team, fixture.home_team_logo)
    away_logo = get_team_logo_url(fixture.away_team, fixture.away_team_logo)
    league_logo = get_league_logo_url(fixture.league_name, fixture.league_logo)
    
    # 🆕 Quote migliori - usa lo stesso criterio semplice del backend principale
    # Controlla solo se almeno una delle quote 1/X/2 non è None, vuota o 0
    best_odds = {}
    
    # Prima cerca le quote 1X2 di base
    for market in ["1", "X", "2"]:
        try:
            market_odds = await _get_best_odds_for_market(fixture.fixture_id, market, db)
            if market_odds:
                best_odds[market] = market_odds
        except Exception as e:
            # Log error but continue with other markets
            print(f"Error getting odds for fixture {fixture.fixture_id}, market {market}: {str(e)}")
            continue
    
    # Opzionale: aggiungi altri mercati se disponibili, ma non obbligatorio
    additional_markets = [m for m in SUPPORTED_MARKETS if m not in ["1", "X", "2"]]
    for market in additional_markets:
        try:
            market_odds = await _get_best_odds_for_market(fixture.fixture_id, market, db)
            if market_odds:
                best_odds[market] = market_odds
        except Exception as e:
            # Log error but continue with other markets
            print(f"Error getting odds for fixture {fixture.fixture_id}, market {market}: {str(e)}")
            continue
    
    # ⚡ OTTIMIZZAZIONE: Predizioni NON caricate per performance (frontend non le usa)
    
    return FixtureResponse(
        fixture_id=fixture.fixture_id,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        home_team_logo=home_logo,
        away_team_logo=away_logo,
        fixture_date=fixture.fixture_date,
        league_id=fixture.league_id,
        league_name=fixture.league_name,
        country_name=getattr(fixture, 'country_name', None),  # Paese della lega
        league_logo=league_logo,
        best_odds=best_odds,
        prediction=None  # Non più caricato per performance
    )

async def _build_fixture_response_no_country(fixture: FixtureTrackingStatus, db: Session) -> FixtureResponse:
    """Helper alternativo per costruire risposta fixture SENZA country_name (per compatibilità db)"""

    # 🆕 Loghi squadre tramite proxy (prima API-Football, poi fallback)
    home_logo = get_team_logo_url(fixture.home_team, fixture.home_team_logo)
    away_logo = get_team_logo_url(fixture.away_team, fixture.away_team_logo)
    league_logo = get_league_logo_url(fixture.league_name, fixture.league_logo)

    # 🆕 Quote migliori - usa lo stesso criterio semplice del backend principale
    best_odds = {}

    # Prima cerca le quote 1X2 di base
    for market in ["1", "X", "2"]:
        try:
            market_odds = await _get_best_odds_for_market(fixture.fixture_id, market, db)
            if market_odds:
                best_odds[market] = market_odds
        except Exception as e:
            # Log error but continue with other markets
            print(f"Error getting odds for fixture {fixture.fixture_id}, market {market}: {str(e)}")
            continue

    # ⚡ OTTIMIZZAZIONE: Predizioni NON caricate per performance (frontend non le usa)

    return FixtureResponse(
        fixture_id=fixture.fixture_id,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        home_team_logo=home_logo,
        away_team_logo=away_logo,
        fixture_date=fixture.fixture_date,
        league_id=fixture.league_id,
        league_name=fixture.league_name,
        country_name=None,  # Non disponibile nel db
        league_logo=league_logo,
        best_odds=best_odds,
        prediction=None  # Non più caricato per performance
    )

async def _get_best_odds_for_market(fixture_id: int, market: str, db: Session) -> Dict[str, float]:
    """Helper per ottenere le migliori quote per un mercato specifico"""
    
    # Ottieni le quote più recenti per questo mercato
    # TEMPORANEO: Rimuovi filtro temporale per debug - trova TUTTE le quote disponibili
    latest_odds = db.query(ExtendedOddsHistory).filter(
        and_(
            ExtendedOddsHistory.fixture_id == fixture_id,
            ExtendedOddsHistory.market_name == market
        )
    ).order_by(desc(ExtendedOddsHistory.collected_at)).all()
    
    if not latest_odds:
        return {}
    
    # Raggruppa per bookmaker e prendi la quota più recente per ogni bookmaker
    bookmaker_odds = {}
    for odd in latest_odds:
        if odd.bookmaker_name not in bookmaker_odds:
            bookmaker_odds[odd.bookmaker_name] = float(odd.odd_value)
    
    return bookmaker_odds
