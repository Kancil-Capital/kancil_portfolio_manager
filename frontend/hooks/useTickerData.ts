import useSWR from "swr";
import { api } from "@/lib/api";
import type { TickerDeepDive } from "@/lib/types";

export function useTickerData(ticker: string) {
  return useSWR<TickerDeepDive>(
    ticker ? `/api/research/${ticker}` : null,
    () => api.get<TickerDeepDive>(`/api/research/${ticker}`)
  );
}
