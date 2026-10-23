-- Preboard Generator: tables for STORAGE=supabase
-- Run once in Supabase → SQL Editor → New query → paste → Run.

create table if not exists public.questions (
    id                  text primary key,
    chapter_id          text not null,
    chapter             text not null,
    topic               text not null,
    qtype               text not null check (qtype in ('mcq','assertion_reason','vsa','sa','la','case_based')),
    marks               integer not null,
    difficulty          text not null check (difficulty in ('easy','medium','hard')),
    competency_based    boolean not null default false,
    question            text not null,
    options             jsonb,
    answer              text not null,
    explanation         text,
    marking_scheme      jsonb not null,
    status              text not null default 'pending' check (status in ('approved','pending','rejected')),
    source              text not null default 'ai' check (source in ('teacher','ai')),
    created_at          timestamptz not null default now(),
    last_used_in_paper  text
);

create index if not exists questions_lookup on public.questions (status, chapter_id, qtype, difficulty);

-- syllabus, blueprint and agent reports (stored as JSON documents)
create table if not exists public.documents (
    name        text primary key,          -- 'syllabus', 'blueprint', 'report:pattern_report', ...
    data        jsonb not null,
    updated_at  timestamptz not null default now()
);

-- Lock the tables: only the secret (service_role) key used by the app can read/write.
alter table public.questions enable row level security;
alter table public.documents enable row level security;
