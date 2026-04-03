import useSWR from "swr";
import { api } from "@/lib/api";
import type { SentimentStatus } from "@/lib/types";

export function useSentimentStatus(ticker: string, enabled: boolean) {
  return useSWR<SentimentStatus>(
    enabled ? `/api/research/${ticker}/sentiment-status` : null,
    () => api.get<SentimentStatus>(`/api/research/${ticker}/sentiment-status`),
    { refreshInterval: 5000 }
  );
}
