# Commit messages

This repo follows [Conventional Commits](https://www.conventionalcommits.org/).

## Format

```
<type>(<scope>): <summary>

<body>

<footer>
```

Only the first line is required.

## Type

| Type       | Use for                                                   |
| ---------- | --------------------------------------------------------- |
| `feat`     | A new user-facing capability                              |
| `fix`      | A bug fix                                                 |
| `refactor` | A code change that neither adds a feature nor fixes a bug |
| `test`     | Adding or changing tests only                             |
| `docs`     | Documentation only (PRDs, CONTEXT.md, READMEs)            |
| `chore`    | Dependencies, config, tooling, scaffolding                |
| `perf`     | A performance improvement                                 |
| `style`    | Formatting only, with no behaviour change                 |

## Scope

The part of the workspace the commit touches:

| Scope    | Covers                                                                    |
| -------- | ------------------------------------------------------------------------- |
| `mobile` | `mobile/`                                                                 |
| `server` | `server/`                                                                 |
| `repo`   | Root config and agent tooling (`.claude/`, `.mcp.json`)                   |

Leave out the scope if a commit spans both apps. Split the commit instead when the changes are unrelated.

## Summary

- Imperative mood: "add", not "added" or "adds".
- Lowercase, and no full stop at the end.
- 72 characters or fewer for the whole first line.
- Use the domain terms from [CONTEXT.md](CONTEXT.md): _To watch_, _Watched_, _Favourite_, _Entry_, _Collection_, _Drop_.

## Body

Optional. Explain **why** the change was made, not what changed (the diff shows that). Wrap lines at 72 characters and leave a blank line after the summary.

## Footer

- `BREAKING CHANGE: <what breaks and how to migrate>` for breaking changes. Also add `!` after the type or scope: `feat(server)!: ...`.
- `Refs: #1` to link the spec issue the change implements.
- `Co-Authored-By:` lines for co-authors, including AI agents.

## Examples

```
feat(server): add endpoint to mark a movie as watched
```

```
fix(mobile): keep favourite button disabled while request is pending
```

```
chore(repo): add agent-device and Better Auth agent skills
```

```
feat(server)!: require a session on all movie routes

Search and movie details were reachable without login, which let
anyone use the TMDB quota through the server.

BREAKING CHANGE: clients must send a valid session with every
request except Better Auth's own endpoints.
Refs: #1
```

## One commit, one change

Each commit should build and pass typechecks on its own. Keep refactors separate from feature work.
