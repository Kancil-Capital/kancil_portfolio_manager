-- Access control: roles, groups, memberships, permissions, audit log (issue #4).
--
-- Global role, one per user (authz.user_roles):
--   admin     CTO: accounts, groups, audit, firm-wide ticker management
--   cio       CIO: everything admin has, plus read access to every group and
--             the firm-wide dashboard
--   member    investment team (PMs, analysts); what they see comes from groups
--   readonly  default for new accounts: research only
-- Group role, per membership (authz.group_members):
--   pm        runs the group: watchlist, dashboard, and its analysts
--   analyst   reads the group and adds to its watchlist
--
-- Anti-escalation rules (each has a test in supabase/tests/02_authz.sql):
--   1. Clients never touch authz data: the schema isn't exposed through the
--      Data API, its tables have RLS on and no grants.
--   2. Changes go through public.authz_* functions, callable by service_role
--      (the backend) only.
--   3. admin and cio can be granted, changed or removed only from a direct
--      database session (migration, SQL editor, psql), never through the API.
--   4. No self-service: nobody changes their own role or memberships.
--   5. The last admin and the last cio can't be removed.
--   6. Every role, membership and group change is written to the audit log,
--      which is append-only.
--   7. New accounts start as readonly.
--   8. PMs manage only their own group's analysts. Only users with
--      groups.manage (admin, cio) create groups or assign PMs.

-- ── Schema ─────────────────────────────────────────────────────────────────────
-- Not in config.toml [api] schemas, so PostgREST doesn't serve it.

create schema authz;
revoke all on schema authz from public;
-- authenticated needs USAGE to call has_permission()/has_group_permission()
-- from RLS policies on future content tables
grant usage on schema authz to authenticated, service_role;

create type authz.app_role as enum ('admin', 'cio', 'member', 'readonly');
create type authz.group_role as enum ('pm', 'analyst');

-- ── Tables ─────────────────────────────────────────────────────────────────────

create table authz.permissions (
  key         text primary key,
  scope       text not null check (scope in ('global', 'group')),
  description text not null
);

create table authz.role_permissions (
  role       authz.app_role not null,
  permission text not null references authz.permissions (key) on delete cascade,
  primary key (role, permission)
);

create table authz.group_role_permissions (
  role       authz.group_role not null,
  permission text not null references authz.permissions (key) on delete cascade,
  primary key (role, permission)
);

create table authz.user_roles (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  role       authz.app_role not null default 'readonly',
  updated_at timestamptz not null default now(),
  updated_by uuid  -- the actor; no FK so the history survives their account
);

create table authz.groups (
  id         uuid primary key default gen_random_uuid(),
  slug       text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{0,39}$'),
  name       text not null check (length(trim(name)) between 1 and 80),
  created_at timestamptz not null default now(),
  created_by uuid
);

create table authz.group_members (
  group_id uuid not null references authz.groups (id) on delete cascade,
  user_id  uuid not null references auth.users (id) on delete cascade,
  role     authz.group_role not null,
  added_at timestamptz not null default now(),
  added_by uuid,
  primary key (group_id, user_id)
);
create index group_members_user_id_idx on authz.group_members (user_id);

create table authz.audit_log (
  id          bigint generated always as identity primary key,
  at          timestamptz not null default now(),
  actor       uuid,                            -- app user who made the change; null for direct DB changes
  db_user     name not null default session_user,
  action      text not null,                   -- e.g. user_roles.update
  target_user uuid,
  group_id    uuid,
  before      jsonb,
  after       jsonb
);
create index audit_log_target_user_idx on authz.audit_log (target_user);
create index audit_log_at_idx on authz.audit_log (at desc);

alter table authz.permissions enable row level security;
alter table authz.role_permissions enable row level security;
alter table authz.group_role_permissions enable row level security;
alter table authz.user_roles enable row level security;
alter table authz.groups enable row level security;
alter table authz.group_members enable row level security;
alter table authz.audit_log enable row level security;

revoke all on all tables in schema authz from public, anon, authenticated, service_role;
revoke all on all sequences in schema authz from public, anon, authenticated, service_role;

-- ── Internal helpers (not granted to any API role) ─────────────────────────────

-- A direct database session (migration, SQL editor, psql) as opposed to the Data
-- API (authenticator) or Supabase Auth (supabase_auth_admin). session_user, not
-- current_user: inside SECURITY DEFINER functions current_user is the owner.
create function authz.is_direct_session(p_session_user name default session_user)
returns boolean
language sql stable
set search_path = ''
as $$ select p_session_user in ('postgres', 'supabase_admin') $$;

-- The app user behind the current change, set by the authz_* functions
create function authz.current_actor()
returns uuid
language sql stable
set search_path = ''
as $$ select nullif(current_setting('authz.actor', true), '')::uuid $$;

create function authz.user_role(p_user uuid)
returns authz.app_role
language sql stable security definer
set search_path = ''
as $$
  select coalesce(
    (select ur.role from authz.user_roles ur where ur.user_id = p_user),
    'readonly'::authz.app_role
  )
$$;

create function authz.user_has_permission(p_user uuid, p_permission text)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select p_user is not null and exists (
    select 1 from authz.role_permissions rp
     where rp.role = authz.user_role(p_user) and rp.permission = p_permission
  )
$$;

-- groups.read_all (CIO) implies group.read on every group, and nothing more
create function authz.user_has_group_permission(p_user uuid, p_group uuid, p_permission text)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select p_user is not null and (
    exists (
      select 1
        from authz.group_members gm
        join authz.group_role_permissions grp on grp.role = gm.role
       where gm.user_id = p_user and gm.group_id = p_group and grp.permission = p_permission
    )
    or (p_permission = 'group.read'
        and exists (select 1 from authz.groups g where g.id = p_group)
        and authz.user_has_permission(p_user, 'groups.read_all'))
  )
$$;

-- ── For RLS policies (authenticated) ───────────────────────────────────────────

create function authz.has_permission(p_permission text)
returns boolean
language sql stable security definer
set search_path = ''
as $$ select authz.user_has_permission(auth.uid(), p_permission) $$;

create function authz.has_group_permission(p_group uuid, p_permission text)
returns boolean
language sql stable security definer
set search_path = ''
as $$ select authz.user_has_group_permission(auth.uid(), p_group, p_permission) $$;

-- ── Triggers ───────────────────────────────────────────────────────────────────

-- Rules 3 and 5
create function authz.guard_user_roles()
returns trigger
language plpgsql
security definer  -- reads user_roles even when the change cascades from auth.users
set search_path = ''
as $$
begin
  if not authz.is_direct_session() then
    if tg_op in ('INSERT', 'UPDATE') and new.role in ('admin', 'cio') then
      raise exception 'The % role can only be granted from a direct database session', new.role
        using errcode = '42501';
    end if;
    if tg_op in ('UPDATE', 'DELETE') and old.role in ('admin', 'cio') then
      raise exception 'A user with the % role can only be changed from a direct database session', old.role
        using errcode = '42501';
    end if;
  end if;

  if tg_op = 'DELETE' or (tg_op = 'UPDATE' and new.role is distinct from old.role) then
    if old.role in ('admin', 'cio') and not exists (
      select 1 from authz.user_roles ur where ur.role = old.role and ur.user_id <> old.user_id
    ) then
      raise exception 'Cannot remove the last user with the % role', old.role
        using errcode = '42501';
    end if;
  end if;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end
$$;

create trigger guard_user_roles
  before insert or update or delete on authz.user_roles
  for each row execute function authz.guard_user_roles();

-- Rule 6: one generic audit trigger for user_roles, group_members and groups
create function authz.audit_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_row jsonb := coalesce(to_jsonb(new), to_jsonb(old));
begin
  insert into authz.audit_log (actor, action, target_user, group_id, before, after)
  values (
    authz.current_actor(),
    tg_table_name || '.' || lower(tg_op),
    (v_row ->> 'user_id')::uuid,
    coalesce((v_row ->> 'group_id')::uuid, case when tg_table_name = 'groups' then (v_row ->> 'id')::uuid end),
    case when tg_op <> 'INSERT' then to_jsonb(old) end,
    case when tg_op <> 'DELETE' then to_jsonb(new) end
  );
  return null;
end
$$;

create trigger audit_user_roles
  after insert or update or delete on authz.user_roles
  for each row execute function authz.audit_change();
create trigger audit_group_members
  after insert or update or delete on authz.group_members
  for each row execute function authz.audit_change();
create trigger audit_groups
  after insert or update or delete on authz.groups
  for each row execute function authz.audit_change();

-- The audit log is append-only, for every session
create function authz.audit_log_append_only()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'authz.audit_log is append-only' using errcode = '42501';
end
$$;

create trigger audit_log_no_update_delete
  before update or delete on authz.audit_log
  for each row execute function authz.audit_log_append_only();
create trigger audit_log_no_truncate
  before truncate on authz.audit_log
  for each statement execute function authz.audit_log_append_only();

-- Rule 7: every new account starts as readonly
create function authz.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into authz.user_roles (user_id) values (new.id) on conflict (user_id) do nothing;
  return new;
end
$$;

create trigger on_auth_user_created_authz
  after insert on auth.users
  for each row execute function authz.handle_new_user();

-- ── Backend API (service_role only) ────────────────────────────────────────────

-- Role, groups and permissions for one user; the backend caches it briefly
create function public.get_principal(p_user uuid)
returns jsonb
language sql stable security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'user_id', p_user,
    'role', authz.user_role(p_user),
    'permissions', coalesce((
      select jsonb_agg(rp.permission order by rp.permission)
        from authz.role_permissions rp
       where rp.role = authz.user_role(p_user)
    ), '[]'::jsonb),
    'groups', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', g.id,
               'slug', g.slug,
               'name', g.name,
               'role', gm.role,
               'permissions', (
                 select coalesce(jsonb_agg(grp.permission order by grp.permission), '[]'::jsonb)
                   from authz.group_role_permissions grp where grp.role = gm.role
               )
             ) order by g.name)
        from authz.group_members gm
        join authz.groups g on g.id = gm.group_id
       where gm.user_id = p_user
    ), '[]'::jsonb)
  )
$$;

-- Set another user's global role to member or readonly
create function public.authz_set_role(p_actor uuid, p_target uuid, p_role authz.app_role)
returns void
language plpgsql security definer
set search_path = ''
as $$
begin
  if p_actor is null or p_target is null or p_role is null then
    raise exception 'actor, target and role are required' using errcode = '22004';
  end if;
  if p_actor = p_target then
    raise exception 'You cannot change your own role' using errcode = '42501';
  end if;
  if not authz.user_has_permission(p_actor, 'users.manage') then
    raise exception 'Changing roles needs the users.manage permission' using errcode = '42501';
  end if;
  if p_role in ('admin', 'cio') or authz.user_role(p_target) in ('admin', 'cio') then
    raise exception 'admin and cio roles can only be changed from a direct database session'
      using errcode = '42501';
  end if;

  perform set_config('authz.actor', p_actor::text, true);
  insert into authz.user_roles (user_id, role, updated_at, updated_by)
  values (p_target, p_role, now(), p_actor)
  on conflict (user_id) do update
    set role = excluded.role, updated_at = now(), updated_by = excluded.updated_by;
end
$$;

-- Add, change or remove (p_role null) a group membership
create function public.authz_set_membership(
  p_actor uuid, p_group uuid, p_target uuid, p_role authz.group_role
)
returns void
language plpgsql security definer
set search_path = ''
as $$
declare
  v_current authz.group_role;
begin
  if p_actor is null or p_group is null or p_target is null then
    raise exception 'actor, group and target are required' using errcode = '22004';
  end if;
  if p_actor = p_target then
    raise exception 'You cannot change your own group membership' using errcode = '42501';
  end if;
  if not exists (select 1 from authz.groups g where g.id = p_group) then
    raise exception 'Group not found' using errcode = 'P0002';
  end if;

  select gm.role into v_current
    from authz.group_members gm where gm.group_id = p_group and gm.user_id = p_target;

  if authz.user_has_permission(p_actor, 'groups.manage') then
    null;  -- admin and cio manage any membership
  elsif authz.user_has_group_permission(p_actor, p_group, 'group.members.manage') then
    -- A PM manages their own group's analysts, nothing else
    if p_role = 'pm' or v_current = 'pm' then
      raise exception 'Only users with groups.manage can assign or change a PM' using errcode = '42501';
    end if;
  else
    raise exception 'You cannot manage this group''s members' using errcode = '42501';
  end if;

  perform set_config('authz.actor', p_actor::text, true);
  if p_role is null then
    delete from authz.group_members gm where gm.group_id = p_group and gm.user_id = p_target;
  else
    insert into authz.group_members (group_id, user_id, role, added_by)
    values (p_group, p_target, p_role, p_actor)
    on conflict (group_id, user_id) do update set role = excluded.role, added_by = excluded.added_by;
  end if;
end
$$;

-- Create a group; returns its id
create function public.authz_create_group(p_actor uuid, p_slug text, p_name text)
returns uuid
language plpgsql security definer
set search_path = ''
as $$
declare
  v_id uuid;
begin
  if not authz.user_has_permission(p_actor, 'groups.manage') then
    raise exception 'Creating groups needs the groups.manage permission' using errcode = '42501';
  end if;
  perform set_config('authz.actor', p_actor::text, true);
  insert into authz.groups (slug, name, created_by)
  values (lower(trim(p_slug)), trim(p_name), p_actor)
  returning id into v_id;
  return v_id;
end
$$;

-- ── Function grants ────────────────────────────────────────────────────────────

revoke all on all functions in schema authz from public, anon, authenticated, service_role;
revoke all on function public.get_principal(uuid) from public, anon, authenticated;
revoke all on function public.authz_set_role(uuid, uuid, authz.app_role) from public, anon, authenticated;
revoke all on function public.authz_set_membership(uuid, uuid, uuid, authz.group_role) from public, anon, authenticated;
revoke all on function public.authz_create_group(uuid, text, text) from public, anon, authenticated;

grant execute on function authz.has_permission(text) to authenticated, service_role;
grant execute on function authz.has_group_permission(uuid, text) to authenticated, service_role;
grant execute on function public.get_principal(uuid) to service_role;
grant execute on function public.authz_set_role(uuid, uuid, authz.app_role) to service_role;
grant execute on function public.authz_set_membership(uuid, uuid, uuid, authz.group_role) to service_role;
grant execute on function public.authz_create_group(uuid, text, text) to service_role;
-- service_role passes authz enum values to the functions above
grant usage on type authz.app_role, authz.group_role to service_role;

-- ── Permission matrix (data, not code) ─────────────────────────────────────────

insert into authz.permissions (key, scope, description) values
  ('research.read',          'global', 'Read research, news, calendar and the ticker list (shared market data)'),
  ('tickers.create',         'global', 'Start tracking a new symbol'),
  ('tickers.manage_any',     'global', 'Change the status of, or delete, any tracked ticker'),
  ('users.invite',           'global', 'Invite new accounts'),
  ('users.manage',           'global', 'Disable accounts and set them to member or readonly'),
  ('groups.manage',          'global', 'Create groups and manage any group''s members, including PMs'),
  ('groups.read_all',        'global', 'Read every group''s content'),
  ('dashboard.firm',         'global', 'Open the firm-wide dashboard'),
  ('audit.read',             'global', 'Read the access-control audit log'),
  ('group.read',             'group',  'Read the group''s content'),
  ('group.watchlist.add',    'group',  'Add tickers to the group''s watchlist'),
  ('group.watchlist.manage', 'group',  'Remove tickers from the watchlist and mark them held'),
  ('group.dashboard',        'group',  'Open the group dashboard'),
  ('group.members.manage',   'group',  'Add and remove the group''s analysts');

insert into authz.role_permissions (role, permission)
select 'admin'::authz.app_role, unnest(array[
  'research.read', 'tickers.create', 'tickers.manage_any',
  'users.invite', 'users.manage', 'groups.manage', 'audit.read'])
union all
select 'cio', unnest(array[
  'research.read', 'tickers.create', 'tickers.manage_any',
  'users.invite', 'users.manage', 'groups.manage', 'audit.read',
  'groups.read_all', 'dashboard.firm'])
union all
select 'member', unnest(array['research.read', 'tickers.create'])
union all
select 'readonly', unnest(array['research.read']);

insert into authz.group_role_permissions (role, permission)
select 'pm'::authz.group_role, unnest(array[
  'group.read', 'group.watchlist.add', 'group.watchlist.manage', 'group.dashboard',
  'group.members.manage'])
union all
select 'analyst', unnest(array['group.read', 'group.watchlist.add']);

-- ── Backfill existing accounts ─────────────────────────────────────────────────
-- The existing app_metadata.role = 'admin' account is the CTO's. Everyone else
-- already had full member access, so they keep it.

insert into authz.user_roles (user_id, role)
select u.id,
       case when u.raw_app_meta_data ->> 'role' = 'admin' then 'admin' else 'member' end::authz.app_role
  from auth.users u
on conflict (user_id) do nothing;
