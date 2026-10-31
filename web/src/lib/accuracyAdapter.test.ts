import { describe, expect, it } from 'vitest';

import { toResults, toSummary } from './accuracyAdapter';

const evaluated = {
  success: true,
  period_days: 30,
  total_predictions: 10,
  average_scores: { winner_accuracy: 50, goals_accuracy: 40, overall_accuracy: 45 },
  accuracy_counts: { winner_correct: 5, goals_correct: 4, total_predictions: 10 },
  accuracy_percentages: { winner_accuracy: 50, goals_accuracy: 40 },
};

const noEvaluations = {
  success: true,
  period_days: 30,
  total_predictions: 0,
  average_scores: { winner_accuracy: 0, goals_accuracy: 0, overall_accuracy: 0 },
  accuracy_counts: { winner_correct: 0, goals_correct: 0, total_predictions: 0 },
  note: 'Nessuna valutazione disponibile nel periodo richiesto',
};

const results = {
  success: true,
  total: 1,
  limit: 20,
  offset: 0,
  results: [
    {
      fixture_id: 1,
      fixture_date: '2026-10-31T21:45:00',
      league_name: 'Serie A',
      home_team: 'Torino',
      away_team: 'Como',
      actual_score: '1-0',
      actual_winner: 'home',
      predicted_winner: 'Torino',
      winner_accuracy: true,
      goals_accuracy: false,
      winner_score: 100,
      goals_score: 0,
      overall_score: 50,
      evaluated_at: '2026-10-31T17:50:24',
    },
  ],
};

describe('toSummary', () => {
  it('keeps the numbers of an evaluated period', () => {
    const summary = toSummary(evaluated);
    expect(summary.total_predictions).toBe(10);
    expect(summary.accuracy_percentages.winner_accuracy).toBe(50);
    expect(summary.average_scores.overall_accuracy).toBe(45);
  });

  it('fills the percentages the API omits when nothing was evaluated', () => {
    const summary = toSummary(noEvaluations);
    expect(summary.total_predictions).toBe(0);
    expect(summary.accuracy_percentages.winner_accuracy).toBe(0);
  });

  it.each([{}, null, undefined, 'error'])('survives a malformed response: %s', (raw) => {
    const summary = toSummary(raw);
    expect(summary.success).toBe(false);
    expect(summary.total_predictions).toBe(0);
    expect(summary.accuracy_counts.winner_correct).toBe(0);
  });
});

describe('toResults', () => {
  it('keeps every evaluated match', () => {
    const rows = toResults(results);
    expect(rows).toHaveLength(1);
    expect(rows[0].home_team).toBe('Torino');
    expect(rows[0].overall_score).toBe(50);
    expect(rows[0].winner_accuracy).toBe(true);
  });

  it.each([{}, null, { results: 'x' }, { success: false, results: [] }])('returns no rows for %s', (raw) => {
    expect(toResults(raw)).toEqual([]);
  });
});
