// Re-export all types from OpenAPI-generated schemas.
// Run `bun generate` to regenerate after backend changes.
export type {
  OHLCVPoint as OhlcvBar,
  Technicals,
  PriceData,
  SentimentDaily as SentimentDay,
  LagCorrelation,
  SentimentStats,
  KeywordCount as Keyword,
  SentimentData,
  PeadFeatures,
  EarningsHistoryItem,
  PeadSignal,
  ArticleSummary,
  TickerDeepDive,
  SentimentStatus,
  CalendarEvent,
  CalendarResponse,
  ArticleWithTickers,
  NewsResponse,
  TrackedTicker,
  AddTickerRequest,
  UpdateTickerRequest,
  UpdateTickerRequestStatus,
  GetCalendarParams,
  GetNewsParams,
} from "./generated/kancilPortfolioManagerAPI.schemas";

export type TickerStatus = "new" | "tracking" | "held" | "untracked";
