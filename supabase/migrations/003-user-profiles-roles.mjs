// Migracion one-shot: perfiles de usuario + gestion de roles.
//
// Por que una tabla y no app_metadata: el sitio es estatico, asi que la
// unica forma de gestionar roles desde la propia web es que la
// autorizacion viva en Postgres con RLS. app_metadata solo se puede tocar
// con la service_role key, que jamas puede viajar al navegador.
//
// Idempotente. La connection string se lee de SECRETS.local.md (untracked).
import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import pg from 'pg';

const secrets = readFileSync(`${homedir()}/proyectos/tecnoboletin/SECRETS.local.md`, 'utf8');
const m = secrets.match(/postgres(?:ql)?:\/\/\S+/);
if (!m) {
  console.error('No se encontro la connection string en SECRETS.local.md');
  process.exit(1);
}

const client = new pg.Client({ connectionString: m[0], ssl: { rejectUnauthorized: false } });

const SQL = `
-- Espejo de auth.users consultable desde el cliente: auth.users no se
-- expone via PostgREST, asi que la pantalla de usuarios necesita esto.
create table if not exists public.user_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  role text not null default 'user' check (role in ('user', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Alta automatica al registrarse.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $fn$
begin
  insert into public.user_profiles (id, email, created_at)
  values (new.id, new.email, coalesce(new.created_at, now()))
  on conflict (id) do update set email = excluded.email;
  return new;
end;
$fn$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Backfill de los usuarios que ya existian antes del trigger.
insert into public.user_profiles (id, email, created_at)
select u.id, u.email, u.created_at from auth.users u
on conflict (id) do update set email = excluded.email;

-- SECURITY DEFINER a proposito: si la politica de user_profiles
-- consultara user_profiles directamente, la RLS se llamaria a si misma
-- (recursion infinita). Esta funcion la lee saltandose RLS.
create or replace function public.is_admin(uid uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $fn$
  select exists (select 1 from public.user_profiles p where p.id = uid and p.role = 'admin');
$fn$;

-- Nadie puede quedarse sin administradores: sin esto, un admin podria
-- degradarse a si mismo y dejar la gestion de roles inaccesible para
-- siempre (no hay backend con service_role para rescatarla).
create or replace function public.guard_last_admin()
returns trigger
language plpgsql
as $fn$
begin
  if old.role = 'admin' and new.role <> 'admin'
     and (select count(*) from public.user_profiles where role = 'admin') <= 1 then
    raise exception 'No se puede quitar el ultimo administrador';
  end if;
  new.updated_at = now();
  return new;
end;
$fn$;

drop trigger if exists guard_last_admin_trigger on public.user_profiles;
create trigger guard_last_admin_trigger
  before update on public.user_profiles
  for each row execute function public.guard_last_admin();

alter table public.user_profiles enable row level security;

do $$
begin
  -- Cada cual ve su perfil; los administradores ven a todo el mundo.
  if not exists (select 1 from pg_policies where tablename = 'user_profiles' and policyname = 'profiles_select') then
    create policy profiles_select on public.user_profiles
      for select using (auth.uid() = id or public.is_admin(auth.uid()));
  end if;
  -- Solo administradores cambian roles. Sin politica de insert/delete: las
  -- altas las hace el trigger y las bajas el cascade de auth.users.
  if not exists (select 1 from pg_policies where tablename = 'user_profiles' and policyname = 'profiles_update_admin') then
    create policy profiles_update_admin on public.user_profiles
      for update using (public.is_admin(auth.uid())) with check (public.is_admin(auth.uid()));
  end if;
end $$;
`;

await client.connect();
await client.query(SQL);

// Primer administrador: las cuentas del propietario del sitio. Es el
// unico paso que necesita acceso directo a la base de datos; a partir de
// aqui los roles se gestionan desde /cuenta/usuarios/.
// Los correos NO van aqui: este repo es publico. Se leen de
// SECRETS.local.md (untracked), bajo una linea '- owner_emails: a@b, c@d'.
const ownerLine = secrets.match(/owner_emails:\s*(.+)/i);
const OWNER_EMAILS = ownerLine ? ownerLine[1].split(/[,\s]+/).filter(Boolean) : [];
const promoted = await client.query(
  `update public.user_profiles set role = 'admin' where email = any($1::text[]) returning email, role`,
  [OWNER_EMAILS]
);

const rows = await client.query(
  'select email, role, created_at from public.user_profiles order by created_at'
);
const pol = await client.query(
  "select policyname, cmd from pg_policies where tablename = 'user_profiles' order by policyname"
);

console.log('MIGRATION_OK');
console.log('promovidos:', promoted.rows.map((r) => `${r.email}=${r.role}`).join(', ') || '(ninguno)');
console.log('policies:', pol.rows.map((r) => `${r.policyname}(${r.cmd})`).join(', '));
console.table(rows.rows);
await client.end();
