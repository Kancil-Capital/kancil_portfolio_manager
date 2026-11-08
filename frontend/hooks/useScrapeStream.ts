"use client";

import { useEffect, useRef, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

export type ScrapeStreamEvent = {
  stage: "analyzing" | "done" | "error";
  article_title: string | null;
  sentiment: number | null;
  articles_done: number;
  articles_total: number | null;
};

type UseScrapeStreamResult = {
  events: ScrapeStreamEvent[];
  isStreaming: boolean;
  articlesAnalyzed: number;
};

/**
 * Connect to WS /api/research/{ticker}/scrape-stream and stream FinBERT progress.
 * JWT is fetched from the active Supabase session and passed as ?token=.
 * Note: WebSocket bypasses the Next.js /api proxy, so it goes direct to
 * NEXT_PUBLIC_API_BASE_URL (http → ws, https → wss).
 *
 * onDone is called once when stage==="done" is received. Polling can then stop.
 */
export function useScrapeStream(
  ticker: string,
  enabled: boolean,
  onDone: () => void,
): UseScrapeStreamResult {
  const [events, setEvents] = useState<ScrapeStreamEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [articlesAnalyzed, setArticlesAnalyzed] = useState(0);
  // Keep onDone stable so the effect doesn't re-run when the caller re-renders
  const onDoneRef = useRef(onDone);
  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (!enabled) return;

    let ws: WebSocket | null = null;
    let cancelled = false;

    async function connect() {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token || cancelled) return;

      const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000")
        .replace(/^https/, "wss")
        .replace(/^http/, "ws");

      ws = new WebSocket(
        `${base}/api/research/${ticker}/scrape-stream?token=${encodeURIComponent(token)}`,
      );

      ws.onopen = () => {
        if (!cancelled) setIsStreaming(true);
      };

      ws.onmessage = (e) => {
        if (cancelled) return;
        try {
          const event: ScrapeStreamEvent = JSON.parse(e.data as string);
          if (event.stage === "analyzing") {
            setEvents((prev) => [...prev, event]);
            setArticlesAnalyzed(event.articles_done);
          } else if (event.stage === "done") {
            setArticlesAnalyzed(event.articles_done);
            setIsStreaming(false);
            onDoneRef.current();
          } else if (event.stage === "error") {
            // The scrape failed; it will be retried on the next visit
            setIsStreaming(false);
          }
        } catch {
          // malformed frame — ignore
        }
      };

      ws.onerror = () => {
        if (!cancelled) setIsStreaming(false);
      };

      ws.onclose = () => {
        if (!cancelled) setIsStreaming(false);
      };
    }

    connect();

    return () => {
      cancelled = true;
      ws?.close();
    };
  }, [ticker, enabled]);

  return { events, isStreaming, articlesAnalyzed };
}
