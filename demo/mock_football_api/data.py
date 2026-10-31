"""Synthetic dataset. Club names are real; every number is generated from a seed."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

LEAGUE = {"id": 135, "name": "Serie A", "country": "Italy", "logo": "https://example.invalid/leagues/135.png"}
SEASON = 2025
CLUBS = [
    "Inter", "AC Milan", "Atalanta", "Bologna", "Cagliari", "Como", "Cremonese", "Fiorentina", "Genoa", "Juventus",
    "Lazio", "Lecce", "Napoli", "Parma", "Pisa", "AS Roma", "Sassuolo", "Torino", "Udinese", "Hellas Verona",
]
BOOKMAKERS = {1: "Bookmaker A", 2: "Bookmaker B", 3: "Bookmaker C"}
# Days relative to today that have a full round of ten matches.
ROUND_OFFSETS = (-7, -3, 0, 3, 7, 10)
KICKOFFS = ("15:00", "18:00", "20:45")


def team(name: str) -> dict:
    team_id = CLUBS.index(name) + 1
    return {"id": team_id, "name": name, "logo": f"https://example.invalid/teams/{team_id}.png"}


@dataclass
class Dataset:
    today: date
    fixtures: list[dict] = field(default_factory=list)
    odds: dict[int, dict] = field(default_factory=dict)
    predictions: dict[int, dict] = field(default_factory=dict)
    team_stats: dict[int, dict] = field(default_factory=dict)
    results: dict[int, tuple[int, int, int, int]] = field(default_factory=dict)

    def fixture(self, fixture_id: int) -> dict | None:
        return next((f for f in self.fixtures if f["fixture"]["id"] == fixture_id), None)

    def find_fixture(self, home: str, away: str) -> dict | None:
        names = {home.lower(), away.lower()}
        return next(
            (
                f
                for f in self.fixtures
                if {f["teams"]["home"]["name"].lower(), f["teams"]["away"]["name"].lower()} == names
                and f["fixture"]["date"].startswith(self.today.isoformat())
            ),
            None,
        )

    def finish(self, fixture: dict) -> None:
        """Applies the result already drawn for this match, as if it had just been played."""
        home, away, half_home, half_away = self.results[fixture["fixture"]["id"]]
        fixture["fixture"]["status"] = {"long": "Match Finished", "short": "FT", "elapsed": 90}
        fixture["goals"] = {"home": home, "away": away}
        fixture["score"] = {
            "halftime": {"home": half_home, "away": half_away},
            "fulltime": {"home": home, "away": away},
        }
        fixture["teams"]["home"]["winner"] = home > away if home != away else None
        fixture["teams"]["away"]["winner"] = away > home if home != away else None


def _pairs(offset: int, rng: random.Random) -> list[tuple[str, str]]:
    if offset == 0:
        # The README's example question asks about this match, so it must exist on any day.
        others = [c for c in CLUBS if c not in ("Inter", "AC Milan")]
        rng.shuffle(others)
        return [("Inter", "AC Milan"), *zip(others[::2], others[1::2])]
    clubs = list(CLUBS)
    rng.shuffle(clubs)
    return list(zip(clubs[::2], clubs[1::2]))


def _odds_entry(fixture: dict, rng: random.Random, strength: float) -> dict:
    bookmakers = []
    for book_id, name in BOOKMAKERS.items():
        margin = rng.uniform(1.03, 1.08)
        home_p, draw_p = strength, 0.27
        away_p = max(0.05, 1 - home_p - draw_p)
        bets = [
            {
                "id": 1,
                "name": "Match Winner",
                "values": [
                    {"value": "Home", "odd": f"{1 / (home_p * margin):.2f}"},
                    {"value": "Draw", "odd": f"{1 / (draw_p * margin):.2f}"},
                    {"value": "Away", "odd": f"{1 / (away_p * margin):.2f}"},
                ],
            },
            {
                "id": 12,
                "name": "Double Chance",
                "values": [
                    {"value": "Home/Draw", "odd": f"{1 / ((home_p + draw_p) * margin):.2f}"},
                    {"value": "Home/Away", "odd": f"{1 / ((home_p + away_p) * margin):.2f}"},
                    {"value": "Draw/Away", "odd": f"{1 / ((draw_p + away_p) * margin):.2f}"},
                ],
            },
            {
                "id": 5,
                "name": "Goals Over/Under",
                "values": [
                    {"value": "Over 2.5", "odd": f"{rng.uniform(1.7, 2.2):.2f}"},
                    {"value": "Under 2.5", "odd": f"{rng.uniform(1.7, 2.2):.2f}"},
                ],
            },
        ]
        bookmakers.append({"id": book_id, "name": name, "bets": bets})
    return {
        "league": {**LEAGUE, "season": SEASON},
        "fixture": {"id": fixture["fixture"]["id"], "date": fixture["fixture"]["date"]},
        "update": fixture["fixture"]["date"],
        "bookmakers": bookmakers,
    }


def _prediction_entry(fixture: dict, rng: random.Random, strength: float) -> dict:
    home, away = fixture["teams"]["home"], fixture["teams"]["away"]
    winner = home if strength >= 0.4 else away
    home_percent = round(strength * 100)
    draw_percent = 27
    under = rng.random() < 0.5
    threshold = rng.choice(("2.5", "3.5"))
    return {
        "predictions": {
            "winner": {"id": winner["id"], "name": winner["name"], "comment": "Win or draw"},
            "win_or_draw": rng.random() < 0.6,
            "under_over": f"{'-' if under else '+'}{threshold}",
            "goals": {"home": f"-{rng.choice(('1.5', '2.5'))}", "away": f"-{rng.choice(('0.5', '1.5'))}"},
            "advice": f"Winner : {winner['name']}",
            "percent": {
                "home": f"{home_percent}%",
                "draw": f"{draw_percent}%",
                "away": f"{max(0, 100 - home_percent - draw_percent)}%",
            },
        },
        "league": {**LEAGUE, "season": SEASON},
        "teams": {
            side: {**t, "last_5": {"form": f"{rng.randint(20, 90)}%", "att": f"{rng.randint(20, 90)}%", "def": f"{rng.randint(20, 90)}%"}}
            for side, t in (("home", home), ("away", away))
        },
        "comparison": {"form": {"home": f"{home_percent}%", "away": f"{100 - home_percent}%"}},
        "h2h": [],
    }


def _team_stats(name: str, rng: random.Random) -> dict:
    wins, draws, loses = rng.randint(4, 14), rng.randint(2, 8), rng.randint(2, 10)
    scored, conceded = rng.randint(15, 45), rng.randint(15, 45)
    return {
        "league": {**LEAGUE, "season": SEASON},
        "team": team(name),
        "form": "".join(rng.choice("WDL") for _ in range(5)),
        "fixtures": {
            "played": {"total": wins + draws + loses},
            "wins": {"total": wins},
            "draws": {"total": draws},
            "loses": {"total": loses},
        },
        "goals": {"for": {"total": {"total": scored}}, "against": {"total": {"total": conceded}}},
        "clean_sheet": {"total": rng.randint(1, 10)},
        "failed_to_score": {"total": rng.randint(1, 8)},
        "penalty": {"total": rng.randint(0, 5)},
        "lineups": [],
        "cards": {},
    }


def generate_dataset(seed: int, today: date) -> Dataset:
    rng = random.Random(f"{seed}:{today.isoformat()}")
    dataset = Dataset(today=today)
    for offset in ROUND_OFFSETS:
        day = today + timedelta(days=offset)
        for index, (home, away) in enumerate(_pairs(offset, rng)):
            fixture_id = day.toordinal() * 100 + index
            kickoff = KICKOFFS[index % len(KICKOFFS)]
            fixture = {
                "fixture": {
                    "id": fixture_id,
                    "date": f"{day.isoformat()}T{kickoff}:00+00:00",
                    "status": {"long": "Not Started", "short": "NS", "elapsed": None},
                },
                "league": {**LEAGUE, "season": SEASON, "round": f"Regular Season - {offset + 20}"},
                "teams": {"home": {**team(home), "winner": None}, "away": {**team(away), "winner": None}},
                "goals": {"home": None, "away": None},
                "score": {"halftime": {"home": None, "away": None}, "fulltime": {"home": None, "away": None}},
            }
            dataset.fixtures.append(fixture)
            strength = rng.uniform(0.25, 0.6)
            goals_home, goals_away = rng.randint(0, 4), rng.randint(0, 3)
            dataset.results[fixture_id] = (
                goals_home,
                goals_away,
                rng.randint(0, goals_home),
                rng.randint(0, goals_away),
            )
            dataset.odds[fixture_id] = _odds_entry(fixture, rng, strength)
            dataset.predictions[fixture_id] = _prediction_entry(fixture, rng, strength)
            if offset < 0:
                dataset.finish(fixture)
    for name in CLUBS:
        dataset.team_stats[CLUBS.index(name) + 1] = _team_stats(name, rng)
    return dataset
