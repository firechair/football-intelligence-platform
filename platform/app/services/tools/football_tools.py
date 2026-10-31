"""
Football Tools for LLM Function Calling

Provides tool definitions and implementations for the LLM to autonomously:
- Fetch betting odds from multiple bookmakers
- Get AI predictions for matches
- Search for specific matches
- Retrieve team statistics
"""

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SimpleCache:
    """Simple in-memory cache for tool results."""

    def __init__(self):
        self._cache = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if datetime.now() < expiry:
                return value
            else:
                del self._cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache with TTL in seconds."""
        expiry = datetime.now() + timedelta(seconds=ttl)
        self._cache[key] = (value, expiry)


class FootballTools:
    """
    Football API tools that can be called by the LLM autonomously.

    Each tool follows OpenRouter's function calling format:
    - Defined with name, description, and JSON schema parameters
    - Executed with provided arguments
    - Returns structured data or error messages
    """

    def __init__(self):
        self.cache = SimpleCache()
        self.api_key = settings.FOOTBALL_API_KEY
        self.api_base_url = os.getenv("FOOTBALL_TOOLS_API_BASE_URL", "https://api-football-v1.p.rapidapi.com/v3")

    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """
        Returns tool definitions in OpenRouter function calling format.

        These definitions are sent to the LLM so it can autonomously decide
        when and how to call each tool.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_match_odds",
                    "description": (
                        "Fetch current betting odds for a specific match from multiple bookmakers. "
                        "Use this when the user asks about odds, betting lines, or wants to compare bookmaker prices. "
                        "Returns odds for 1X2, Over/Under, Both Teams to Score, etc."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "match_id": {
                                "type": "string",
                                "description": "The unique identifier of the football match"
                            },
                            "bookmakers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of specific bookmakers to include (e.g., ['Bookmaker A', 'Bookmaker I']). If not provided, returns all available bookmakers."
                            },
                            "bet_type": {
                                "type": "string",
                                "enum": ["1X2", "Over/Under", "BTTS", "Asian Handicap", "all"],
                                "description": "Type of bet to fetch odds for. Use 'all' for comprehensive odds."
                            }
                        },
                        "required": ["match_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_predictions",
                    "description": (
                        "Get AI-powered predictions and statistical analysis for a match. "
                        "Use this when the user asks for predictions, match analysis, who will win, "
                        "or wants to understand the probability of different outcomes. "
                        "Returns confidence scores, form analysis, and head-to-head stats."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "match_id": {
                                "type": "string",
                                "description": "The unique identifier of the football match"
                            },
                            "include_form": {
                                "type": "boolean",
                                "description": "Whether to include recent form analysis (last 5 matches). Defaults to true."
                            },
                            "include_h2h": {
                                "type": "boolean",
                                "description": "Whether to include head-to-head historical data. Defaults to true."
                            }
                        },
                        "required": ["match_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_matches",
                    "description": (
                        "Search for football matches by team name, league, or date. "
                        "Use this when the user mentions a team name, league, or asks about matches on a specific date. "
                        "Returns a list of matching fixtures with basic info."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_name": {
                                "type": "string",
                                "description": "Name of the team to search for (e.g., 'Inter Milan', 'Barcelona')"
                            },
                            "league": {
                                "type": "string",
                                "description": "League name or ID (e.g., 'Serie A', 'Premier League', 'Champions League')"
                            },
                            "date_from": {
                                "type": "string",
                                "description": "Start date in YYYY-MM-DD format. Defaults to today."
                            },
                            "date_to": {
                                "type": "string",
                                "description": "End date in YYYY-MM-DD format. Defaults to 7 days from date_from."
                            },
                            "status": {
                                "type": "string",
                                "enum": ["upcoming", "live", "finished", "all"],
                                "description": "Match status filter. Defaults to 'upcoming'."
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_team_stats",
                    "description": (
                        "Get detailed statistics for a specific team including goals scored/conceded, "
                        "win rate, clean sheets, and performance metrics. "
                        "Use this when the user asks about team performance, statistics, or form."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {
                                "type": "string",
                                "description": "The unique identifier of the team"
                            },
                            "season": {
                                "type": "string",
                                "description": "Season year (e.g., '2024'). Defaults to current season."
                            },
                            "league_id": {
                                "type": "string",
                                "description": "Specific league to get stats for. If not provided, returns stats across all competitions."
                            }
                        },
                        "required": ["team_id"]
                    }
                }
            }
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name with provided arguments.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool

        Returns:
            Dictionary containing either:
            - {"success": True, "data": <result>}
            - {"success": False, "error": <error_message>}
        """
        try:
            logger.info(f"[TOOLS] Executing tool: {tool_name} with args: {arguments}")

            if tool_name == "get_match_odds":
                return await self._get_match_odds(**arguments)
            elif tool_name == "get_predictions":
                return await self._get_predictions(**arguments)
            elif tool_name == "search_matches":
                return await self._search_matches(**arguments)
            elif tool_name == "get_team_stats":
                return await self._get_team_stats(**arguments)
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }

        except Exception as e:
            logger.error(f"[TOOLS] Error executing {tool_name}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }

    async def _get_match_odds(
        self,
        match_id: str,
        bookmakers: Optional[List[str]] = None,
        bet_type: str = "all"
    ) -> Dict[str, Any]:
        """Fetch betting odds for a match."""
        try:
            # Check cache first
            cache_key = f"odds:{match_id}:{bet_type}"
            cached_odds = await self.cache.get(cache_key)

            if cached_odds:
                logger.info(f"[TOOLS] Returning cached odds for match {match_id}")
                return {"success": True, "data": cached_odds, "source": "cache"}

            # Fetch from API
            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/odds",
                    headers=headers,
                    params={"fixture": match_id},
                    timeout=10.0
                )
                response.raise_for_status()

            api_data = response.json()

            # Process and structure the odds data
            if not api_data.get("response"):
                return {
                    "success": False,
                    "error": "No odds data available for this match"
                }

            odds_data = self._process_odds_data(
                api_data["response"],
                bookmakers,
                bet_type
            )

            # Cache for 5 minutes (odds change frequently)
            await self.cache.set(cache_key, odds_data, ttl=300)

            return {"success": True, "data": odds_data, "source": "api"}

        except httpx.HTTPError as e:
            logger.error(f"[TOOLS] HTTP error fetching odds: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to fetch odds: {str(e)}"
            }

    async def _get_predictions(
        self,
        match_id: str,
        include_form: bool = True,
        include_h2h: bool = True
    ) -> Dict[str, Any]:
        """Get AI predictions for a match."""
        try:
            # Check cache
            cache_key = f"predictions:{match_id}:{include_form}:{include_h2h}"
            cached_predictions = await self.cache.get(cache_key)

            if cached_predictions:
                logger.info(f"[TOOLS] Returning cached predictions for match {match_id}")
                return {"success": True, "data": cached_predictions, "source": "cache"}

            # Fetch from API
            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/predictions",
                    headers=headers,
                    params={"fixture": match_id},
                    timeout=10.0
                )
                response.raise_for_status()

            api_data = response.json()

            if not api_data.get("response"):
                return {
                    "success": False,
                    "error": "No predictions available for this match"
                }

            predictions_data = self._process_predictions_data(
                api_data["response"][0],
                include_form,
                include_h2h
            )

            # Cache for 30 minutes
            await self.cache.set(cache_key, predictions_data, ttl=1800)

            return {"success": True, "data": predictions_data, "source": "api"}

        except httpx.HTTPError as e:
            logger.error(f"[TOOLS] HTTP error fetching predictions: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to fetch predictions: {str(e)}"
            }

    async def _search_matches(
        self,
        team_name: Optional[str] = None,
        league: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: str = "upcoming"
    ) -> Dict[str, Any]:
        """Search for matches based on criteria."""
        try:
            # Set default dates if not provided
            if not date_from:
                date_from = datetime.now().strftime("%Y-%m-%d")
            if not date_to:
                date_to = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

            # Build cache key
            cache_key = f"search:{team_name}:{league}:{date_from}:{date_to}:{status}"
            cached_matches = await self.cache.get(cache_key)

            if cached_matches:
                logger.info(f"[TOOLS] Returning cached search results")
                return {"success": True, "data": cached_matches, "source": "cache"}

            # Fetch from API
            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
            }

            params = {
                "from": date_from,
                "to": date_to
            }

            if team_name:
                # First, resolve team name to team ID
                team_id = await self._resolve_team_name(team_name)
                if team_id:
                    params["team"] = team_id

            if league:
                # Resolve league name to league ID
                league_id = await self._resolve_league_name(league)
                if league_id:
                    params["league"] = league_id

            if status != "all":
                status_map = {
                    "upcoming": "NS",  # Not Started
                    "live": "LIVE",
                    "finished": "FT"  # Full Time
                }
                params["status"] = status_map.get(status, "NS")

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/fixtures",
                    headers=headers,
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()

            api_data = response.json()

            if not api_data.get("response"):
                return {
                    "success": True,
                    "data": {"matches": [], "count": 0},
                    "source": "api"
                }

            matches_data = self._process_matches_data(api_data["response"])

            # Cache for 10 minutes
            await self.cache.set(cache_key, matches_data, ttl=600)

            return {"success": True, "data": matches_data, "source": "api"}

        except httpx.HTTPError as e:
            logger.error(f"[TOOLS] HTTP error searching matches: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to search matches: {str(e)}"
            }

    async def _get_team_stats(
        self,
        team_id: str,
        season: Optional[str] = None,
        league_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detailed team statistics."""
        try:
            # Default to current season if not provided
            if not season:
                season = str(datetime.now().year)

            cache_key = f"team_stats:{team_id}:{season}:{league_id}"
            cached_stats = await self.cache.get(cache_key)

            if cached_stats:
                logger.info(f"[TOOLS] Returning cached stats for team {team_id}")
                return {"success": True, "data": cached_stats, "source": "cache"}

            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
            }

            params = {
                "team": team_id,
                "season": season
            }

            if league_id:
                params["league"] = league_id

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/teams/statistics",
                    headers=headers,
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()

            api_data = response.json()

            if not api_data.get("response"):
                return {
                    "success": False,
                    "error": "No statistics available for this team"
                }

            stats_data = self._process_team_stats_data(api_data["response"])

            # Cache for 1 hour (stats don't change frequently)
            await self.cache.set(cache_key, stats_data, ttl=3600)

            return {"success": True, "data": stats_data, "source": "api"}

        except httpx.HTTPError as e:
            logger.error(f"[TOOLS] HTTP error fetching team stats: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to fetch team statistics: {str(e)}"
            }

    # Helper methods for data processing

    def _process_odds_data(
        self,
        raw_odds: List[Dict],
        bookmakers: Optional[List[str]],
        bet_type: str
    ) -> Dict[str, Any]:
        """Process and structure odds data from API response."""
        processed = {
            "match_id": raw_odds[0]["fixture"]["id"],
            "odds_by_bookmaker": [],
            "best_odds": {},
            "timestamp": datetime.now().isoformat()
        }

        for fixture_odds in raw_odds:
            for bookmaker in fixture_odds.get("bookmakers", []):
                # Filter by bookmaker if specified
                if bookmakers and bookmaker["name"] not in bookmakers:
                    continue

                bookmaker_data = {
                    "name": bookmaker["name"],
                    "bets": []
                }

                for bet in bookmaker.get("bets", []):
                    # Filter by bet type if specified
                    if bet_type != "all" and bet["name"] != bet_type:
                        continue

                    bookmaker_data["bets"].append({
                        "type": bet["name"],
                        "values": bet["values"]
                    })

                if bookmaker_data["bets"]:
                    processed["odds_by_bookmaker"].append(bookmaker_data)

        # Calculate best odds for each outcome
        processed["best_odds"] = self._calculate_best_odds(processed["odds_by_bookmaker"])

        return processed

    def _calculate_best_odds(self, bookmakers_data: List[Dict]) -> Dict[str, Any]:
        """Find the best odds across all bookmakers."""
        best_odds = {}

        for bookmaker in bookmakers_data:
            for bet in bookmaker["bets"]:
                bet_type = bet["type"]
                if bet_type not in best_odds:
                    best_odds[bet_type] = {}

                for value in bet["values"]:
                    outcome = value["value"]
                    odd = float(value["odd"])

                    if outcome not in best_odds[bet_type] or odd > best_odds[bet_type][outcome]["odd"]:
                        best_odds[bet_type][outcome] = {
                            "odd": odd,
                            "bookmaker": bookmaker["name"]
                        }

        return best_odds

    def _process_predictions_data(
        self,
        raw_prediction: Dict,
        include_form: bool,
        include_h2h: bool
    ) -> Dict[str, Any]:
        """Process and structure prediction data from API response."""
        processed = {
            "match_id": raw_prediction["predictions"].get("fixture_id"),
            "winner": raw_prediction["predictions"].get("winner"),
            "win_or_draw": raw_prediction["predictions"].get("win_or_draw"),
            "under_over": raw_prediction["predictions"].get("under_over"),
            "goals": raw_prediction["predictions"].get("goals"),
            "advice": raw_prediction["predictions"].get("advice"),
            "comparison": raw_prediction.get("comparison", {}),
            "timestamp": datetime.now().isoformat()
        }

        if include_form and "teams" in raw_prediction:
            processed["form"] = {
                "home": raw_prediction["teams"]["home"].get("last_5", {}),
                "away": raw_prediction["teams"]["away"].get("last_5", {})
            }

        if include_h2h and "h2h" in raw_prediction:
            processed["head_to_head"] = raw_prediction["h2h"]

        return processed

    def _process_matches_data(self, raw_matches: List[Dict]) -> Dict[str, Any]:
        """Process and structure matches data from API response."""
        matches = []

        for match in raw_matches:
            matches.append({
                "match_id": match["fixture"]["id"],
                "date": match["fixture"]["date"],
                "status": match["fixture"]["status"]["long"],
                "league": {
                    "id": match["league"]["id"],
                    "name": match["league"]["name"],
                    "country": match["league"]["country"]
                },
                "home_team": {
                    "id": match["teams"]["home"]["id"],
                    "name": match["teams"]["home"]["name"],
                    "logo": match["teams"]["home"]["logo"]
                },
                "away_team": {
                    "id": match["teams"]["away"]["id"],
                    "name": match["teams"]["away"]["name"],
                    "logo": match["teams"]["away"]["logo"]
                },
                "score": match.get("goals", {})
            })

        return {
            "matches": matches,
            "count": len(matches),
            "timestamp": datetime.now().isoformat()
        }

    def _process_team_stats_data(self, raw_stats: Dict) -> Dict[str, Any]:
        """Process and structure team statistics data from API response."""
        return {
            "team": raw_stats.get("team", {}),
            "league": raw_stats.get("league", {}),
            "form": raw_stats.get("form"),
            "fixtures": raw_stats.get("fixtures", {}),
            "goals": raw_stats.get("goals", {}),
            "clean_sheet": raw_stats.get("clean_sheet", {}),
            "failed_to_score": raw_stats.get("failed_to_score", {}),
            "penalty": raw_stats.get("penalty", {}),
            "lineups": raw_stats.get("lineups", []),
            "cards": raw_stats.get("cards", {}),
            "timestamp": datetime.now().isoformat()
        }

    async def _resolve_team_name(self, team_name: str) -> Optional[str]:
        """Resolve team name to team ID using API search."""
        try:
            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/teams",
                    headers=headers,
                    params={"search": team_name},
                    timeout=10.0
                )
                response.raise_for_status()

            api_data = response.json()

            if api_data.get("response") and len(api_data["response"]) > 0:
                return str(api_data["response"][0]["team"]["id"])

            return None

        except Exception as e:
            logger.error(f"[TOOLS] Error resolving team name: {str(e)}")
            return None

    async def _resolve_league_name(self, league_name: str) -> Optional[str]:
        """Resolve league name to league ID using API search."""
        try:
            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/leagues",
                    headers=headers,
                    params={"search": league_name},
                    timeout=10.0
                )
                response.raise_for_status()

            api_data = response.json()

            if api_data.get("response") and len(api_data["response"]) > 0:
                return str(api_data["response"][0]["league"]["id"])

            return None

        except Exception as e:
            logger.error(f"[TOOLS] Error resolving league name: {str(e)}")
            return None
