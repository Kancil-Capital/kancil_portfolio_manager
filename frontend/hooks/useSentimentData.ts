import { useGetTickerSentiment } from "@/lib/generated/research/research";
import type { SentimentData } from "@/lib/types";

export function useSentimentData(ticker: string, minConfidence: number) {
  const params = minConfidence > 0 ? { min_confidence: minConfidence } : undefined;
  const result = useGetTickerSentiment(ticker, params);
  return {
    ...result,
    data: (result.data as { data: SentimentData } | undefined)?.data,
  };
}
