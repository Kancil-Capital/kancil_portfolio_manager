-- Least-privilege grants for the public schema (issue #32).
--
-- The initial schema dump granted ALL on every table, sequence and function in
-- public, current and future, to anon and authenticated. That left RLS as the
-- only barrier: any table created without RLS would be readable and writable
-- with the publishable key.
--
-- Policy from here on:
--   anon           nothing (the app never uses the Data API without a login)
--   authenticated  SELECT only, on tables that have a read policy
--   service_role   unchanged (the backend; it bypasses RLS)
--   functions      EXECUTE for service_role only
--   new objects    no grants to anon, authenticated or PUBLIC. Each migration
--                  grants what it needs explicitly, next to its RLS policies.
--
-- Revokes only: nothing is dropped, and every statement can be undone with the
-- matching GRANT.

-- ── Existing tables ────────────────────────────────────────────────────────────

revoke all on all tables in schema public from anon;
revoke all on all tables in schema public from authenticated;

-- Matches the existing "authenticated read ..." policies
grant select on public.tracked_tickers to authenticated;
grant select on public.eps_cache to authenticated;

-- ── Existing sequences ─────────────────────────────────────────────────────────

revoke all on all sequences in schema public from anon;
revoke all on all sequences in schema public from authenticated;

-- ── Existing functions ─────────────────────────────────────────────────────────
-- Both are SECURITY INVOKER and only called by the backend (service_role).

revoke all on function public.get_articles_paginated(
  text, text, text, double precision, text, integer, integer
) from public, anon, authenticated;
revoke all on function public.get_sentiments(
  text[], timestamp with time zone, timestamp with time zone
) from public, anon, authenticated;

grant execute on function public.get_articles_paginated(
  text, text, text, double precision, text, integer, integer
) to service_role;
grant execute on function public.get_sentiments(
  text[], timestamp with time zone, timestamp with time zone
) to service_role;

-- Pin search_path (Supabase linter: function_search_path_mutable).
-- get_articles_paginated refers to its tables without a schema, so '' would
-- break it; public with pg_temp last is the safe equivalent.
alter function public.get_articles_paginated(
  text, text, text, double precision, text, integer, integer
) set search_path = public, pg_temp;
alter function public.get_sentiments(
  text[], timestamp with time zone, timestamp with time zone
) set search_path = public, pg_temp;

-- ── Future objects ─────────────────────────────────────────────────────────────
-- Objects created by postgres (migrations, Studio, SQL editor). service_role
-- keeps its defaults so the backend can use new tables without extra grants.

alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on functions from anon, authenticated;

-- Postgres also grants EXECUTE on every new function to PUBLIC (which anon and
-- authenticated inherit). This default is global, not per schema, so it also
-- covers new schemas such as authz.
alter default privileges for role postgres
  revoke execute on functions from public;
