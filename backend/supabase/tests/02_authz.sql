-- Access-control schema (issue #4): permission matrix, group scoping and the
-- anti-escalation rules listed at the top of the authz migration.
-- Uses the users and groups from seed.sql.

begin;

create extension if not exists pgtap with schema extensions;

select * from no_plan();

-- Seeded ids
create temp table ids (name text primary key, id uuid) on commit drop;
insert into ids values
  ('admin',    '11111111-1111-1111-1111-111111111111'),
  ('analyst',  '22222222-2222-2222-2222-222222222222'),
  ('cio',      '33333333-3333-3333-3333-333333333333'),
  ('pm',       '44444444-4444-4444-4444-444444444444'),
  ('analyst2', '55555555-5555-5555-5555-555555555555'),
  ('viewer',   '66666666-6666-6666-6666-666666666666'),
  ('alpha',    'a1a1a1a1-0000-0000-0000-000000000001'),
  ('beta',     'b2b2b2b2-0000-0000-0000-000000000002');
grant select on ids to authenticated;

create function pg_temp.id(p text) returns uuid language sql as
  $$ select id from ids where name = p $$;

-- Act as a logged-in user, the way PostgREST sets it from the JWT
create function pg_temp.login(p text) returns void language sql as $$
  select set_config('request.jwt.claims',
                    json_build_object('sub', (select id from ids where name = p), 'role', 'authenticated')::text,
                    true)
$$;
-- New functions get no EXECUTE for PUBLIC (least-privilege defaults), so grant it
grant execute on function pg_temp.id(text), pg_temp.login(text) to authenticated;

-- ── Rule 1: clients never touch authz data ─────────────────────────────────────

select is_empty(
  $$
    select c.relname, r.rolname
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
     cross join (values ('anon'), ('authenticated')) as r(rolname)
     where n.nspname = 'authz' and c.relkind in ('r', 'p', 'v', 'S')
       and (has_table_privilege(r.rolname, c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')
            or (c.relkind = 'S' and has_sequence_privilege(r.rolname, c.oid, 'USAGE,SELECT,UPDATE')))
  $$,
  'anon and authenticated have no privileges on any authz table or sequence'
);

select is_empty(
  $$ select 1 from pg_namespace where nspname = 'authz' and has_schema_privilege('anon', oid, 'USAGE') $$,
  'anon cannot even see the authz schema'
);

set local role authenticated;
select pg_temp.login('admin');
select throws_ok('select * from authz.user_roles', '42501', null,
  'a logged-in admin still cannot read authz.user_roles directly');
select throws_ok($$ insert into authz.group_members values (pg_temp.id('alpha'), pg_temp.id('admin'), 'pm') $$,
  '42501', null, 'a logged-in admin cannot write group_members directly');
select throws_ok($$ select public.get_principal(pg_temp.id('admin')) $$, '42501', null,
  'authenticated cannot call get_principal');
select throws_ok($$ select public.authz_set_role(pg_temp.id('admin'), pg_temp.id('viewer'), 'member') $$,
  '42501', null, 'authenticated cannot call authz_set_role');
select throws_ok($$ select public.authz_set_membership(pg_temp.id('admin'), pg_temp.id('alpha'), pg_temp.id('viewer'), 'analyst') $$,
  '42501', null, 'authenticated cannot call authz_set_membership');
reset role;

-- ── Permission matrix (has_permission, as each logged-in user) ─────────────────

set local role authenticated;

select pg_temp.login('viewer');
select ok(authz.has_permission('research.read'), 'readonly: research.read');
select ok(not authz.has_permission('tickers.create'), 'readonly: no tickers.create');

select pg_temp.login('analyst');
select ok(authz.has_permission('tickers.create'), 'member: tickers.create');
select ok(not authz.has_permission('users.manage'), 'member: no users.manage');
select ok(not authz.has_permission('groups.read_all'), 'member: no groups.read_all');

select pg_temp.login('admin');
select ok(authz.has_permission('users.manage') and authz.has_permission('groups.manage')
          and authz.has_permission('audit.read'), 'admin: users.manage, groups.manage, audit.read');
select ok(not authz.has_permission('groups.read_all'), 'admin: no groups.read_all');
select ok(not authz.has_permission('dashboard.firm'), 'admin: no dashboard.firm');

select pg_temp.login('cio');
select ok(authz.has_permission('groups.read_all') and authz.has_permission('dashboard.firm')
          and authz.has_permission('users.manage'), 'cio: groups.read_all, dashboard.firm, users.manage');

select set_config('request.jwt.claims', '', true);
select ok(not authz.has_permission('research.read'), 'no logged-in user: no permissions at all');

-- ── Group scoping (has_group_permission) ───────────────────────────────────────

select pg_temp.login('pm');
select ok(authz.has_group_permission(pg_temp.id('alpha'), 'group.watchlist.manage'),
  'PM of Alpha manages the Alpha watchlist');
select ok(authz.has_group_permission(pg_temp.id('alpha'), 'group.members.manage'),
  'PM of Alpha manages Alpha members');
select ok(not authz.has_group_permission(pg_temp.id('beta'), 'group.read'),
  'PM of Alpha cannot read Beta');

select pg_temp.login('analyst');
select ok(authz.has_group_permission(pg_temp.id('alpha'), 'group.read')
          and authz.has_group_permission(pg_temp.id('alpha'), 'group.watchlist.add'),
  'Alpha analyst reads Alpha and adds to its watchlist');
select ok(not authz.has_group_permission(pg_temp.id('alpha'), 'group.watchlist.manage'),
  'Alpha analyst cannot manage the Alpha watchlist');
select ok(not authz.has_group_permission(pg_temp.id('beta'), 'group.read'),
  'Alpha analyst cannot read Beta');

select pg_temp.login('analyst2');
select ok(not authz.has_group_permission(pg_temp.id('alpha'), 'group.read'),
  'Beta analyst cannot read Alpha');

select pg_temp.login('cio');
select ok(authz.has_group_permission(pg_temp.id('alpha'), 'group.read')
          and authz.has_group_permission(pg_temp.id('beta'), 'group.read'),
  'CIO reads every group');
select ok(not authz.has_group_permission(pg_temp.id('alpha'), 'group.watchlist.add'),
  'CIO cannot write to a group they are not in');

select pg_temp.login('admin');
select ok(not authz.has_group_permission(pg_temp.id('alpha'), 'group.read'),
  'admin (CTO) cannot read a group they are not in');

reset role;

-- ── get_principal ──────────────────────────────────────────────────────────────

select is(
  public.get_principal(pg_temp.id('pm')) - 'user_id',
  jsonb_build_object(
    'role', 'member',
    'permissions', jsonb_build_array('research.read', 'tickers.create'),
    'groups', jsonb_build_array(jsonb_build_object(
      'id', pg_temp.id('alpha'), 'slug', 'alpha', 'name', 'Alpha', 'role', 'pm',
      'permissions', jsonb_build_array('group.dashboard', 'group.members.manage', 'group.read',
                                       'group.watchlist.add', 'group.watchlist.manage')))),
  'get_principal returns the PM''s role, permissions and groups'
);

select is(
  public.get_principal('00000000-0000-0000-0000-00000000dead') ->> 'role', 'readonly',
  'a user with no role row is treated as readonly'
);

-- ── Rules 3 and 4: authz_set_role ──────────────────────────────────────────────

select lives_ok($$ select public.authz_set_role(pg_temp.id('admin'), pg_temp.id('viewer'), 'member') $$,
  'admin can set another user to member');
select is((select role::text from authz.user_roles where user_id = pg_temp.id('viewer')), 'member',
  '...and the role changed');
select results_eq(
  $$ select actor, before ->> 'role', after ->> 'role' from authz.audit_log
      where action = 'user_roles.update' and target_user = pg_temp.id('viewer') $$,
  $$ values (pg_temp.id('admin'), 'readonly', 'member') $$,
  '...and the change is audited with the actor, before and after (rule 6)'
);

select throws_ok($$ select public.authz_set_role(pg_temp.id('admin'), pg_temp.id('admin'), 'member') $$,
  '42501', 'You cannot change your own role', 'admin cannot change their own role');
select throws_ok($$ select public.authz_set_role(pg_temp.id('admin'), pg_temp.id('analyst'), 'cio') $$,
  '42501', null, 'admin cannot grant cio through the API');
select throws_ok($$ select public.authz_set_role(pg_temp.id('cio'), pg_temp.id('analyst'), 'admin') $$,
  '42501', null, 'cio cannot grant admin through the API');
select throws_ok($$ select public.authz_set_role(pg_temp.id('admin'), pg_temp.id('cio'), 'readonly') $$,
  '42501', null, 'admin cannot demote the cio through the API');
select throws_ok($$ select public.authz_set_role(pg_temp.id('pm'), pg_temp.id('viewer'), 'readonly') $$,
  '42501', null, 'a PM (member) cannot change global roles');

-- ── Rules 4 and 8: authz_set_membership ────────────────────────────────────────

select lives_ok($$ select public.authz_set_membership(pg_temp.id('admin'), pg_temp.id('alpha'), pg_temp.id('analyst2'), 'analyst') $$,
  'admin can add a user to any group');
select throws_ok($$ select public.authz_set_membership(pg_temp.id('admin'), pg_temp.id('alpha'), pg_temp.id('admin'), 'analyst') $$,
  '42501', 'You cannot change your own group membership', 'admin cannot add themselves to a group');
select throws_ok($$ select public.authz_set_membership(pg_temp.id('cio'), pg_temp.id('beta'), pg_temp.id('cio'), 'pm') $$,
  '42501', null, 'cio cannot add themselves to a group');

select lives_ok($$ select public.authz_set_membership(pg_temp.id('pm'), pg_temp.id('alpha'), pg_temp.id('viewer'), 'analyst') $$,
  'PM adds an analyst to their own group');
select lives_ok($$ select public.authz_set_membership(pg_temp.id('pm'), pg_temp.id('alpha'), pg_temp.id('viewer'), null) $$,
  'PM removes an analyst from their own group');
select throws_ok($$ select public.authz_set_membership(pg_temp.id('pm'), pg_temp.id('alpha'), pg_temp.id('viewer'), 'pm') $$,
  '42501', null, 'PM cannot make someone a PM');
select throws_ok($$ select public.authz_set_membership(pg_temp.id('pm'), pg_temp.id('beta'), pg_temp.id('viewer'), 'analyst') $$,
  '42501', null, 'PM cannot manage another group');
select throws_ok($$ select public.authz_set_membership(pg_temp.id('pm'), pg_temp.id('alpha'), pg_temp.id('pm'), null) $$,
  '42501', null, 'PM cannot remove themselves');
select throws_ok($$ select public.authz_set_membership(pg_temp.id('analyst'), pg_temp.id('alpha'), pg_temp.id('viewer'), 'analyst') $$,
  '42501', null, 'an analyst cannot manage members');

select lives_ok($$ select public.authz_set_membership(pg_temp.id('cio'), pg_temp.id('beta'), pg_temp.id('pm'), 'pm') $$,
  'cio can assign a PM to a group');
select throws_ok($$ select public.authz_set_membership(pg_temp.id('analyst2'), pg_temp.id('beta'), pg_temp.id('pm'), null) $$,
  '42501', null, 'a Beta analyst cannot remove the Beta PM');
select throws_ok($$ select public.authz_set_membership(pg_temp.id('admin'), '00000000-0000-0000-0000-000000000000', pg_temp.id('viewer'), 'analyst') $$,
  'P0002', 'Group not found', 'unknown group is rejected');

-- ── Groups ─────────────────────────────────────────────────────────────────────

select lives_ok($$ select public.authz_create_group(pg_temp.id('admin'), 'Gamma', 'Gamma Fund') $$,
  'admin can create a group (slug is lower-cased)');
select ok(exists (select 1 from authz.groups where slug = 'gamma'), '...and it exists');
select ok(exists (select 1 from authz.audit_log where action = 'groups.insert' and actor = pg_temp.id('admin')),
  '...and its creation is audited');
select throws_ok($$ select public.authz_create_group(pg_temp.id('pm'), 'delta', 'Delta') $$,
  '42501', null, 'a PM cannot create groups');
select throws_ok($$ select public.authz_create_group(pg_temp.id('admin'), 'Bad Slug!', 'Bad') $$,
  '23514', null, 'slugs are validated');

-- ── Rule 3: the guard tells direct sessions from API sessions ──────────────────

select ok(not authz.is_direct_session('authenticator'), 'Data API sessions (authenticator) are not direct');
select ok(not authz.is_direct_session('supabase_auth_admin'), 'Supabase Auth sessions are not direct');
select ok(authz.is_direct_session('postgres'), 'postgres (migrations, SQL editor) is direct');

-- ── Rule 5: the last admin and last cio can't be removed ───────────────────────
-- This test runs as postgres, a direct session, so only the "last" rule applies

select throws_ok($$ delete from authz.user_roles where user_id = pg_temp.id('cio') $$,
  '42501', 'Cannot remove the last user with the cio role', 'the last cio cannot be removed');
select throws_ok($$ update authz.user_roles set role = 'member' where user_id = pg_temp.id('admin') $$,
  '42501', 'Cannot remove the last user with the admin role', 'the last admin cannot be demoted');
select lives_ok($$ update authz.user_roles set role = 'admin' where user_id = pg_temp.id('analyst') $$,
  'a direct session can grant admin (break-glass)');
select lives_ok($$ update authz.user_roles set role = 'member' where user_id = pg_temp.id('admin') $$,
  '...after which the original admin is no longer the last and can be demoted');

-- ── Rule 6: the audit log is append-only ───────────────────────────────────────

select throws_ok('update authz.audit_log set actor = null', '42501', null, 'audit rows cannot be edited');
select throws_ok('delete from authz.audit_log', '42501', null, 'audit rows cannot be deleted');
select throws_ok('truncate authz.audit_log', '42501', null, 'the audit log cannot be truncated');
select ok(exists (select 1 from authz.audit_log where db_user = 'postgres' and actor is null
                   and action = 'user_roles.update' and target_user = pg_temp.id('analyst')),
  'direct database changes are audited too, with no app actor');

-- ── Rule 7: new accounts start as readonly ─────────────────────────────────────

insert into auth.users (instance_id, id, aud, role, email)
values ('00000000-0000-0000-0000-000000000000', '77777777-7777-7777-7777-777777777777',
        'authenticated', 'authenticated', 'new@kancil.test');
select is((select role::text from authz.user_roles where user_id = '77777777-7777-7777-7777-777777777777'),
  'readonly', 'a new account gets the readonly role');

select * from finish();

rollback;
