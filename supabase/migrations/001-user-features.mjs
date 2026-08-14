// Migracion one-shot: tablas de funciones de usuario para Tecnoboletin,
// con RLS de "cada usuario solo ve/toca lo suyo". Idempotente.
// La connection string se lee de SECRETS.local.md (untracked), nunca se
// hardcodea aqui.
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
create table if not exists public.user_favorites (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('boletin', 'nodo')),
  ref text not null,
  created_at timestamptz not null default now(),
  unique (user_id, kind, ref)
);
alter table public.user_favorites enable row level security;
drop policy if exists "select own favorites" on public.user_favorites;
create policy "select own favorites" on public.user_favorites
  for select using (auth.uid() = user_id);
drop policy if exists "insert own favorites" on public.user_favorites;
create policy "insert own favorites" on public.user_favorites
  for insert with check (auth.uid() = user_id);
drop policy if exists "delete own favorites" on public.user_favorites;
create policy "delete own favorites" on public.user_favorites
  for delete using (auth.uid() = user_id);

create table if not exists public.user_reads (
  user_id uuid not null references auth.users(id) on delete cascade,
  boletin_date text not null check (boletin_date ~ '^\\d{4}-\\d{2}-\\d{2}$'),
  read_at timestamptz not null default now(),
  primary key (user_id, boletin_date)
);
alter table public.user_reads enable row level security;
drop policy if exists "select own reads" on public.user_reads;
create policy "select own reads" on public.user_reads
  for select using (auth.uid() = user_id);
drop policy if exists "insert own reads" on public.user_reads;
create policy "insert own reads" on public.user_reads
  for insert with check (auth.uid() = user_id);
drop policy if exists "delete own reads" on public.user_reads;
create policy "delete own reads" on public.user_reads
  for delete using (auth.uid() = user_id);
`;

try {
  await client.connect();
  await client.query(SQL);
  const check = await client.query(`
    select tablename,
      (select count(*) from pg_policies p where p.tablename = t.tablename) as policies,
      (select relrowsecurity from pg_class c where c.relname = t.tablename) as rls
    from pg_tables t
    where schemaname = 'public' and tablename in ('user_favorites', 'user_reads')
    order by tablename;
  `);
  console.log('MIGRATION_OK');
  console.table(check.rows);
} catch (err) {
  console.error('MIGRATION_FAIL:', err.message);
  process.exit(1);
} finally {
  await client.end();
}
