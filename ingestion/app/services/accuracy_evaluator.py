import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models import (
    MatchPredictions,
    FinishedFixtures,
    PredictionAccuracy,
    FixtureTrackingStatus
)
from app.utils.football_api import football_api

logger = logging.getLogger(__name__)

class PredictionAccuracyEvaluator:
    """Servizio per valutare l'accuratezza delle predizioni"""

    def __init__(self, db: Session):
        self.db = db

    async def collect_finished_fixtures(self, days_back: int = 7) -> int:
        """
        Raccoglie i risultati delle partite finite controllando i match con predizioni.
        
        NUOVO APPROCCIO (corretto):
        1. Ottiene fixture_ids dalla tabella match_predictions (solo fixture con predizioni)
        2. Per ogni fixture, chiama l'API per verificare se è finita
        3. Se finita (status=FT), salva il risultato in finished_fixtures
        
        RATE LIMITING:
        - Usa il global rate limiter in football_api.py (1 req/sec, max 2 concurrent)
        - Sistema totale ha limite di 6 req/sec
        - Altri job (fixtures, odds, predictions) usano stesso limiter
        - Processo è sequenziale quindi non causa sovraccarico
        
        Questo è molto più efficiente e affidabile rispetto a richiedere tutte le partite finite per data.
        """
        logger.info(f"Starting collection of finished fixtures for predictions in last {days_back} days")

        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        try:
            # 1. Ottieni fixture_ids dalla tabella MatchPredictions
            predictions = self.db.query(MatchPredictions).filter(
                MatchPredictions.fixture_date >= cutoff_date
            ).all()
            
            if not predictions:
                logger.info("No predictions found in the specified date range")
                return 0
            
            logger.info(f"Found {len(predictions)} predictions to check for finished status")
            logger.info(f"⚠️  This will take approximately {len(predictions)} seconds due to API rate limiting (1 req/sec)")
            
            # 2. Per ogni fixture con predizione, controlla se è finita
            saved_count = 0
            for idx, prediction in enumerate(predictions):
                try:
                    fixture_id = prediction.fixture_id
                    
                    # Verifica se già abbiamo il risultato
                    existing = self.db.query(FinishedFixtures).filter(
                        FinishedFixtures.fixture_id == fixture_id
                    ).first()
                    
                    if existing:
                        continue  # Già salvato
                    
                    # Chiama l'API per ottenere il risultato della partita
                    # NOTA: football_api.get_fixture_results usa il global rate limiter (1 req/sec)
                    fixture_data = await football_api.get_fixture_results(fixture_id)
                    
                    if not fixture_data:
                        continue  # Nessun dato disponibile
                    
                    # Verifica se la partita è finita (status = FT)
                    status = fixture_data.get("fixture", {}).get("status", {}).get("short")
                    if status == "FT":
                        saved = self._save_finished_fixture(fixture_data)
                        if saved:
                            saved_count += 1
                            logger.info(f"Saved finished fixture {fixture_id} ({saved_count}/{len(predictions)})")
                    
                    # Log progress ogni 50 fixtures
                    if (idx + 1) % 50 == 0:
                        logger.info(f"Checked {idx + 1}/{len(predictions)} predictions, saved {saved_count} finished fixtures")
                        
                except Exception as e:
                    logger.error(f"Failed to check fixture {prediction.fixture_id}: {str(e)}")
                    continue
            
            logger.info(f"Finished checking {len(predictions)} predictions, saved {saved_count} finished fixtures")
            return saved_count

        except Exception as e:
            logger.error(f"Failed to collect finished fixtures: {str(e)}")
            return 0

    def _save_finished_fixture(self, fixture_data: Dict[str, Any]) -> bool:
        """Salva un risultato di partita finita nel database"""
        try:
            fixture = fixture_data["fixture"]
            teams = fixture_data["teams"]
            goals = fixture_data["goals"]
            score = fixture_data["score"]

            fixture_id = fixture["id"]

            # Verifica se già esiste
            existing = self.db.query(FinishedFixtures).filter(
                FinishedFixtures.fixture_id == fixture_id
            ).first()

            if existing:
                return False  # Già presente

            # Determina il vincitore
            winner = None
            if goals["home"] > goals["away"]:
                winner = "home"
            elif goals["away"] > goals["home"]:
                winner = "away"
            else:
                winner = "draw"

            finished_fixture = FinishedFixtures(
                fixture_id=fixture_id,
                fixture_date=datetime.fromisoformat(fixture["date"].replace('Z', '+00:00')),
                league_id=fixture_data["league"]["id"],
                league_name=fixture_data["league"]["name"],
                country_name=fixture_data["league"]["country"],
                home_team=teams["home"]["name"],
                away_team=teams["away"]["name"],
                home_score=goals["home"],
                away_score=goals["away"],
                winner=winner,
                halftime_home_score=score["halftime"]["home"] if score.get("halftime") else None,
                halftime_away_score=score["halftime"]["away"] if score.get("halftime") else None,
                total_goals=goals["home"] + goals["away"]
            )

            self.db.add(finished_fixture)
            self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Error saving finished fixture: {str(e)}")
            self.db.rollback()
            return False

    async def evaluate_predictions_accuracy(self, days_back: int = 7) -> int:
        """Valuta l'accuratezza delle predizioni per partite finite"""
        logger.info(f"Starting prediction accuracy evaluation for last {days_back} days")

        # Recupera partite finite con predizioni
        finished_with_predictions = self._get_finished_fixtures_with_predictions(days_back)

        evaluated_count = 0
        for fixture_data in finished_with_predictions:
            try:
                evaluated = await self._evaluate_single_prediction(fixture_data)
                if evaluated:
                    evaluated_count += 1
            except Exception as e:
                logger.error(f"Failed to evaluate prediction for fixture {fixture_data['fixture_id']}: {str(e)}")
                continue

        logger.info(f"Evaluated accuracy for {evaluated_count} predictions")
        return evaluated_count

    def _get_finished_fixtures_with_predictions(self, days_back: int) -> List[Dict[str, Any]]:
        """Recupera partite finite che hanno predizioni associate"""
        cutoff_date = datetime.now() - timedelta(days=days_back)

        # Query per trovare partite finite con predizioni
        results = self.db.query(
            FinishedFixtures.fixture_id,
            FinishedFixtures.fixture_date,
            FinishedFixtures.league_id,
            FinishedFixtures.league_name,
            FinishedFixtures.home_team,
            FinishedFixtures.away_team,
            FinishedFixtures.home_score,
            FinishedFixtures.away_score,
            FinishedFixtures.winner,
            FinishedFixtures.total_goals,
            MatchPredictions.winner_team_id,
            MatchPredictions.winner_team_name,
            MatchPredictions.win_or_draw,
            MatchPredictions.under_over,
            MatchPredictions.goals_home,
            MatchPredictions.goals_away,
            MatchPredictions.advice,
            MatchPredictions.collected_at
        ).join(
            MatchPredictions,
            FinishedFixtures.fixture_id == MatchPredictions.fixture_id
        ).filter(
            FinishedFixtures.fixture_date >= cutoff_date
        ).all()

        # Converte in dizionari
        fixtures_data = []
        for row in results:
            fixtures_data.append({
                'fixture_id': row[0],
                'fixture_date': row[1],
                'league_id': row[2],
                'league_name': row[3],
                'home_team': row[4],
                'away_team': row[5],
                'actual_home_score': row[6],
                'actual_away_score': row[7],
                'actual_winner': row[8],
                'actual_total_goals': row[9],
                'predicted_winner_id': row[10],
                'predicted_winner_name': row[11],
                'predicted_win_or_draw': row[12],
                'predicted_under_over': row[13],
                'predicted_goals_home': row[14],
                'predicted_goals_away': row[15],
                'prediction_advice': row[16],
                'prediction_collected_at': row[17]
            })

        return fixtures_data

    async def _evaluate_single_prediction(self, fixture_data: Dict[str, Any]) -> bool:
        """Valuta l'accuratezza di una singola predizione"""
        fixture_id = fixture_data['fixture_id']

        # Verifica se già valutata
        existing = self.db.query(PredictionAccuracy).filter(
            PredictionAccuracy.fixture_id == fixture_id
        ).first()

        if existing:
            return False  # Già valutata

        try:
            # Calcola accuratezza
            accuracy_data = self._calculate_prediction_accuracy(fixture_data)

            # Salva nel database
            prediction_accuracy = PredictionAccuracy(
                fixture_id=fixture_id,
                actual_home_score=fixture_data['actual_home_score'],
                actual_away_score=fixture_data['actual_away_score'],
                actual_winner=fixture_data['actual_winner'],
                actual_total_goals=fixture_data['actual_total_goals'],
                predicted_winner_id=fixture_data['predicted_winner_id'],
                predicted_winner_name=fixture_data['predicted_winner_name'],
                predicted_win_or_draw=fixture_data['predicted_win_or_draw'],
                predicted_under_over=fixture_data['predicted_under_over'],
                predicted_goals_home=fixture_data['predicted_goals_home'],
                predicted_goals_away=fixture_data['predicted_goals_away'],
                prediction_advice=fixture_data['prediction_advice'],
                winner_accuracy=accuracy_data['winner_accuracy'],
                goals_accuracy=accuracy_data['goals_accuracy'],
                total_goals_accuracy=accuracy_data['total_goals_accuracy'],
                win_draw_accuracy=accuracy_data['win_draw_accuracy'],
                winner_score=accuracy_data['winner_score'],
                goals_score=accuracy_data['goals_score'],
                overall_score=accuracy_data['overall_score'],
                fixture_date=fixture_data['fixture_date'],
                league_id=fixture_data['league_id'],
                league_name=fixture_data['league_name'],
                home_team=fixture_data['home_team'],
                away_team=fixture_data['away_team'],
                prediction_collected_at=fixture_data['prediction_collected_at']
            )

            self.db.add(prediction_accuracy)
            self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Error evaluating prediction for fixture {fixture_id}: {str(e)}")
            self.db.rollback()
            return False

    def _calculate_prediction_accuracy(self, fixture_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calcola l'accuratezza di una predizione"""
        actual_winner = fixture_data['actual_winner']
        actual_total_goals = fixture_data['actual_total_goals']
        predicted_winner_name = fixture_data['predicted_winner_name']
        predicted_under_over = fixture_data['predicted_under_over']
        predicted_win_or_draw = fixture_data['predicted_win_or_draw']

        # Accuratezza vincitore
        winner_accuracy = False
        if predicted_winner_name and actual_winner:
            # Confronto semplificato: controlla se il nome della squadra predetta
            # corrisponde al vincitore reale (case insensitive)
            predicted_team = predicted_winner_name.lower()
            if actual_winner == "home" and predicted_team in fixture_data['home_team'].lower():
                winner_accuracy = True
            elif actual_winner == "away" and predicted_team in fixture_data['away_team'].lower():
                winner_accuracy = True
            elif actual_winner == "draw" and ("draw" in predicted_team or predicted_win_or_draw):
                winner_accuracy = True

        # Accuratezza under/over (2.5 gol)
        goals_accuracy = False
        if predicted_under_over and actual_total_goals is not None:
            if predicted_under_over.lower() == "under" and actual_total_goals < 2.5:
                goals_accuracy = True
            elif predicted_under_over.lower() == "over" and actual_total_goals > 2.5:
                goals_accuracy = True

        # Accuratezza totale gol (confronto esatto)
        total_goals_accuracy = False
        if fixture_data['predicted_goals_home'] and fixture_data['predicted_goals_away']:
            try:
                pred_home = float(fixture_data['predicted_goals_home'].replace('+', '').replace('-', ''))
                pred_away = float(fixture_data['predicted_goals_away'].replace('+', '').replace('-', ''))
                if int(pred_home + pred_away) == actual_total_goals:
                    total_goals_accuracy = True
            except (ValueError, TypeError):
                pass

        # Accuratezza win/draw
        win_draw_accuracy = False
        if predicted_win_or_draw and actual_winner:
            if predicted_win_or_draw and actual_winner in ["home", "away"]:
                win_draw_accuracy = True
            elif not predicted_win_or_draw and actual_winner == "draw":
                win_draw_accuracy = True

        # Punteggi percentuali
        winner_score = 100.0 if winner_accuracy else 0.0
        goals_score = 100.0 if goals_accuracy else 0.0

        # Punteggio complessivo (media ponderata)
        scores = []
        if winner_accuracy is not None:
            scores.append(winner_score)
        if goals_accuracy is not None:
            scores.append(goals_score)

        overall_score = sum(scores) / len(scores) if scores else 0.0

        return {
            'winner_accuracy': winner_accuracy,
            'goals_accuracy': goals_accuracy,
            'total_goals_accuracy': total_goals_accuracy,
            'win_draw_accuracy': win_draw_accuracy,
            'winner_score': winner_score,
            'goals_score': goals_score,
            'overall_score': overall_score
        }

    async def collect_and_evaluate_all(self, days_back: int = 7) -> Dict[str, int]:
        """Raccoglie risultati e valuta accuratezza in un'unica operazione"""
        logger.info(f"Starting complete accuracy evaluation for last {days_back} days")

        # Prima raccogli risultati partite finite
        fixtures_collected = await self.collect_finished_fixtures(days_back)

        # Poi valuta l'accuratezza delle predizioni
        predictions_evaluated = await self.evaluate_predictions_accuracy(days_back)

        result = {
            'fixtures_collected': fixtures_collected,
            'predictions_evaluated': predictions_evaluated
        }

        logger.info(f"Completed accuracy evaluation: {result}")
        return result
