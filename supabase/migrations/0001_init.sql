-- =============================================================================
-- Astra — Developer Capability-Verification Platform
-- Migration 0001: initial schema, encryption, triggers, and row level security
-- =============================================================================
-- Target: Supabase Postgres (auth schema managed by GoTrue).
-- Auth model: Supabase Auth with GitHub OAuth only. No email/password.
-- Design note: commit-level data is intentionally NOT stored in its own table.
--              It is aggregated into repositories.astra_capability_summary (JSONB)
--              to keep row counts bounded and avoid per-commit table bloat.
-- =============================================================================

begin;

-- -----------------------------------------------------------------------------
-- Extensions
-- -----------------------------------------------------------------------------
-- pgcrypto: gen_random_uuid() for primary keys.
create extension if not exists pgcrypto with schema extensions;

-- pgsodium: libsodium-backed Transparent Column Encryption (TCE) for at-rest
-- encryption of OAuth access tokens. On Supabase this extension lives in the
-- `pgsodium` schema and is pre-provisioned; `if not exists` makes this idempotent.
create extension if not exists pgsodium;

-- =============================================================================
-- TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- public.users
-- One row per authenticated identity. `id` mirrors auth.users(id) 1:1 so that
-- auth.uid() can be compared directly against public.users.id in RLS policies.
-- Deleting the auth user cascades and removes the public profile.
-- -----------------------------------------------------------------------------
create table public.users (
  id            uuid primary key
                references auth.users (id) on delete cascade,
  display_name  text,
  -- Human-friendly public handle for the capability passport URL
  -- (/passport/[slug]). Auto-generated from the GitHub username by the
  -- handle_new_user() trigger; guaranteed unique and non-null.
  passport_slug text        not null unique,
  is_public     boolean     not null default true,
  created_at    timestamptz not null default now()
);

comment on table public.users is
  'Astra user profiles. id is 1:1 with auth.users(id). passport_slug drives the public /passport/[slug] route.';

-- -----------------------------------------------------------------------------
-- public.identities
-- External provider connections owned by a user. Holds the encrypted provider
-- access token. Never exposed to any role other than the owning user.
-- -----------------------------------------------------------------------------
create table public.identities (
  id                      uuid primary key default gen_random_uuid(),
  user_id                 uuid not null
                          references public.users (id) on delete cascade,
  provider                text not null
                          check (provider in ('github', 'arxiv', 'huggingface')),
  provider_username       text not null,
  -- pgsodium Transparent Column Encryption is applied to this column below via
  -- a SECURITY LABEL. Ciphertext is stored here; a paired view in the
  -- `decrypted` schema exposes plaintext only to privileged roles.
  access_token_encrypted  text,
  verified                boolean not null default false,
  connected_at            timestamptz not null default now(),
  -- A user connects a given provider at most once.
  unique (user_id, provider)
);

comment on table public.identities is
  'Per-provider connections for a user. access_token_encrypted is encrypted at rest via pgsodium TCE and is strictly owner-private.';

create index identities_user_id_idx on public.identities (user_id);

-- -----------------------------------------------------------------------------
-- public.repositories
-- Repositories discovered under an identity. Commit-level analysis is folded
-- into astra_capability_summary (JSONB) rather than a separate commits table.
-- -----------------------------------------------------------------------------
create table public.repositories (
  id                        uuid primary key default gen_random_uuid(),
  identity_id               uuid not null
                            references public.identities (id) on delete cascade,
  repo_full_name            text not null,
  is_fork                   boolean not null default false,
  primary_language          text,
  astra_capability_summary  jsonb not null default '{}'::jsonb,
  last_analyzed_at          timestamptz,
  unique (identity_id, repo_full_name)
);

comment on table public.repositories is
  'Repositories per identity. astra_capability_summary holds aggregated commit-level signals to avoid a high-volume commits table.';
comment on column public.repositories.astra_capability_summary is
  'Aggregated commit-level analysis (languages, cadence, complexity, etc.). Replaces a raw commits table by design.';

create index repositories_identity_id_idx on public.repositories (identity_id);

-- -----------------------------------------------------------------------------
-- public.capability_scores
-- Computed Astra scores. Written exclusively by the backend (service_role).
-- Immutable from the client. is_current flags the latest score per user.
-- -----------------------------------------------------------------------------
create table public.capability_scores (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null
                      references public.users (id) on delete cascade,
  score_version       text not null default 'v1.0',
  astra_score         float not null,
  subscore_breakdown  jsonb not null default '{}'::jsonb,
  percentile          float,
  is_current          boolean not null default true,
  computed_at         timestamptz not null default now()
);

comment on table public.capability_scores is
  'Computed Astra capability scores. Insert/update only via service_role; clients read-only subject to owner visibility.';

create index capability_scores_user_id_idx on public.capability_scores (user_id);
-- At most one "current" score per user.
create unique index capability_scores_one_current_idx
  on public.capability_scores (user_id)
  where is_current;

-- =============================================================================
-- ENCRYPTION — pgsodium Transparent Column Encryption for identity tokens
-- =============================================================================
-- We create (once) a dedicated pgsodium key and attach it to
-- identities.access_token_encrypted via a SECURITY LABEL. pgsodium then
-- transparently encrypts writes and provisions a decrypted view for reads by
-- privileged roles. The DO block resolves the key id dynamically because the
-- SECURITY LABEL text must embed the concrete key UUID.
-- -----------------------------------------------------------------------------
do $$
declare
  v_key_id uuid;
begin
  -- Reuse an existing key of this name if the migration is re-run.
  select id into v_key_id
  from pgsodium.key
  where name = 'astra_identity_token_key';

  if v_key_id is null then
    v_key_id := (select pgsodium.create_key(name => 'astra_identity_token_key'));
  end if;

  execute format(
    'security label for pgsodium on column public.identities.access_token_encrypted is %L',
    'ENCRYPT WITH KEY ID ' || v_key_id::text
  );
end
$$;

-- =============================================================================
-- TRIGGER — auto-provision public.users on new auth.users
-- =============================================================================
-- Runs as SECURITY DEFINER so it can insert into public.users regardless of the
-- caller's RLS context (GoTrue inserts into auth.users during OAuth sign-up).
-- Extracts the GitHub username from raw_user_meta_data->>'user_name', slugifies
-- it, and de-duplicates to satisfy the UNIQUE NOT NULL passport_slug constraint.
-- -----------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_github_username text;
  v_base_slug       text;
  v_final_slug      text;
  v_suffix          integer := 0;
begin
  -- GitHub OAuth populates 'user_name'; fall back defensively so the insert
  -- never violates NOT NULL even for non-GitHub or malformed metadata.
  v_github_username := coalesce(
    new.raw_user_meta_data ->> 'user_name',
    new.raw_user_meta_data ->> 'preferred_username',
    nullif(split_part(coalesce(new.email, ''), '@', 1), ''),
    'user'
  );

  -- Slugify: lowercase, non-alphanumeric runs -> single hyphen, trim hyphens.
  v_base_slug := regexp_replace(lower(v_github_username), '[^a-z0-9]+', '-', 'g');
  v_base_slug := trim(both '-' from v_base_slug);
  if v_base_slug is null or v_base_slug = '' then
    v_base_slug := 'user';
  end if;

  -- Ensure uniqueness by appending an incrementing suffix on collision.
  v_final_slug := v_base_slug;
  while exists (select 1 from public.users where passport_slug = v_final_slug) loop
    v_suffix := v_suffix + 1;
    v_final_slug := v_base_slug || '-' || v_suffix::text;
  end loop;

  insert into public.users (id, display_name, passport_slug)
  values (
    new.id,
    coalesce(
      new.raw_user_meta_data ->> 'full_name',
      new.raw_user_meta_data ->> 'name',
      v_github_username
    ),
    v_final_slug
  );

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

-- =============================================================================
-- GRANTS
-- =============================================================================
-- RLS is the security boundary, but the anon/authenticated roles still need
-- base table privileges for policies to be reachable. service_role bypasses RLS
-- entirely and is used by the FastAPI backend for score writes.
-- -----------------------------------------------------------------------------
grant usage on schema public to anon, authenticated, service_role;

grant select                         on public.users             to anon, authenticated;
grant update, delete                 on public.users             to authenticated;

grant select, insert, update, delete on public.identities        to authenticated;

grant select                         on public.repositories      to anon, authenticated;
grant insert, update, delete         on public.repositories      to authenticated;

grant select                         on public.capability_scores to anon, authenticated;

grant all on public.users, public.identities, public.repositories, public.capability_scores
  to service_role;

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================
alter table public.users             enable row level security;
alter table public.identities        enable row level security;
alter table public.repositories      enable row level security;
alter table public.capability_scores enable row level security;

-- -----------------------------------------------------------------------------
-- users policies
-- -----------------------------------------------------------------------------
-- Reasoning: a profile is world-readable when the owner opts into a public
-- passport (is_public = true). The owner can always read their own row even
-- when private, so the app works while a profile is hidden.
create policy users_select_public_or_self
  on public.users
  for select
  to anon, authenticated
  using (is_public = true or auth.uid() = id);

-- Reasoning: only the owner may mutate their profile. WITH CHECK prevents an
-- owner from reassigning the row's id to someone else during an update.
create policy users_update_self
  on public.users
  for update
  to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Reasoning: only the owner may delete their profile (which cascades to auth
-- via the FK relationship in the opposite direction is not triggered; this
-- simply removes the public projection they own).
create policy users_delete_self
  on public.users
  for delete
  to authenticated
  using (auth.uid() = id);

-- Note: there is deliberately no INSERT policy. Rows are created solely by the
-- SECURITY DEFINER trigger handle_new_user(), which bypasses RLS.

-- -----------------------------------------------------------------------------
-- identities policies
-- -----------------------------------------------------------------------------
-- Reasoning: identities are strictly private. They contain encrypted access
-- tokens and must never be visible to any user other than the owner. Because
-- public.users.id equals auth.users.id, ownership is exactly auth.uid() =
-- user_id for every command. A single ALL policy enforces this uniformly for
-- SELECT/INSERT/UPDATE/DELETE, with WITH CHECK blocking inserts/updates that
-- would assign a row to another user.
create policy identities_owner_all
  on public.identities
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- -----------------------------------------------------------------------------
-- repositories policies
-- -----------------------------------------------------------------------------
-- Reasoning: a repository is publicly readable only when the repo's owning user
-- has a public passport. We resolve ownership by joining identities -> users.
-- The owner can always read their own repositories regardless of visibility.
create policy repositories_select_public_or_owner
  on public.repositories
  for select
  to anon, authenticated
  using (
    exists (
      select 1
      from public.identities i
      join public.users u on u.id = i.user_id
      where i.id = repositories.identity_id
        and (u.is_public = true or u.id = auth.uid())
    )
  );

-- Reasoning: write access (insert/update/delete) is restricted to the user who
-- owns the parent identity. WITH CHECK re-validates ownership on the resulting
-- row so a user cannot move a repository under someone else's identity.
create policy repositories_insert_owner
  on public.repositories
  for insert
  to authenticated
  with check (
    exists (
      select 1
      from public.identities i
      where i.id = repositories.identity_id
        and i.user_id = auth.uid()
    )
  );

create policy repositories_update_owner
  on public.repositories
  for update
  to authenticated
  using (
    exists (
      select 1
      from public.identities i
      where i.id = repositories.identity_id
        and i.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.identities i
      where i.id = repositories.identity_id
        and i.user_id = auth.uid()
    )
  );

create policy repositories_delete_owner
  on public.repositories
  for delete
  to authenticated
  using (
    exists (
      select 1
      from public.identities i
      where i.id = repositories.identity_id
        and i.user_id = auth.uid()
    )
  );

-- -----------------------------------------------------------------------------
-- capability_scores policies
-- -----------------------------------------------------------------------------
-- Reasoning: scores follow the same public-read-if-owner-is-public rule as
-- repositories, resolved directly against the owning user. The owner can always
-- read their own scores.
create policy capability_scores_select_public_or_owner
  on public.capability_scores
  for select
  to anon, authenticated
  using (
    exists (
      select 1
      from public.users u
      where u.id = capability_scores.user_id
        and (u.is_public = true or u.id = auth.uid())
    )
  );

-- Reasoning: scores are immutable from the client. There is NO insert/update/
-- delete policy for anon or authenticated, so those roles can never write.
-- service_role (used by the FastAPI backend) bypasses RLS and is the only path
-- that may compute and persist scores. The explicit service_role policy below
-- documents that intent; it is permissive because service_role already bypasses
-- RLS, but keeping it makes the write authority auditable in the schema.
create policy capability_scores_service_write
  on public.capability_scores
  for all
  to service_role
  using (true)
  with check (true);

commit;
