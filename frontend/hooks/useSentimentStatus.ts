import { useGetSentimentStatus } from "@/lib/generated/research/research";
import type { SentimentStatus } from "@/lib/types";

export function useSentimentStatus(ticker: string, enabled: boolean) {
  const result = useGetSentimentStatus(ticker, {
    swr: {
      enabled,
      refreshInterval: 5000,
    },
  });
  return {
    ...result,
    data: (result.data as { data: SentimentStatus } | undefined)?.data,
  };
}
