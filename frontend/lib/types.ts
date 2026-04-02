// Shared TypeScript interfaces matching the FastAPI response models

export interface OhlcvBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Technicals {
  rsi_14: number;
  ma20: number;
  ma50: number;
  pct_above_ma20: number;
  pct_above_ma50: number;
  atr_pct: number;
}

export interface PriceData {
  current: number;
  change_pct: number;
  ohlcv: OhlcvBar[];
  technicals: Technicals;
}

export interface SentimentDay {
  date: string;
  mean: number;
  positive: number;
  neutral: number;
  negative: number;
  count: number;
}

export interface LagCorrelation {
  lag: number;
  correlation: number;
}

export interface SentimentStats {
  mean_30d: number;
  net_sentiment: number;
  total_articles: number;
  sentiment_ratio: number;
  best_lag: number;
  best_lag_correlation: number;
}

export interface Keyword {
  word: string;
  count: number;
}

export interface SentimentData {
  daily: SentimentDay[];
  lag_correlations: LagCorrelation[];
  stats: SentimentStats;
  keywords: Keyword[];
}

export interface PeadFeatures {
  ret_5d_pre: number;
  ret_10d_pre: number;
  ret_20d_pre: number;
  pre_earn_vol_20d: number;
  volume_ratio: number;
  sue: number;
  eps_surprise: number;
  hist_beat_rate: number;
  beat_streak: number;
  rate_regime: number;
  vix_regime: number;
  tnx: number;
  vix: number;
}

export interface EarningsHistoryItem {
  date: string;
  eps_surprise: number;
  sue: number;
  beat: boolean;
}

export interface PeadSignal {
  earnings_date: string;
  days_to_earnings: number;
  outperform_prob_5d: number;
  outperform_prob_10d: number;
  outperform_prob_20d: number;
  best_horizon: number;
  features: PeadFeatures;
  earnings_history: EarningsHistoryItem[];
}

export interface ArticleSummary {
  id: string;
  title: string;
  url: string;
  source: string;
  timestamp: string;
  sentiment: number;
  confidence: number;
}

export type TickerStatus = "new" | "tracking" | "held" | "untracked";

export interface TickerDeepDive {
  ticker: string;
  name: string;
  sector: string;
  status: TickerStatus;
  sentiment_ready: boolean;
  price: PriceData;
  sentiment: SentimentData | null;
  pead: PeadSignal | null;
  articles: ArticleSummary[];
}

export interface SentimentStatus {
  ready: boolean;
  article_count: number;
  estimated_seconds_remaining: number | null;
}

export interface CalendarEvent {
  ticker: string;
  name: string;
  sector: string;
  status: string;
  earnings_date: string;
  days_to_earnings: number;
  sentiment_score: number | null;
  sue: number | null;
  outperform_prob: number | null;
  hist_beat_rate: number | null;
  ret_5d_pre: number | null;
}

export interface CalendarResponse {
  events: CalendarEvent[];
}

export interface ArticleWithTickers extends ArticleSummary {
  tickers: string[];
}

export interface NewsResponse {
  articles: ArticleWithTickers[];
  total: number;
}

export interface TrackedTicker {
  ticker: string;
  status: TickerStatus;
  sentiment_ready: boolean;
  added_by: string | null;
  last_scraped: string | null;
}
