// Migracion one-shot: tabla de triaje para Tecnoboletin, con RLS de
// "cada usuario solo ve/toca lo suyo". Idempotente.
// La connection string se lee de SECRETS.local.md (untracked).
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

// El triaje es una decision del usuario sobre un item concreto de un
// boletin concreto: la clave natural es (user_id, boletin_date, item_idx).
// Al ser PK, el upsert desde el cliente no necesita mas indices.
const SQL = `
create table if not exists public.user_triage (
  user_id uuid not null references auth.users(id) on delete cascade,
  boletin_date text not null check (boletin_date ~ '^\\d{4}-\\d{2}-\\d{2}$'),
  item_idx integer not null,
  estado text not null check (estado in ('explorar', 'probar', 'leer', 'vigilar', 'descartar')),
  updated_at timestamptz not null default now(),
  primary key (user_id, boletin_date, item_idx)
);

alter table public.user_triage enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where tablename = 'user_triage' and policyname = 'triage_select_own') then
    create policy triage_select_own on public.user_triage for select using (auth.uid() = user_id);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'user_triage' and policyname = 'triage_insert_own') then
    create policy triage_insert_own on public.user_triage for insert with check (auth.uid() = user_id);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'user_triage' and policyname = 'triage_update_own') then
    create policy triage_update_own on public.user_triage for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'user_triage' and policyname = 'triage_delete_own') then
    create policy triage_delete_own on public.user_triage for delete using (auth.uid() = user_id);
  end if;
end $$;
`;

await client.connect();
await client.query(SQL);

const pol = await client.query(
  "select policyname, cmd from pg_policies where tablename = 'user_triage' order by policyname"
);
const rls = await client.query(
  "select relrowsecurity from pg_class where relname = 'user_triage'"
);
const cols = await client.query(
  "select column_name from information_schema.columns where table_name = 'user_triage' order by ordinal_position"
);
console.log('MIGRATION_OK');
console.log('columns:', cols.rows.map((r) => r.column_name).join(', '));
console.log('rls:', rls.rows[0]?.relrowsecurity);
console.log('policies:', pol.rows.map((r) => `${r.policyname}(${r.cmd})`).join(', '));
await client.end();
