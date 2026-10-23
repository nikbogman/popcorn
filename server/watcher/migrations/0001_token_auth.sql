-- Better Auth's accounts and sessions give way to one password and bearer tokens.
drop table if exists session, account, verification, "user";
drop schema if exists drizzle cascade;

-- Only the token's hash is stored, so a leaked row can't be used to sign in.
create table auth_token (
  token_hash text primary key,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);
