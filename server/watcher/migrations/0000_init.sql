-- The schema the Node server left behind. "if not exists" so a database it migrated keeps its data.

-- The Status and Favourite rules' invariants, enforced by the database too.
create table if not exists collection_entry (
  tmdb_id integer primary key,
  title text not null,
  year integer,
  poster_path text,
  status text not null,
  added_at timestamptz not null,
  watched_at timestamptz,
  favourite boolean not null,
  constraint status_valid check (status in ('to_watch', 'watched')),
  constraint watched_at_iff_watched check ((status = 'watched') = (watched_at is not null)),
  constraint favourite_implies_watched check (not favourite or status = 'watched')
);

-- The one logged-in Instagram session the scraper browses with, as Playwright storage state.
create table if not exists instagram_session (
  id integer primary key default 1,
  storage_state jsonb not null,
  saved_at timestamptz not null default now(),
  constraint instagram_session_single_row check (id = 1)
);

-- The reel scrape queue: each row is a job and, once done, its result.
create table if not exists reel_scrape (
  id uuid primary key default gen_random_uuid(),
  url text not null,
  status text not null default 'queued',
  reel jsonb,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint reel_scrape_status_valid check (status in ('queued', 'running', 'done', 'failed'))
);
