# corp-django-template

A Copier template for Django web applications in the corporate environment. Mines [cookiecutter-django](https://github.com/cookiecutter/cookiecutter-django) for layout and conventions; layers on the [planly-django](../) tutorial's corporate-deploy patterns (uv + Astral tooling, structlog JSON logging, GitLab CI, debian:trixie-slim Dockerfile, OIDC SSO, HTMX + Tailwind v4, Postgres-only).

## Quick start

```bash
# Install copier (recommended via uv)
uv tool install copier

# Generate a project
copier copy <this-repo-url> my-new-app
cd my-new-app
cp .env.example .env       # fill in real values
uv sync --all-groups
docker compose up
```

The generated project ships an `apps/example/` placeholder app to prove every toggle wires together. Day-one task: `git rm -r apps/example` and add your domain models.

## Updating an existing project

Copier remembers the answers used at generation time and can pull template improvements back into a project that was generated earlier:

```bash
cd my-already-generated-app
copier update
# Review the diff, resolve any conflicts, commit.
```

## Prompt reference

Run `copier copy` interactively for inline help. The full list:

| Prompt | Default | Drives |
|---|---|---|
| `project_name` | (required) | Display name in README, settings |
| `project_slug` | derived | Generated directory name |
| `package_slug` | derived | Python identifier for settings prefixes |
| `description`, `author_name`, `email`, `domain_name`, `timezone` | — | Pyproject + settings |
| `python_version` | `3.14` | Pyproject, Dockerfile, ruff `target-version`, ty |
| `postgresql_version` | `17` | Compose `db` service image |
| `tailwind_version` | `v4.1.10` | Dockerfile `TAILWIND_VERSION` ARG (only if `use_htmx`) |
| `auth_method` | `oidc` / `gateway` | OIDC SSO via mozilla-django-oidc, or corp-gateway middleware skeleton |
| `use_drf` | `true` | DRF + drf-spectacular |
| `use_htmx` | `true` | HTMX + Tailwind v4 + django-template-partials |
| `use_fts` | `false` | Unaccent + pg_trgm + `GeneratedField` search vectors |
| `use_attachments` | `false` | django-storages[s3] + python-magic libmagic validators |
| `use_notifications` | `false` | django.tasks fan-out + worker service in compose |
| `use_whitenoise` | `true` | WhiteNoise middleware + manifest static files |
| `corporate_ca_bundle` | `true` | `update-ca-certificates` block in Dockerfile |
| `gitlab_runner_image` | `python:3.14-slim-trixie` | CI image |
| `open_source_license` | `Proprietary` | LICENSE file |

## Toggle matrix

The default toggles (`auth_method=oidc`, `use_drf`, `use_htmx`, `use_whitenoise`, `corporate_ca_bundle`) match the recommended corporate baseline. Optional features (`use_fts`, `use_attachments`, `use_notifications`) are off by default — turn them on if your project needs them.

The `gateway` auth path generates a `RemoteUserMiddleware` skeleton with `# TODO(team)` markers where the real corporate gateway header conventions need to land. Don't ship to production without filling those in.

## Repository layout

```
copier.yml                     # prompts + Copier config
README.md                      # this file
UPSTREAM.md                    # cookiecutter-django commit lineage + deviations
.gitlab-ci.yml                 # template's own CI: dogfood matrix
tests/
├── answers/
│   ├── minimal.yml            # auth=oidc, no feature toggles
│   ├── full.yml               # everything on
│   └── gateway-api-only.yml   # auth=gateway + DRF only
├── conftest.py
└── test_*.py                  # generates each combination, runs its tests
template/                      # the templated tree (Copier's _subdirectory)
```

## Maintenance

The template ships with its own pytest suite that, on every push, generates each named matrix combination, runs `uv sync`, `pytest`, `ruff check`, `manage.py check`, and (when `use_drf`) `manage.py spectacular --validate --fail-on-warn` inside the generated project. CI fails if any combination breaks.

When upstream cookiecutter-django adopts a pattern worth pulling, translate it manually into Copier syntax and update `UPSTREAM.md` with the upstream commit and a one-line summary of what was pulled. Don't `git merge` — the engines differ.

## Contributing

1. Branch off `main`.
2. Make the template change.
3. Add or update a `tests/answers/*.yml` file if your change introduces a new toggle combination.
4. Run `pytest tests/` locally.
5. Update `UPSTREAM.md` if you mined anything from upstream.
6. Open a merge request.
