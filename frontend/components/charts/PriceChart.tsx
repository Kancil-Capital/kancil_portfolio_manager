"use client";

import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries, LineSeries } from "lightweight-charts";
import type { OhlcvBar } from "@/lib/types";

interface Props {
  ohlcv: OhlcvBar[];
}

function computeMA(ohlcv: OhlcvBar[], period: number): { time: string; value: number }[] {
  const result: { time: string; value: number }[] = [];
  for (let i = period - 1; i < ohlcv.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += ohlcv[j].close;
    result.push({ time: ohlcv[i].date, value: sum / period });
  }
  return result;
}

export function PriceChart({ ohlcv }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !ohlcv.length) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#1F2937" },
        textColor: "#9CA3AF",
        fontSize: 11,
        fontFamily: "var(--font-jetbrains-mono), monospace",
      },
      grid: {
        vertLines: { color: "#37415155" },
        horzLines: { color: "#37415155" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: {
        borderColor: "#374151",
        textColor: "#9CA3AF",
      },
      timeScale: {
        borderColor: "#374151",
        timeVisible: false,
        secondsVisible: false,
      },
      autoSize: true,
    });

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10B981",
      downColor: "#EF4444",
      borderUpColor: "#10B981",
      borderDownColor: "#EF4444",
      wickUpColor: "#10B981",
      wickDownColor: "#EF4444",
    });

    candleSeries.setData(
      ohlcv.map((bar) => ({
        time: bar.date,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      }))
    );

    // MA20
    if (ohlcv.length >= 20) {
      const ma20Series = chart.addSeries(LineSeries, {
        color: "#3B82F6",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      ma20Series.setData(computeMA(ohlcv, 20));
    }

    // MA50
    if (ohlcv.length >= 50) {
      const ma50Series = chart.addSeries(LineSeries, {
        color: "#F59E0B",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      ma50Series.setData(computeMA(ohlcv, 50));
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
    };
  }, [ohlcv]);

  return <div ref={containerRef} className="w-full" style={{ height: 280 }} />;
}
