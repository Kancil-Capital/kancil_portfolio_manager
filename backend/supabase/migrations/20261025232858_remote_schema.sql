


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "public"."get_articles_paginated"("p_ticker" "text" DEFAULT NULL::"text", "p_sentiment" "text" DEFAULT NULL::"text", "p_source" "text" DEFAULT NULL::"text", "p_min_confidence" double precision DEFAULT NULL::double precision, "p_sort_by" "text" DEFAULT 'recent'::"text", "p_limit" integer DEFAULT 20, "p_offset" integer DEFAULT 0) RETURNS TABLE("id" bigint, "title" "text", "url" "text", "source" "text", "timestamp" timestamp with time zone, "sentiment" double precision, "confidence" double precision, "tickers" "text"[], "total_count" bigint)
    LANGUAGE "sql" STABLE
    AS $$
  WITH filtered AS (
    SELECT
      a.id,
      a.title,
      a.url,
      a.source,
      a.timestamp,
      s.score      AS sentiment,
      s.confidence AS confidence,
      s.affected   AS ticker
    FROM sentiments s
    INNER JOIN articles a ON a.id = s.article_id
    WHERE
      (p_ticker         IS NULL OR s.affected    = p_ticker)
      AND (p_source     IS NULL OR a.source      = p_source)
      AND (p_min_confidence IS NULL OR s.confidence >= p_min_confidence)
      AND (
        p_sentiment IS NULL
        OR (p_sentiment = 'positive' AND s.score >  0.1)
        OR (p_sentiment = 'negative' AND s.score < -0.1)
        OR (p_sentiment = 'neutral'  AND s.score >= -0.1 AND s.score <= 0.1)
      )
  ),
  grouped AS (
    SELECT
      id, title, url, source, timestamp,
      AVG(sentiment)              AS sentiment,
      AVG(confidence)             AS confidence,
      ARRAY_AGG(DISTINCT ticker)  AS tickers
    FROM filtered
    GROUP BY id, title, url, source, timestamp
  ),
  counted AS (
    SELECT COUNT(*) AS total_count FROM grouped
  )
  SELECT
    g.id, g.title, g.url, g.source, g.timestamp,
    g.sentiment, g.confidence, g.tickers,
    c.total_count
  FROM grouped g, counted c
  ORDER BY
    CASE WHEN p_sort_by = 'oldest'      THEN g.timestamp    END ASC  NULLS LAST,
    CASE WHEN p_sort_by = 'positive'    THEN g.sentiment    END DESC NULLS LAST,
    CASE WHEN p_sort_by = 'negative'    THEN g.sentiment    END ASC  NULLS LAST,
    CASE WHEN p_sort_by = 'impact_desc' THEN ABS(g.sentiment) END DESC NULLS LAST,
    CASE WHEN p_sort_by = 'impact_asc'  THEN ABS(g.sentiment) END ASC  NULLS LAST,
    g.timestamp DESC
  LIMIT p_limit OFFSET p_offset;
$$;


ALTER FUNCTION "public"."get_articles_paginated"("p_ticker" "text", "p_sentiment" "text", "p_source" "text", "p_min_confidence" double precision, "p_sort_by" "text", "p_limit" integer, "p_offset" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_calendar_signals"("days_ahead" integer DEFAULT 30) RETURNS TABLE("ticker" "text", "earnings_date" "date", "days_to_earnings" integer, "sue" double precision, "eps_surprise" double precision, "hist_beat_rate" double precision, "ret_5d_pre" double precision, "outperform_prob_5d" double precision, "outperform_prob_10d" double precision, "outperform_prob_20d" double precision, "best_horizon" smallint)
    LANGUAGE "sql" STABLE
    AS $$
  SELECT DISTINCT ON (p.ticker)
    p.ticker,
    p.earnings_date,
    p.days_to_earnings,
    p.sue,
    p.eps_surprise,
    p.hist_beat_rate,
    p.ret_5d_pre,
    p.outperform_prob_5d,
    p.outperform_prob_10d,
    p.outperform_prob_20d,
    p.best_horizon
  FROM pead_signals p
  INNER JOIN tracked_tickers t ON t.ticker = p.ticker
  WHERE
    t.status IN ('tracking', 'held')
    AND p.earnings_date IS NOT NULL
    AND p.earnings_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + days_ahead)
  ORDER BY p.ticker, p.computed_at DESC;
$$;


ALTER FUNCTION "public"."get_calendar_signals"("days_ahead" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_sentiments"("keywords" "text"[], "start_date" timestamp with time zone, "end_date" timestamp with time zone) RETURNS TABLE("affected" "text", "sentiment" real, "confidence" real, "a_timestamp" timestamp with time zone, "title" "text", "body" "text", "author" "text", "source" "text", "url" "text")
    LANGUAGE "sql"
    AS $$
  SELECT DISTINCT ON (s.article_id)
    s.affected,
    s.score,
    s.confidence,
    a.timestamp,
    a.title,
    a.body,
    a.author,
    a.source,
    a.url
  FROM public.sentiments s
  JOIN public.articles a ON a.id = s.article_id
  WHERE s.affected = ANY(keywords)
    AND a.timestamp BETWEEN start_date AND end_date
  ORDER BY s.article_id, a.timestamp ASC;
$$;


ALTER FUNCTION "public"."get_sentiments"("keywords" "text"[], "start_date" timestamp with time zone, "end_date" timestamp with time zone) OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."pead_signals" (
    "ticker" "text" NOT NULL,
    "computed_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "earnings_date" "date",
    "days_to_earnings" integer,
    "ret_5d_pre" double precision,
    "ret_10d_pre" double precision,
    "ret_20d_pre" double precision,
    "pre_earn_vol_20d" double precision,
    "volume_ratio" double precision,
    "rolling_beta_60d" double precision,
    "sector_rs_20d" double precision,
    "eps_surprise" double precision,
    "sue" double precision,
    "hist_beat_rate" double precision,
    "beat_streak" integer,
    "lagged_surprise" double precision,
    "rate_regime" smallint,
    "vix_regime" smallint,
    "tnx" double precision,
    "vix" double precision,
    "outperform_prob_5d" double precision,
    "outperform_prob_10d" double precision,
    "outperform_prob_20d" double precision,
    "best_horizon" smallint,
    CONSTRAINT "pead_signals_best_horizon_check" CHECK (("best_horizon" = ANY (ARRAY[5, 10, 20]))),
    CONSTRAINT "pead_signals_rate_regime_check" CHECK (("rate_regime" = ANY (ARRAY[0, 1]))),
    CONSTRAINT "pead_signals_vix_regime_check" CHECK (("vix_regime" = ANY (ARRAY[0, 1])))
);


ALTER TABLE "public"."pead_signals" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."latest_pead_signals"() RETURNS SETOF "public"."pead_signals"
    LANGUAGE "sql" STABLE
    AS $$
  SELECT DISTINCT ON (ticker) *
  FROM pead_signals
  ORDER BY ticker, computed_at DESC;
$$;


ALTER FUNCTION "public"."latest_pead_signals"() OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."articles" (
    "id" bigint NOT NULL,
    "timestamp" timestamp with time zone DEFAULT "now"() NOT NULL,
    "title" "text" NOT NULL,
    "body" "text" NOT NULL,
    "author" "text" NOT NULL,
    "source" "text" NOT NULL,
    "url" "text" NOT NULL
);


ALTER TABLE "public"."articles" OWNER TO "postgres";


COMMENT ON TABLE "public"."articles" IS 'This is a duplicate of articles0';



ALTER TABLE "public"."articles" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."articles_id_seq1"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."eps_cache" (
    "ticker" "text" NOT NULL,
    "fiscal_date" "date" NOT NULL,
    "earnings_date" "date",
    "reported_eps" double precision,
    "estimated_eps" double precision,
    "eps_surprise" double precision,
    "eps_surprise_pct" double precision,
    "sue" double precision,
    "fetched_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."eps_cache" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."sentiments" (
    "article_id" bigint NOT NULL,
    "affected" "text" NOT NULL,
    "score" real NOT NULL,
    "confidence" real NOT NULL
);


ALTER TABLE "public"."sentiments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."tracked_tickers" (
    "ticker" "text" NOT NULL,
    "added_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "added_by" "text",
    "status" "text" DEFAULT 'tracking'::"text" NOT NULL,
    "sentiment_ready" boolean DEFAULT false NOT NULL,
    "last_scraped" timestamp with time zone,
    "name" "text",
    "sector" "text",
    "region" "text",
    "country" "text",
    CONSTRAINT "tracked_tickers_status_check" CHECK (("status" = ANY (ARRAY['new'::"text", 'tracking'::"text", 'held'::"text", 'untracked'::"text"])))
);


ALTER TABLE "public"."tracked_tickers" OWNER TO "postgres";


ALTER TABLE ONLY "public"."articles"
    ADD CONSTRAINT "articles_pkey1" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."articles"
    ADD CONSTRAINT "articles_url_key1" UNIQUE ("url");



ALTER TABLE ONLY "public"."eps_cache"
    ADD CONSTRAINT "eps_cache_pkey" PRIMARY KEY ("ticker", "fiscal_date");



ALTER TABLE ONLY "public"."pead_signals"
    ADD CONSTRAINT "pead_signals_pkey" PRIMARY KEY ("ticker", "computed_at");



ALTER TABLE ONLY "public"."sentiments"
    ADD CONSTRAINT "sentiments_pkey" PRIMARY KEY ("article_id", "affected");



ALTER TABLE ONLY "public"."tracked_tickers"
    ADD CONSTRAINT "tracked_tickers_pkey" PRIMARY KEY ("ticker");



CREATE INDEX "articles_timestamp_idx1" ON "public"."articles" USING "btree" ("timestamp");



CREATE INDEX "idx_eps_cache_fetched_at" ON "public"."eps_cache" USING "btree" ("fetched_at");



CREATE INDEX "idx_eps_cache_ticker" ON "public"."eps_cache" USING "btree" ("ticker");



CREATE INDEX "idx_pead_signals_earnings_date" ON "public"."pead_signals" USING "btree" ("earnings_date") WHERE ("earnings_date" IS NOT NULL);



CREATE INDEX "idx_pead_signals_ticker_time" ON "public"."pead_signals" USING "btree" ("ticker", "computed_at" DESC);



CREATE INDEX "idx_tracked_tickers_status" ON "public"."tracked_tickers" USING "btree" ("status");



CREATE INDEX "sentiments_affected_idx" ON "public"."sentiments" USING "btree" ("affected");



ALTER TABLE ONLY "public"."sentiments"
    ADD CONSTRAINT "sentiments_article_id_fkey" FOREIGN KEY ("article_id") REFERENCES "public"."articles"("id") ON UPDATE CASCADE;



ALTER TABLE "public"."articles" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "authenticated read eps_cache" ON "public"."eps_cache" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "authenticated read pead_signals" ON "public"."pead_signals" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "authenticated read tracked_tickers" ON "public"."tracked_tickers" FOR SELECT TO "authenticated" USING (true);



ALTER TABLE "public"."eps_cache" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."pead_signals" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."sentiments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."tracked_tickers" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";

























































































































































GRANT ALL ON FUNCTION "public"."get_articles_paginated"("p_ticker" "text", "p_sentiment" "text", "p_source" "text", "p_min_confidence" double precision, "p_sort_by" "text", "p_limit" integer, "p_offset" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_articles_paginated"("p_ticker" "text", "p_sentiment" "text", "p_source" "text", "p_min_confidence" double precision, "p_sort_by" "text", "p_limit" integer, "p_offset" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_articles_paginated"("p_ticker" "text", "p_sentiment" "text", "p_source" "text", "p_min_confidence" double precision, "p_sort_by" "text", "p_limit" integer, "p_offset" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."get_calendar_signals"("days_ahead" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_calendar_signals"("days_ahead" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_calendar_signals"("days_ahead" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."get_sentiments"("keywords" "text"[], "start_date" timestamp with time zone, "end_date" timestamp with time zone) TO "anon";
GRANT ALL ON FUNCTION "public"."get_sentiments"("keywords" "text"[], "start_date" timestamp with time zone, "end_date" timestamp with time zone) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_sentiments"("keywords" "text"[], "start_date" timestamp with time zone, "end_date" timestamp with time zone) TO "service_role";



GRANT ALL ON TABLE "public"."pead_signals" TO "anon";
GRANT ALL ON TABLE "public"."pead_signals" TO "authenticated";
GRANT ALL ON TABLE "public"."pead_signals" TO "service_role";



GRANT ALL ON FUNCTION "public"."latest_pead_signals"() TO "anon";
GRANT ALL ON FUNCTION "public"."latest_pead_signals"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."latest_pead_signals"() TO "service_role";


















GRANT ALL ON TABLE "public"."articles" TO "anon";
GRANT ALL ON TABLE "public"."articles" TO "authenticated";
GRANT ALL ON TABLE "public"."articles" TO "service_role";



GRANT ALL ON SEQUENCE "public"."articles_id_seq1" TO "anon";
GRANT ALL ON SEQUENCE "public"."articles_id_seq1" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."articles_id_seq1" TO "service_role";



GRANT ALL ON TABLE "public"."eps_cache" TO "anon";
GRANT ALL ON TABLE "public"."eps_cache" TO "authenticated";
GRANT ALL ON TABLE "public"."eps_cache" TO "service_role";



GRANT ALL ON TABLE "public"."sentiments" TO "anon";
GRANT ALL ON TABLE "public"."sentiments" TO "authenticated";
GRANT ALL ON TABLE "public"."sentiments" TO "service_role";



GRANT ALL ON TABLE "public"."tracked_tickers" TO "anon";
GRANT ALL ON TABLE "public"."tracked_tickers" TO "authenticated";
GRANT ALL ON TABLE "public"."tracked_tickers" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";































