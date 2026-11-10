-- Every table in the app's schemas must have row level security enabled.
-- A table without RLS is readable and writable by anyone holding the public
-- (publishable) key, whatever the backend does.
-- Run with `make db-test` (supabase test db). Each file runs in a transaction
-- that is rolled back.

begin;

create extension if not exists pgtap with schema extensions;

select plan(2);

-- Guard against the check passing vacuously (e.g. wrong schema names)
select cmp_ok(
  (select count(*)::int
     from pg_class c
     join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind in ('r', 'p')),
  '>', 0,
  'public schema has tables to check'
);

select is_empty(
  $$
    select n.nspname || '.' || c.relname
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
     where n.nspname in ('public', 'authz')
       and c.relkind in ('r', 'p')   -- ordinary and partitioned tables
       and not c.relrowsecurity
  $$,
  'every table in public and authz has RLS enabled'
);

select * from finish();

rollback;
