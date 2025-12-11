-- Supabase session tracking for WhatsApp recommendations extractor
-- Run this in Supabase SQL editor before deploying the API.

create table if not exists public.sessions (
    session_id text primary key,
    status text not null default 'processing',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    zip_name text,
    preview_mode boolean not null default true,
    progress_message text,
    error_message text,
    result_url text,
    result_json jsonb,
    openai_enhanced boolean not null default false,
    expires_at timestamptz
);

-- Indexes to speed up lookups and cleanup
create index if not exists idx_sessions_status on public.sessions(status);
create index if not exists idx_sessions_created_at on public.sessions(created_at desc);
create index if not exists idx_sessions_expires_at on public.sessions(expires_at);

-- Updated_at trigger
create or replace function public.update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_sessions_updated_at on public.sessions;
create trigger trg_sessions_updated_at
before update on public.sessions
for each row execute procedure public.update_updated_at_column();

