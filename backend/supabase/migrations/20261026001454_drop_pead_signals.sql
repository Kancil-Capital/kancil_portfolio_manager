-- PEAD signals are now computed on demand and cached in memory by
-- services/pead_service.py, so the stored table and its nightly refresh are gone.

-- Neither function is called by the backend; latest_pead_signals() returns
-- SETOF pead_signals, so both must go before the table.
DROP FUNCTION IF EXISTS public.get_calendar_signals(integer);
DROP FUNCTION IF EXISTS public.latest_pead_signals();

-- Drops its indexes and RLS policy with it.
DROP TABLE IF EXISTS public.pead_signals;
