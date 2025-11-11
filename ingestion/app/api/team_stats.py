from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

from app.utils.football_api import football_api

router = APIRouter(prefix="/team-stats", tags=["team-stats"])

@router.get("/")
async def get_team_statistics(
    team_name: str = Query(..., description="Nome della squadra"),
    league: Optional[str] = Query(None, description="Nome del campionato"),
    country: Optional[str] = Query(None, description="Paese del campionato")
):
    """
    Recupera statistiche dettagliate per una squadra specifica.

    Questo endpoint permette al backend di ottenere statistiche squadre
    senza dover fare chiamate HTTP dirette (bypassando le restrizioni Railway).
    """
    try:
        logger.info(f"Getting team stats for: {team_name}")

        # Prima cerca l'ID della squadra
        teams_data = await football_api._make_request("teams", {"search": team_name})
        teams = teams_data.get("response", [])

        if not teams:
            raise HTTPException(status_code=404, detail=f"Squadra '{team_name}' non trovata")

        # Prendi la prima squadra trovata
        team_info = teams[0]
        team_id = team_info.get("team", {}).get("id")

        if not team_id:
            raise HTTPException(status_code=404, detail=f"ID squadra non trovato per '{team_name}'")

        # Prepara parametri per le statistiche
        stats_params = {
            "team": team_id,
            "season": 2024  # Stagione corrente
        }

        # Aggiungi filtro campionato se specificato
        if league and country:
            league_data = await football_api._make_request("leagues", {"name": league, "country": country})
            leagues = league_data.get("response", [])

            if leagues:
                league_id = leagues[0].get("league", {}).get("id")
                if league_id:
                    stats_params["league"] = league_id

        # Recupera le statistiche
        stats_data = await football_api._make_request("teams/statistics", stats_params)
        team_stats = stats_data.get("response", {})

        if not team_stats:
            raise HTTPException(status_code=404, detail=f"Statistiche non disponibili per '{team_name}'")

        # Restituisci i dati
        return {
            "success": True,
            "data": team_stats,
            "team_info": {
                "id": team_id,
                "name": team_info.get("team", {}).get("name"),
                "country": team_info.get("team", {}).get("country"),
                "logo": team_info.get("team", {}).get("logo")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team stats for {team_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Errore interno del server: {str(e)}")

