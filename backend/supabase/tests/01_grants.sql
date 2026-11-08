-- Least-privilege grant policy for the public schema (issue #32).
--   anon           nothing
--   authenticated  SELECT only, on tables with a read policy
--   service_role   full access (the backend)
--   functions      EXECUTE for service_role only, with search_path pinned
--   new objects    no grants to anon, authenticated or PUBLIC by default

begin;

create extension if not exists pgtap with schema extensions;

select plan(16);

-- ── Existing objects ───────────────────────────────────────────────────────────

select is_empty(
  $$
    select c.relname
      from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relkind in ('r', 'p', 'v', 'm')
       and has_table_privilege('anon', c.oid,
             'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
  $$,
  'anon has no privileges on any public table or view'
);

select is(
  (select string_agg(c.relname || ':' || p.priv, ',' order by c.relname, p.priv)
     from pg_class c
     join pg_namespace n on n.oid = c.relnamespace
    cross join unnest(array['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'])
          as p(priv)
    where n.nspname = 'public' and c.relkind in ('r', 'p', 'v', 'm')
      and has_table_privilege('authenticated', c.oid, p.priv)),
  'eps_cache:SELECT,tracked_tickers:SELECT',
  'authenticated can only SELECT, and only tables with a read policy'
);

select is_empty(
  $$
    select c.relname, r.rolname
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
     cross join (values ('anon'), ('authenticated')) as r(rolname)
     where n.nspname = 'public' and c.relkind = 'S'
       and has_sequence_privilege(r.rolname, c.oid, 'USAGE,SELECT,UPDATE')
  $$,
  'anon and authenticated have no privileges on public sequences'
);

select is_empty(
  $$
    select p.oid::regprocedure::text, r.rolname
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     cross join (values ('anon'), ('authenticated')) as r(rolname)
     where n.nspname = 'public'
       and has_function_privilege(r.rolname, p.oid, 'EXECUTE')
  $$,
  'anon and authenticated cannot execute any public function'
);

select is_empty(
  $$
    select p.oid::regprocedure::text
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and not exists (select 1 from unnest(p.proconfig) cfg where cfg like 'search_path=%')
  $$,
  'every public function pins its search_path'
);

select is_empty(
  $$
    select c.relname
      from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relkind in ('r', 'p')
       and not has_table_privilege('service_role', c.oid, 'SELECT,INSERT,UPDATE,DELETE')
  $$,
  'service_role (the backend) still has full access to every public table'
);

select ok(
  has_function_privilege('service_role',
    'public.get_articles_paginated(text, text, text, double precision, text, integer, integer)',
    'EXECUTE')
  and has_function_privilege('service_role',
    'public.get_sentiments(text[], timestamp with time zone, timestamp with time zone)',
    'EXECUTE'),
  'service_role can still call the RPC functions'
);

-- ── Real queries as each role ──────────────────────────────────────────────────

set local role anon;
select throws_ok(
  'select 1 from public.tracked_tickers', '42501', null,
  'anon cannot read tracked_tickers'
);
select throws_ok(
  $$ select * from public.get_sentiments(array['NVDA'], now() - interval '1 day', now()) $$,
  '42501', null,
  'anon cannot call get_sentiments'
);
reset role;

set local role authenticated;
select lives_ok(
  'select 1 from public.tracked_tickers',
  'authenticated can read tracked_tickers (read policy)'
);
select throws_ok(
  $$ insert into public.tracked_tickers (ticker) values ('ZZZZ') $$, '42501', null,
  'authenticated cannot insert into tracked_tickers'
);
select throws_ok(
  'select 1 from public.articles', '42501', null,
  'authenticated cannot read articles (no read policy)'
);
reset role;

-- ── New objects get no grants by default ───────────────────────────────────────

create table public._grant_probe (id int);
create sequence public._grant_probe_seq;
create function public._grant_probe_fn() returns int language sql as 'select 1';
create schema _grant_probe_schema;
create function _grant_probe_schema.fn() returns int language sql as 'select 1';

select ok(
  not has_table_privilege('anon', 'public._grant_probe',
        'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
  and not has_table_privilege('authenticated', 'public._grant_probe',
        'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
  and not has_sequence_privilege('anon', 'public._grant_probe_seq', 'USAGE,SELECT,UPDATE')
  and not has_sequence_privilege('authenticated', 'public._grant_probe_seq', 'USAGE,SELECT,UPDATE'),
  'a new public table or sequence gets no grants to anon or authenticated'
);

select ok(
  has_table_privilege('service_role', 'public._grant_probe', 'SELECT,INSERT,UPDATE,DELETE'),
  'a new public table is still usable by service_role'
);

select ok(
  not has_function_privilege('anon', 'public._grant_probe_fn()', 'EXECUTE')
  and not has_function_privilege('authenticated', 'public._grant_probe_fn()', 'EXECUTE'),
  'a new public function is not executable by anon or authenticated'
);

select is_empty(
  $$
    select a.grantee
      from pg_proc p, aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
     where p.oid = '_grant_probe_schema.fn()'::regprocedure
       and a.grantee = 0  -- 0 = PUBLIC
  $$,
  'a new function in any schema (e.g. authz) is not executable by PUBLIC'
);

select * from finish();

rollback;
