from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging
import hashlib
import re

router = APIRouter(prefix="/assets", tags=["assets"])

# Cache in-memory per loghi (TTL 6 ore)
logo_cache: Dict[str, dict] = {}
failure_cache: Dict[str, datetime] = {}

# Semaforo per limitare fetch concorrenti
logo_semaphore = asyncio.Semaphore(4)

# Logger
logger = logging.getLogger(__name__)

# Mappatura per normalizzare nomi squadre con varianti
TEAM_NAME_MAPPINGS = {
    "Juventus U21": "Juventus",
    "Juventus Under 21": "Juventus",
    "Juventus Primavera": "Juventus",
    "AC Milan U21": "AC Milan",
    "Inter Milan U21": "Inter Milan",
    "Real Madrid U21": "Real Madrid",
    "Barcelona U21": "Barcelona",
    "Bayern Munich U21": "Bayern Munich",
}

def normalize_team_name(team_name: str) -> str:
    """Normalizza il nome della squadra per gestire varianti come U21, W, Femminile, etc."""
    if not team_name:
        return team_name
    
    # Controlla mappatura diretta
    normalized = TEAM_NAME_MAPPINGS.get(team_name)
    if normalized:
        return normalized
    
    # Rimuovi suffissi comuni per squadre giovanili/femminili/varianti
    import re
    patterns = [
        # Squadre giovanili
        r'\s+U21$', r'\s+U20$', r'\s+U19$', r'\s+U18$', r'\s+U17$', r'\s+U16$',
        r'\s+Under\s+21$', r'\s+Under\s+20$', r'\s+Under\s+19$',
        r'\s+Primavera$', r'\s+Youth$', r'\s+Reserve$', r'\s+Reserves$',
        r'\s+Junior$', r'\s+Juniors$', r'\s+Academy$', r'\s+Giovanili$',
        # Squadre di riserva
        r'\s+B$', r'\s+II$', r'\s+2$', r'\s+III$', r'\s+3$',
        r'\s+FC\s+B$', r'\s+FC\s+II$', r'\s+FC\s+2$',
        # Squadre femminili
        r'\s+W$', r'\s+Women$', r'\s+Femminile$', r'\s+F$',
        r'\s+Ladies$', r'\s+Girls$', r'\s+Donne$',
        # Squadre maschili (raramente usato ma per completezza)
        r'\s+M$', r'\s+Men$', r'\s+Maschile$', r'\s+Uomini$'
    ]
    
    original_name = team_name
    # Applica tutti i pattern fino a quando non ci sono più cambiamenti
    changed = True
    iterations = 0
    while changed and iterations < 3:  # Limite per evitare loop infiniti
        changed = False
        for pattern in patterns:
            new_name = re.sub(pattern, '', team_name, flags=re.IGNORECASE)
            if new_name != team_name:
                team_name = new_name.strip()
                changed = True
                break
        iterations += 1
    
    result = team_name.strip()
    if result != original_name:
        logger.info(f"Team name normalized: '{original_name}' -> '{result}'")
    
    return result

# Headers per evitare rate limiting
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# URL problematici da evitare (rimosso media.api-sports.io per permettere loghi API-Football)
PROBLEMATIC_DOMAINS = {
    # 'media.api-sports.io',  # Commentato per permettere loghi API-Football
    'logos.api-sports.io',
    'media-1.api-sports.io',
    'media-2.api-sports.io'
}

def is_valid_image_url(url: str) -> bool:
    """Valida se l'URL è un'immagine valida"""
    if not url or not isinstance(url, str):
        return False
    
    # Controlla se è un URL valido
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain...
        r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # host...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        return False
    
    # Controlla domini problematici
    for domain in PROBLEMATIC_DOMAINS:
        if domain in url:
            return False
    
    # Controlla estensioni immagine
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']
    url_lower = url.lower()
    
    # Se ha estensione immagine, è valido
    if any(url_lower.endswith(ext) for ext in image_extensions):
        return True
    
    # Se non ha estensione ma sembra un URL di immagine, è valido
    if any(keyword in url_lower for keyword in ['logo', 'image', 'img', 'avatar']):
        return True
    
    # Accetta placeholder da via.placeholder.com
    if 'via.placeholder.com' in url_lower:
        return True
    
    return False

def get_cache_key(url: str) -> str:
    """Genera chiave cache per URL"""
    return hashlib.md5(url.encode()).hexdigest()

def is_cache_valid(cache_entry: dict) -> bool:
    """Controlla se l'entry cache è ancora valida"""
    if not cache_entry:
        return False
    
    cached_at = cache_entry.get('cached_at')
    if not cached_at:
        return False
    
    # TTL 6 ore per successi, 5-30 minuti per failure
    ttl_hours = 6 if cache_entry.get('success', False) else 0.5
    expiry = cached_at + timedelta(hours=ttl_hours)
    
    return datetime.now() < expiry

def is_failure_cached(url: str) -> bool:
    """Controlla se l'URL è in failure cache"""
    cache_key = get_cache_key(url)
    
    if cache_key not in failure_cache:
        return False
    
    failure_time = failure_cache[cache_key]
    # Failure cache: 5-30 minuti a seconda del tipo di errore
    expiry = failure_time + timedelta(minutes=30)
    
    if datetime.now() > expiry:
        del failure_cache[cache_key]
        return False
    
    return True

async def fetch_image_with_retry(url: str, max_retries: int = 2) -> tuple[bytes, str]:
    """Fetch immagine con retry e gestione errori"""
    
    async with logo_semaphore:
        for attempt in range(max_retries + 1):
            try:
                timeout = httpx.Timeout(10.0, connect=5.0)
                
                async with httpx.AsyncClient(
                    timeout=timeout,
                    headers=DEFAULT_HEADERS,
                    follow_redirects=True
                ) as client:
                    
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', 'image/png')
                        
                        # Verifica che sia effettivamente un'immagine
                        if not content_type.startswith('image/'):
                            content_type = 'image/png'
                        
                        return response.content, content_type
                    
                    elif response.status_code == 429:  # Rate limiting
                        if attempt < max_retries:
                            wait_time = (attempt + 1) * 2
                            logger.warning(f"Rate limited for {url}, waiting {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise HTTPException(status_code=429, detail="Rate limited")
                    
                    elif response.status_code in [404, 403]:
                        raise HTTPException(status_code=404, detail="Image not found")
                    
                    else:
                        raise HTTPException(
                            status_code=response.status_code, 
                            detail=f"Failed to fetch image: {response.status_code}"
                        )
            
            except httpx.TimeoutException:
                if attempt < max_retries:
                    logger.warning(f"Timeout for {url}, retrying...")
                    await asyncio.sleep(1)
                    continue
                else:
                    raise HTTPException(status_code=408, detail="Request timeout")
            
            except httpx.RequestError as e:
                if attempt < max_retries:
                    logger.warning(f"Request error for {url}: {e}, retrying...")
                    await asyncio.sleep(1)
                    continue
                else:
                    raise HTTPException(status_code=502, detail="Failed to fetch image")
    
    raise HTTPException(status_code=500, detail="Max retries exceeded")

@router.get("/logo")
@router.head("/logo")
async def get_logo_proxy(
    request: Request,
    url: str = Query(..., description="URL del logo da recuperare"),
    name: Optional[str] = Query(None, description="Nome della squadra/lega"),
    type: Optional[str] = Query(None, description="Tipo di logo (team/league)"),
    fallback: Optional[str] = Query(None, description="URL di fallback se il principale fallisce")
):
    """Proxy per loghi con cache, gestione errori e fallback - Versione semplificata per compatibilità frontend"""
    
    # Check for known problematic URLs and return 204 immediately (like backend)
    if not url or url in ['null', '', 'undefined']:
        return Response(status_code=204)
    
    # Validazione URL semplificata
    if not is_valid_image_url(url):
        return Response(status_code=204)
    
    cache_key = get_cache_key(url)
    
    # Controlla cache successi
    if cache_key in logo_cache and is_cache_valid(logo_cache[cache_key]):
        cached_entry = logo_cache[cache_key]
        
        # Per richieste HEAD, restituisci solo headers
        if request.method == "HEAD":
            return Response(
                content=None,
                media_type=cached_entry['content_type'],
                headers={
                    'Cache-Control': 'public, max-age=21600',  # 6 ore
                    'X-Cache': 'HIT',
                    'Content-Length': str(len(cached_entry['content']))
                }
            )
        
        return Response(
            content=cached_entry['content'],
            media_type=cached_entry['content_type'],
            headers={
                'Cache-Control': 'public, max-age=21600',  # 6 ore
                'X-Cache': 'HIT'
            }
        )
    
    try:
        # Fetch immagine
        content, content_type = await fetch_image_with_retry(url)
        
        # Cache successo
        logo_cache[cache_key] = {
            'content': content,
            'content_type': content_type,
            'cached_at': datetime.now(),
            'success': True
        }
        
        # Per richieste HEAD, restituisci solo headers
        if request.method == "HEAD":
            return Response(
                content=None,
                media_type=content_type,
                headers={
                    'Cache-Control': 'public, max-age=21600',  # 6 ore
                    'X-Cache': 'MISS',
                    'Content-Length': str(len(content))
                }
            )
        
        return Response(
            content=content,
            media_type=content_type,
            headers={
                'Cache-Control': 'public, max-age=21600',  # 6 ore
                'X-Cache': 'MISS'
            }
        )
    
    except Exception as e:
        # Per tutti gli errori, ritorna 204 come fa il backend
        logger.warning(f"Logo fetch failed for {url}: {e}")
        return Response(status_code=204)

@router.get("/logo/status")
async def get_logo_cache_status():
    """Endpoint per monitorare lo stato della cache loghi"""
    
    # Pulisci cache scadute
    current_time = datetime.now()
    
    # Pulisci logo cache
    expired_keys = []
    for key, entry in logo_cache.items():
        if not is_cache_valid(entry):
            expired_keys.append(key)
    
    for key in expired_keys:
        del logo_cache[key]
    
    # Pulisci failure cache
    expired_failures = []
    for key, failure_time in failure_cache.items():
        if current_time > failure_time + timedelta(minutes=30):
            expired_failures.append(key)
    
    for key in expired_failures:
        del failure_cache[key]
    
    return {
        'logo_cache_size': len(logo_cache),
        'failure_cache_size': len(failure_cache),
        'semaphore_available': logo_semaphore._value,
        'cache_stats': {
            'total_entries': len(logo_cache),
            'success_entries': len([e for e in logo_cache.values() if e.get('success', False)]),
            'failure_entries': len(failure_cache)
        }
    }

@router.post("/logo/clear-cache")
async def clear_logo_cache():
    """Endpoint per pulire manualmente la cache loghi"""
    
    global logo_cache, failure_cache
    
    cache_size = len(logo_cache)
    failure_size = len(failure_cache)
    
    logo_cache.clear()
    failure_cache.clear()
    
    return {
        'message': 'Cache cleared successfully',
        'cleared_entries': cache_size,
        'cleared_failures': failure_size
    }