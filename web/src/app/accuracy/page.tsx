'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  CheckCircle,
  XCircle,
  TrendingUp,
  Target,
  BarChart3,
  RefreshCw,
  Calendar,
  Trophy,
  Goal,
  Trash2
} from 'lucide-react';
import { toast } from 'sonner';

interface AccuracySummary {
  success: boolean;
  period_days: number;
  total_predictions: number;
  average_scores: {
    winner_accuracy: number;
    goals_accuracy: number;
    overall_accuracy: number;
  };
  accuracy_counts: {
    winner_correct: number;
    goals_correct: number;
    total_predictions: number;
  };
  accuracy_percentages: {
    winner_accuracy: number;
    goals_accuracy: number;
  };
}

interface AccuracyResult {
  fixture_id: number;
  fixture_date: string;
  league_name: string;
  home_team: string;
  away_team: string;
  actual_score: string;
  actual_winner: string;
  predicted_winner: string;
  winner_accuracy: boolean;
  goals_accuracy: boolean;
  winner_score: number;
  goals_score: number;
  overall_score: number;
  evaluated_at: string;
}

export default function AccuracyPage() {
  const [summary, setSummary] = useState<AccuracySummary | null>(null);
  const [results, setResults] = useState<AccuracyResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [cleaning, setCleaning] = useState(false);

  const fetchSummary = async () => {
    try {
      const response = await fetch('/api/football/accuracy/summary?days_back=30');
      const data = await response.json();
      if (data.success) {
        setSummary(data);
      }
    } catch (error) {
      console.error('Error fetching accuracy summary:', error);
    }
  };

  const fetchResults = async () => {
    try {
      const response = await fetch('/api/football/accuracy/results?limit=20');
      const data = await response.json();
      if (data.success) {
        setResults(data.results);
      }
    } catch (error) {
      console.error('Error fetching accuracy results:', error);
    }
  };

  const evaluateAccuracy = async () => {
    setEvaluating(true);
    try {
      const response = await fetch('/api/football/accuracy/collect-and-evaluate?days_back=7', {
        method: 'POST',
      });
      const data = await response.json();

      if (data.success) {
        toast.success('Valutazione accuratezza completata!');
        await fetchSummary();
        await fetchResults();
      } else {
        toast.error('Errore nella valutazione: ' + (data.error || 'Errore sconosciuto'));
      }
    } catch (error) {
      toast.error('Errore di connessione');
      console.error('Error evaluating accuracy:', error);
    } finally {
      setEvaluating(false);
    }
  };

  const cleanupPredictions = async () => {
    setCleaning(true);
    try {
      const response = await fetch('/api/football/cleanup/predictions?days_back=30', {
        method: 'POST',
      });
      const data = await response.json();

      if (data.success) {
        toast.success('Pulizia predizioni completata!');
        // Ricarica i dati per riflettere le modifiche
        await fetchSummary();
      } else {
        toast.error('Errore nella pulizia: ' + (data.error || 'Errore sconosciuto'));
      }
    } catch (error) {
      toast.error('Errore di connessione');
      console.error('Error cleaning predictions:', error);
    } finally {
      setCleaning(false);
    }
  };

  useEffect(() => {
    fetchSummary();
    fetchResults();
  }, []);

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const getAccuracyColor = (percentage: number) => {
    if (percentage >= 70) return 'text-green-600';
    if (percentage >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getAccuracyBadgeVariant = (isAccurate: boolean) => {
    return isAccurate ? 'default' : 'secondary';
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Target className="h-8 w-8" />
            Accuratezza Predizioni
          </h1>
          <p className="text-muted-foreground mt-2">
            Analizza le performance delle predizioni confrontandole con i risultati reali.
            <br />
            <small className="text-xs">
              💡 Le predizioni vengono conservate per 60+ giorni dopo la fine delle partite per permettere la valutazione dell'accuratezza.
            </small>
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            onClick={evaluateAccuracy}
            disabled={evaluating}
            className="flex items-center gap-2"
          >
            {evaluating ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <BarChart3 className="h-4 w-4" />
            )}
            {evaluating ? 'Valutando...' : 'Valuta Accuratezza'}
          </Button>

          <Button
            onClick={cleanupPredictions}
            disabled={cleaning}
            variant="outline"
            className="flex items-center gap-2"
            title="Rimuove predizioni molto vecchie (>90 giorni) e future lontane (>180 giorni). Preserva predizioni per partite finite fino a 60 giorni dopo la valutazione."
          >
            {cleaning ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            {cleaning ? 'Pulendo...' : 'Pulisci Vecchie'}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="summary" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="summary">Riepilogo</TabsTrigger>
          <TabsTrigger value="details">Dettagli</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-6">
          {summary && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {/* Winner Accuracy */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Accuratezza Vincitore</CardTitle>
                  <Trophy className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className={`text-2xl font-bold ${getAccuracyColor(summary.accuracy_percentages.winner_accuracy)}`}>
                    {formatPercentage(summary.accuracy_percentages.winner_accuracy)}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {summary.accuracy_counts.winner_correct} su {summary.total_predictions} predizioni
                  </p>
                  <Progress
                    value={summary.accuracy_percentages.winner_accuracy}
                    className="mt-2"
                  />
                </CardContent>
              </Card>

              {/* Goals Accuracy */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Accuratezza Gol</CardTitle>
                  <Goal className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className={`text-2xl font-bold ${getAccuracyColor(summary.accuracy_percentages.goals_accuracy)}`}>
                    {formatPercentage(summary.accuracy_percentages.goals_accuracy)}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {summary.accuracy_counts.goals_correct} su {summary.total_predictions} predizioni
                  </p>
                  <Progress
                    value={summary.accuracy_percentages.goals_accuracy}
                    className="mt-2"
                  />
                </CardContent>
              </Card>

              {/* Overall Score */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Punteggio Complessivo</CardTitle>
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className={`text-2xl font-bold ${getAccuracyColor(summary.average_scores.overall_accuracy)}`}>
                    {summary.average_scores.overall_accuracy.toFixed(1)}%
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Media di tutte le predizioni
                  </p>
                  <Progress
                    value={summary.average_scores.overall_accuracy}
                    className="mt-2"
                  />
                </CardContent>
              </Card>

              {/* Total Predictions */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Predizioni Analizzate</CardTitle>
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {summary.total_predictions}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Negli ultimi {summary.period_days} giorni
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          {!summary && !loading && (
            <Card>
              <CardContent className="flex items-center justify-center h-32">
                <p className="text-muted-foreground">Nessun dato di accuratezza disponibile</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="details" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Dettagli Predizioni Recenti</CardTitle>
              <CardDescription>
                Elenco dettagliato delle ultime valutazioni di accuratezza
              </CardDescription>
            </CardHeader>
            <CardContent>
              {results.length > 0 ? (
                <div className="space-y-4">
                  {results.map((result) => (
                    <div key={result.fixture_id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-semibold">
                          {result.home_team} vs {result.away_team}
                        </div>
                        <Badge variant="outline">
                          {result.league_name}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">Risultato:</span>
                          <div className="font-medium">{result.actual_score}</div>
                        </div>

                        <div>
                          <span className="text-muted-foreground">Predetto:</span>
                          <div className="font-medium">{result.predicted_winner}</div>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Vincitore:</span>
                          {result.winner_accuracy ? (
                            <CheckCircle className="h-4 w-4 text-green-600" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-600" />
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Gol:</span>
                          {result.goals_accuracy ? (
                            <CheckCircle className="h-4 w-4 text-green-600" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-600" />
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span>Punteggio: {result.overall_score.toFixed(1)}%</span>
                        <span>{new Date(result.fixture_date).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  Nessun risultato di accuratezza disponibile
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
// Force rebuild
