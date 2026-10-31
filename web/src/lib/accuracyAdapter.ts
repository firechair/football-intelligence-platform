// The accuracy API omits some fields when nothing has been evaluated yet, and the page reads them unconditionally.
export interface AccuracySummary {
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

export interface AccuracyResult {
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

type Raw = Record<string, any>;

const asObject = (raw: unknown): Raw => (raw !== null && typeof raw === 'object' ? (raw as Raw) : {});
const asNumber = (value: unknown): number => (typeof value === 'number' ? value : 0);

export function toSummary(raw: unknown): AccuracySummary {
  const data = asObject(raw);
  const averages = asObject(data.average_scores);
  const counts = asObject(data.accuracy_counts);
  const percentages = asObject(data.accuracy_percentages);
  return {
    success: data.success === true,
    period_days: asNumber(data.period_days),
    total_predictions: asNumber(data.total_predictions),
    average_scores: {
      winner_accuracy: asNumber(averages.winner_accuracy),
      goals_accuracy: asNumber(averages.goals_accuracy),
      overall_accuracy: asNumber(averages.overall_accuracy),
    },
    accuracy_counts: {
      winner_correct: asNumber(counts.winner_correct),
      goals_correct: asNumber(counts.goals_correct),
      total_predictions: asNumber(counts.total_predictions),
    },
    accuracy_percentages: {
      winner_accuracy: asNumber(percentages.winner_accuracy),
      goals_accuracy: asNumber(percentages.goals_accuracy),
    },
  };
}

export function toResults(raw: unknown): AccuracyResult[] {
  const { results } = asObject(raw);
  return Array.isArray(results) ? (results as AccuracyResult[]) : [];
}
