import { useGetResearch } from "@/lib/generated/research/research";
import type { TickerDeepDive } from "@/lib/types";

export function useTickerData(ticker: string) {
  const result = useGetResearch(ticker);
  return {
    ...result,
    data: (result.data as { data: TickerDeepDive } | undefined)?.data,
    mutate: result.mutate,
  };
}
