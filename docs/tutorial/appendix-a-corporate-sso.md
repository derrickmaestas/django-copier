# Appendix A — Corporate SSO via OIDC

## Goal

By the end of this appendix you'll have a complete migration path from Planly's built-in username/password + self-issued JWT auth to **corporate SSO via OpenID Connect (OIDC)**. Specifically:

- Browser users land on a "Sign in" link that redirects to the corporate IdP, authenticate via the user's installed client certificate (PIV/CAC card, smart card, or browser cert), and return to Planly with an active session — **no password ever entered into Planly**.
- API clients present an `Authorization: Bearer <jwt>` header with a JWT issued *by the IdP* (not by Planly). Planly validates the signature against the IdP's published JWKS endpoint and authorizes the request.
- Existing Django users (created during onboarding) get linked to their IdP identity on first SSO login via their `employee_id`.
- The deploy is **stateless**: Planly never holds the user's credentials, never issues its own access tokens, and reduces to "verify a signed JWT and look up the local row."

The big themes: **delegate identity entirely to the IdP**; **trust JWT claims, validate the signature**; and **keep the queryset-level team scoping unchanged** — SSO replaces *authentication*, not *authorization*. Once a user is identified, the rest of the app (Membership, `for_user()`, the admin URL) works exactly as before.

This is an **alternative to Chapter 5's password auth and Chapter 13's `simplejwt`-based API tokens**. Read those chapters first; this appendix replaces specific pieces of that work for corporate environments where SSO is the standard.

---

## The flow, in plain language

There are two distinct authentication flows in Planly: the *browser session* (what the kanban board uses) and the *API bearer token* (what external clients use). Both delegate to the IdP, but through different OAuth2 mechanisms.

### Browser session login (OIDC Authorization Code with PKCE)

```
1. User visits /plans/.
2. Planly's @login_required redirects to /oidc/authenticate/.
3. /oidc/authenticate/ redirects the browser to the IdP's authorize endpoint:
     https://idp.corp.example.com/authorize
     ?response_type=code
     &client_id=<planly-client-id>
     &redirect_uri=https://planly.corp/oidc/callback/
     &scope=openid email profile
     &state=<random>
     &code_challenge=<pkce-hash>
     &code_challenge_method=S256
4. The IdP page negotiates TLS with the user's installed certificate.
   The user does NOT see a password form — the cert exchange completes
   silently (or with a "select your certificate" browser dialog).
5. The IdP redirects back to Planly:
     https://planly.corp/oidc/callback/?code=<auth-code>&state=<echo>
6. Planly's callback view exchanges the code for tokens:
     POST https://idp.corp.example.com/token
       grant_type=authorization_code, code=<auth-code>,
       client_id=<planly-client-id>, client_secret=<...>,
       code_verifier=<pkce-verifier>
   ← {access_token, id_token, refresh_token, expires_in}
7. Planly validates id_token's signature against the IdP's JWKS,
   reads claims (sub, email, employee_id, name, ...), looks up
   or creates a User row, calls login(request, user) — Django
   sets a session cookie. From here on, the request is identical
   to the cookie-based flows from Chapters 9-12.
```

The *user* sees: click "Sign in," brief redirect, land on `/plans/`. No password form. No challenge. The cert exchange in step 4 is what Active Directory / corporate SSO calls "Windows-integrated authentication" or "smart card sign-in."

### API bearer-token auth

For clients that don't share the browser session (a shell script, a mobile app, an external service), the IdP issues an access token through whichever flow it supports — typically **client credentials** for service accounts or **resource owner password** for legacy integrations. From Planly's perspective, the flow ends with the client holding a JWT signed by the IdP.

```
1. Client makes a request:
     GET /api/v1/tasks/
     Authorization: Bearer eyJraWQiOiJrZXkx...
2. Planly's OIDCJWTAuthentication class:
   a. Reads the kid (key id) from the JWT header.
   b. Fetches the IdP's JWKS (cached for an hour) at
      https://idp.corp.example.com/jwks.json
   c. Looks up the public key matching the kid.
   d. Validates the signature, expiry, audience, and issuer.
   e. Reads claims, finds the User row by employee_id.
3. The view runs as if the user logged in normally.
```

Note what's **not** in this flow: Planly never calls the IdP at request time except to fetch JWKS keys (cached). There's no token introspection, no per-request RPC. The JWT is self-validating.

---

## Library choice: `mozilla-django-oidc`

Two practical libraries handle this flow in Django:

- **`mozilla-django-oidc`** — focused OIDC client, Django-shaped. Provides the auth backend, callback view, and middleware. ~30 lines of glue.
- **`authlib`** — general-purpose OAuth/OIDC/JOSE library. ~150 lines of glue; flexibility we don't need.

For the Planly case (one corporate IdP, standard Authorization Code flow), `mozilla-django-oidc` is the simpler fit. We'll use it for the browser flow. For the DRF side, we write a small custom authentication class (~50 lines) using `pyjwt[crypto]` directly — `mozilla-django-oidc` doesn't cover that case.

---

## Step 1 — Install dependencies

```bash
uv add mozilla-django-oidc 'pyjwt[crypto]'
uv remove djangorestframework-simplejwt   # IdP issues tokens now, not Planly
```

`pyjwt[crypto]` pulls in `cryptography`, which provides the RS256 signature verification the IdP uses. `mozilla-django-oidc` itself depends on `requests` for talking to the IdP's discovery and token endpoints.

---

## Step 2 — Settings

The IdP-facing configuration lives in `config/settings/base.py` so dev, test, and production all share it; the *secrets* come from environment.

```python
# config/settings/base.py

INSTALLED_APPS = [
    ...,
    "mozilla_django_oidc",
]

# ──────────────────────────────────────────────
# OIDC client — corporate SSO
# ──────────────────────────────────────────────
# `mozilla-django-oidc` reads the discovery document at
# .well-known/openid-configuration to learn the IdP's authorize, token,
# userinfo, and JWKS endpoints. One env var instead of five.
OIDC_OP_DISCOVERY_ENDPOINT = os.environ["OIDC_DISCOVERY_URL"]
OIDC_RP_CLIENT_ID = os.environ["OIDC_CLIENT_ID"]
OIDC_RP_CLIENT_SECRET = os.environ["OIDC_CLIENT_SECRET"]

# RS256 is what every modern IdP uses; HS256 (shared secret) is for
# self-issued tokens, which we no longer do.
OIDC_RP_SIGN_ALGO = "RS256"

# `openid` is mandatory; `email` and `profile` give us the standard
# claims (email, name). Add custom scopes (e.g. `employee_directory`)
# if your IdP only releases employee_id under a non-default scope.
OIDC_RP_SCOPES = "openid email profile"

# PKCE adds an integrity check to the code exchange — defends against
# the auth code being intercepted in transit. The IdP must support it
# (every modern one does); if yours doesn't, set this to False.
OIDC_USE_PKCE = True

# How often to verify the access token is still valid by re-fetching
# userinfo. 15 minutes is the standard balance between catching
# revocations promptly and not hammering the IdP.
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 15 * 60

# Hook our custom backend that maps claims onto Planly's User model.
AUTHENTICATION_BACKENDS = [
    "apps.accounts.auth.PlanlyOIDCBackend",
    # Keep ModelBackend during migration so the admin and any local
    # superuser fallback still work. Remove when the cutover is done.
    "django.contrib.auth.backends.ModelBackend",
]

# Replace the password-form login URL with the OIDC entry point.
LOGIN_URL = "oidc_authentication_init"
LOGIN_REDIRECT_URL = "/plans/"
LOGOUT_REDIRECT_URL = "/"
OIDC_OP_LOGOUT_URL_METHOD = "apps.accounts.auth.provider_logout"
```

`OIDC_OP_LOGOUT_URL_METHOD` is the optional callback that returns the URL to redirect to *after* killing the local Django session — typically the IdP's RP-initiated logout endpoint, which kills the IdP's own session cookie too.

For dev convenience, `config/settings/local.py` can point at a fake IdP (a local instance of `keycloak`, `glauth`, or even a static-claim mock) so devs don't need a real corporate cert to log in.

---

## Step 3 — Custom backend mapping claims to the `User` model

The interesting code lives here. `mozilla-django-oidc` calls four hook methods; we override them to use `employee_id` (our PK) instead of email (which the library defaults to).

```python
# apps/accounts/auth.py
"""OIDC authentication backend.

Maps the corporate IdP's claims onto Planly's custom User model.
The IdP's `sub` claim or a custom `employee_id` claim is the stable
key — never use `email`, which can change when an employee changes
name or moves teams.
"""

from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import User


class PlanlyOIDCBackend(OIDCAuthenticationBackend):
    """Auth backend that creates / updates Planly Users from IdP claims."""

    def filter_users_by_claims(self, claims):
        """Find the existing User row for these claims (None if missing).

        Called BEFORE create_user — gives us a chance to match on
        employee_id rather than the library's default of email.
        """
        employee_id = self._employee_id_from_claims(claims)
        if employee_id is None:
            return User.objects.none()
        return User.objects.filter(employee_id=employee_id)

    def create_user(self, claims):
        """Create a Planly User from the first time this person signs in."""
        user = User.objects.create(
            employee_id=self._employee_id_from_claims(claims),
            email=claims.get("email", ""),
            display_name=claims.get("name", ""),
            division=claims.get("division", ""),
            organization=claims.get("organization", ""),
        )
        # IdP-only auth — no local password is ever set. set_unusable_password
        # makes that explicit and protects against a future code path
        # that mistakenly tries to authenticate this user with `check_password`.
        user.set_unusable_password()
        user.save(update_fields=["password"])
        return user

    def update_user(self, user, claims):
        """Sync the local row with the IdP on every login.

        The IdP is the source of truth for everything in this method.
        Don't merge: overwrite. If the user updated their name in the
        corporate directory yesterday, Planly should pick that up
        today.
        """
        user.display_name = claims.get("name", user.display_name)
        if "email" in claims:
            user.email = claims["email"]
        user.division = claims.get("division", user.division)
        user.organization = claims.get("organization", user.organization)
        user.save(
            update_fields=["display_name", "email", "division", "organization"]
        )
        return user

    def verify_claims(self, claims):
        """Refuse to authenticate if the IdP didn't release the data we need.

        Called AFTER signature validation but BEFORE create/update.
        Reject early so we don't half-create rows.
        """
        if not super().verify_claims(claims):
            return False
        return self._employee_id_from_claims(claims) is not None

    @staticmethod
    def _employee_id_from_claims(claims) -> int | None:
        """Look for the employee id under either claim name.

        Some IdPs put it in `employee_id` (a custom claim mapped from
        the corporate directory); others reuse the standard `sub`.
        Try both in order; cast to int — our model's PK is integer.
        """
        raw = claims.get("employee_id") or claims.get("sub")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None


def provider_logout(request):
    """Build the IdP's RP-initiated logout URL.

    Some IdPs honor an `id_token_hint` parameter; some require a
    pre-registered `post_logout_redirect_uri`. Adjust to match yours.
    """
    id_token = request.session.get("oidc_id_token")
    params = {
        "post_logout_redirect_uri": request.build_absolute_uri(
            settings.LOGOUT_REDIRECT_URL or reverse("home")
        ),
    }
    if id_token:
        params["id_token_hint"] = id_token
    return f"{settings.OIDC_OP_LOGOUT_ENDPOINT}?{urlencode(params)}"
```

A few details earn a sentence:

- **`filter_users_by_claims` returns a `QuerySet`, not a User**. The default backend matches by email; if multiple users share an email (rare but possible during account merges), the default raises. Returning a queryset filtered to our integer PK is unambiguous.
- **`set_unusable_password()` after create**. Django's `AbstractUser` carries a `password` column; we never want anyone to end up able to log in via the local form. Setting an unusable password is the standard signal that this account is externally authenticated.
- **`verify_claims` rejects early** if `employee_id` is missing. Without it, you'd create a User with `pk=None` and only discover the failure on `save()`.
- **`provider_logout` builds the RP-initiated logout URL**. The library calls this *after* clearing the Django session; the returned URL kills the IdP's own session cookie too, so the next visit prompts a fresh cert exchange. Without this, "log out" only kills Planly — the IdP still considers the user logged in until its session timeout.

---

## Step 4 — URL wiring

```python
# config/urls.py
urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(settings.ADMIN_URL, admin.site.urls),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("", include("apps.core.urls", namespace="core")),
    path("plans/", include("apps.plans.urls", namespace="plans")),
    path("tasks/", include("apps.tasks.urls", namespace="tasks")),
    path("notifications/", include("apps.notifications.urls", namespace="notifications")),
    path("api/v1/", include("config.api_router")),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]
```

The `mozilla_django_oidc.urls` include exposes:

- `/oidc/authenticate/` — start the flow (the new `LOGIN_URL`)
- `/oidc/callback/` — IdP redirects here after the cert exchange
- `/oidc/logout/` — kill the Django session and (optionally) the IdP session

The old `path("accounts/", include("django.contrib.auth.urls"))` line is removed — those views (login form, password reset, logout-via-form) are no longer reachable.

---

## Step 5 — Replace `simplejwt` with JWKS-based JWT validation for the API

The Chapter 13 setup had Planly issuing JWTs at `/api/v1/auth/token/` using a shared secret. Now the IdP issues tokens, and Planly only validates. `simplejwt`'s API doesn't bend gracefully to "validate against an external signer," so we drop it and write a small custom DRF authentication class.

```python
# apps/accounts/api/authentication.py
"""DRF authentication that validates Bearer tokens against the corporate IdP.

Tokens are signed by the IdP, not by us. We fetch the IdP's JWKS
(public keys) once per process, cache them for an hour, and refresh
on signature mismatch (the IdP rotates keys periodically).
"""

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

from apps.accounts.models import User

# Module-level cache of the JWKS client. Re-creating it on every
# request would defeat the cache it maintains internally; pyjwt's
# PyJWKClient is thread-safe.
_jwks_client = jwt.PyJWKClient(
    settings.OIDC_OP_JWKS_ENDPOINT,
    cache_keys=True,
    lifespan=3600,
)


class OIDCJWTAuthentication(authentication.BaseAuthentication):
    """Validate `Authorization: Bearer <jwt>` against the IdP's public keys."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None
        if len(header) != 2:
            raise exceptions.AuthenticationFailed("Malformed Authorization header.")

        token = header[1].decode()
        claims = self._decode(token)
        user = self._user_for_claims(claims)
        return (user, token)

    def authenticate_header(self, request):
        return f'{self.keyword} realm="api"'

    def _decode(self, token):
        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                signing_key,
                algorithms=[settings.OIDC_RP_SIGN_ALGO],
                audience=settings.OIDC_API_AUDIENCE,
                issuer=settings.OIDC_OP_ISSUER,
                leeway=10,  # tolerate up to 10 s of NTP skew
            )
        except jwt.PyJWTError as exc:
            raise exceptions.AuthenticationFailed(f"Invalid token: {exc}") from exc

    @staticmethod
    def _user_for_claims(claims):
        employee_id = claims.get("employee_id") or claims.get("sub")
        if employee_id is None:
            raise exceptions.AuthenticationFailed("Token is missing employee_id.")
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError) as exc:
            raise exceptions.AuthenticationFailed("employee_id is not an integer.") from exc

        # get_or_create: an API client may legitimately be the first
        # contact a user has with Planly. Mirror the browser flow's
        # "auto-create on first login" behavior so service-account
        # tokens don't 401 just because nobody clicked Sign In yet.
        user, _ = User.objects.get_or_create(
            employee_id=employee_id,
            defaults={
                "email": claims.get("email", ""),
                "display_name": claims.get("name", ""),
            },
        )
        return user
```

Three settings need to land alongside this — they're not in the OIDC discovery document:

```python
# config/settings/base.py
OIDC_OP_JWKS_ENDPOINT = os.environ["OIDC_JWKS_URL"]
OIDC_OP_ISSUER = os.environ["OIDC_ISSUER"]
OIDC_API_AUDIENCE = os.environ["OIDC_API_AUDIENCE"]
```

`OIDC_OP_ISSUER` is the value the IdP puts in the JWT's `iss` claim. `OIDC_API_AUDIENCE` is the value it puts in `aud` — typically `"planly-api"` or whatever you registered when creating the OAuth client. Both are validated explicitly so a token issued for a *different* application can't be replayed at Planly.

Wire the new class into the DRF settings:

```python
# config/settings/base.py
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.api.authentication.OIDCJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    ...
}
```

`SessionAuthentication` stays — the browsable API at `/api/v1/docs/` and any in-app `fetch()` rely on the Django session that the OIDC login created.

---

## Step 6 — Remove the obsolete code

These pieces from earlier chapters become unreachable; delete them:

| Removed | Why |
|---|---|
| `templates/registration/login.html` | Browser flow now starts at `/oidc/authenticate/` |
| `path("accounts/", include("django.contrib.auth.urls"))` in `config/urls.py` | Auth views (login form, password reset) no longer routed |
| `User.set_password()` calls in seed scripts and tests | Externally authenticated; passwords are unusable |
| `SIMPLE_JWT = {...}` in `config/settings/base.py` | Library uninstalled |
| `from rest_framework_simplejwt.views import ...` and the `auth/token/...` URL block in `config/api_router.py` | IdP issues tokens; Planly doesn't |
| `apps/accounts/tests/test_api/test_views.py` JWT round-trip test (`test_jwt_auth_returns_current_user`) | Replaced by `OIDCJWTAuthentication` tests with mocked JWKS |

The `User` model and the `Membership.role` field are *unchanged*. The team scoping in every queryset (`for_user()`) is *unchanged*. The `IsTeamOwnerOrAdmin` permission from Chapter 16 is *unchanged*. SSO swaps the front door; the rooms behind it look the same.

---

## Step 7 — Migrating existing users

The user table from the dev seed (Chapter 11) and any production accounts created before SSO went live need their `employee_id` field to match what the IdP will issue. If the IdP and the local DB agree on `employee_id`, the first OIDC login finds the existing row via `filter_users_by_claims` and just updates the display_name / email. No data loss.

If they disagree, you have a one-time migration job:

```python
# apps/accounts/management/commands/sync_employee_ids.py
"""One-shot reconciliation for pre-SSO accounts.

Reads a CSV from the corporate directory mapping email → employee_id
and updates local Users. Idempotent — safe to re-run.
"""

import csv

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("csv_path")

    def handle(self, csv_path, **options):
        updated = 0
        skipped = 0
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                target_id = int(row["employee_id"])
                user = User.objects.filter(email=row["email"]).first()
                if user is None:
                    skipped += 1
                    continue
                if user.employee_id == target_id:
                    continue
                # employee_id is the PK — can't UPDATE in place. Insert
                # the new row, repoint FKs, drop the old. SQL-only since
                # Django's ORM won't reassign a PK.
                ...  # vendor-specific; see below
                updated += 1
        self.stdout.write(f"{updated} users updated, {skipped} not found")
```

Reassigning a primary key isn't an ORM-friendly operation; if your dataset is small, the cleanest path is "delete and let SSO re-create." If you have FKs from `Membership`, `Comment`, `Notification`, `Assignment`, etc., either run the SQL `UPDATE ... SET user_id = new` inside a transaction, or drop those FKs `ON UPDATE CASCADE` before running the rename.

For production you'd schedule this during a maintenance window, with a rollback that reverses the user_id mapping if SSO turns out to be misconfigured.

---

## Operational concerns

These show up reliably in corporate deploys:

### Internal CA certs

The IdP's TLS endpoint is almost always signed by the corporate root CA, not a public one. `requests` (which `mozilla-django-oidc` and `pyjwt`'s JWKS client both use) defaults to the system trust store. Two ways to wire the corporate CA:

1. **Build it into the image** — `COPY corporate-ca.crt /usr/local/share/ca-certificates/ && update-ca-certificates` in the Dockerfile. Most reliable; the bundle is identical across all containers.
2. **Mount via env var** — `REQUESTS_CA_BUNDLE=/etc/ssl/certs/corporate-ca.crt` in `.env.production`. Easier to update without rebuilding; the cert needs to live somewhere on the host.

Test it during deploy: `docker compose exec web uv run python -c 'import requests; requests.get(\"$OIDC_DISCOVERY_URL\")'` — a `SSLError` on this command means the CA isn't trusted yet, fix it before the first user attempts to log in.

### JWKS rotation and caching

`PyJWKClient(cache_keys=True, lifespan=3600)` caches the IdP's public keys for an hour. If the IdP rotates a key mid-cache, the next request signed with the new key fails. Two safety nets:

- `pyjwt` *does* automatically re-fetch JWKS on key-not-found (it tries the cache, then refreshes if missing).
- For multi-process gunicorn, the cache is per-worker — N workers means N JWKS fetches per hour, which is harmless. If the IdP rate-limits you, switch to a Redis-backed cache (set `cache_keys=False` and wrap the call yourself).

### Clock skew

`leeway=10` in the `jwt.decode()` call tolerates 10 seconds of NTP drift between Planly and the IdP. Without it, a token issued at 12:00:00 with a 2-second-fast Planly clock fails validation immediately. 10 seconds is generous; 30 is the upper bound where you should suspect a bigger problem.

### Group / role claims

Many IdPs include a `groups` or `roles` claim listing the user's directory groups. Map these to Planly's `Membership.role` by extending `update_user`:

```python
def update_user(self, user, claims):
    super().update_user(user, claims)  # the base attribute sync
    self._sync_memberships(user, claims.get("groups", []))
    return user

def _sync_memberships(self, user, group_names):
    """Map IdP group names to Planly Memberships.

    Convention: groups starting with `planly-` are recognized.
    `planly-team-eng` → membership in Team(name='eng') with role MEMBER.
    `planly-admin-eng` → ADMIN role in the same team.
    Anything else: ignored.
    """
    desired = {}
    for raw in group_names:
        if not raw.startswith("planly-"):
            continue
        ...  # parse, find Team, decide role
    # Reconcile: create new memberships, update changed roles, delete
    # memberships absent from `desired`.
```

This keeps the corporate directory as the source of truth — promote someone to admin in AD, they're an admin in Planly on their next login.

### Logout

`mozilla-django-oidc`'s logout view kills the Django session cookie. Whether it *also* kills the IdP session depends on whether `OIDC_OP_LOGOUT_URL_METHOD` returns a usable URL and whether the IdP supports RP-initiated logout. Some corporate IdPs intentionally don't — they want a single sign-on across many internal apps and a per-app logout shouldn't break that.

If your IdP doesn't honor RP-initiated logout, set `OIDC_OP_LOGOUT_URL_METHOD = None`. The user's Planly session ends; their IdP cookie persists; the next "Sign in" click silently re-authenticates them with the cert. Usually that's the right behavior on shared workstations.

### Service accounts

Some workloads (a nightly batch job, a Slack bot calling the API) need a non-human identity. The standard pattern is a *service account* in the IdP — a registered identity with no human owner that uses the OAuth2 *client credentials* grant to obtain a JWT. The service-account JWT looks identical to a human's JWT and is validated by the same `OIDCJWTAuthentication` class.

In our `_user_for_claims` method, the service account becomes a Planly User with a synthetic `employee_id` (your IdP's convention here — often a number above the human range, like `9000000+`). Its `Membership` rows determine what teams it can read; the rest of the auth pipeline doesn't care that there's no human behind the keyboard.

---

## Testing

Mocking the IdP is the path of least resistance. Three patterns:

### Mock the OIDC backend in browser-flow tests

```python
import pytest
from unittest.mock import patch
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
class TestOIDCLogin:
    def test_existing_user_logs_in(self, client):
        user = UserFactory(employee_id=1234)
        claims = {
            "employee_id": "1234",
            "email": user.email,
            "name": user.display_name,
        }
        with patch(
            "apps.accounts.auth.PlanlyOIDCBackend.get_userinfo",
            return_value=claims,
        ), patch(
            "apps.accounts.auth.PlanlyOIDCBackend.verify_token",
            return_value=claims,
        ):
            # The library's callback view exchanges the code for tokens,
            # then hands the (mocked) claims to our backend.
            response = client.get(
                reverse("oidc_authentication_callback"),
                {"code": "fake-code", "state": client.session["oidc_states"][0]},
            )
        assert response.status_code == 302
        assert "_auth_user_id" in client.session
```

Mocking `get_userinfo` and `verify_token` lets the test drive the *Planly side* of the flow without standing up an IdP.

### Mock JWKS in API tests

For `OIDCJWTAuthentication` tests, generate a throwaway RSA keypair in `conftest.py`, sign tokens with it, and patch the JWKS client to return that public key:

```python
@pytest.fixture(scope="session")
def rsa_keypair():
    from cryptography.hazmat.primitives.asymmetric import rsa
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def signed_jwt(rsa_keypair):
    import jwt
    def _sign(claims):
        return jwt.encode(claims, rsa_keypair, algorithm="RS256")
    return _sign


@pytest.fixture(autouse=True)
def patch_jwks(monkeypatch, rsa_keypair):
    """Make the module-level JWKS client return our test public key."""
    class _FakeKey:
        key = rsa_keypair.public_key()
    monkeypatch.setattr(
        "apps.accounts.api.authentication._jwks_client",
        type("_C", (), {"get_signing_key_from_jwt": lambda self, t: _FakeKey()})(),
    )
```

Then write the assertion-shaped tests:

```python
def test_valid_jwt_authenticates(api_client, signed_jwt, settings):
    user = UserFactory(employee_id=42)
    settings.OIDC_OP_ISSUER = "https://idp.test"
    settings.OIDC_API_AUDIENCE = "planly-api"
    token = signed_jwt({
        "iss": "https://idp.test",
        "aud": "planly-api",
        "sub": "42",
        "exp": int(time.time()) + 60,
    })
    response = api_client.get(
        "/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    assert response.status_code == 200
    assert response.data["employee_id"] == 42


def test_expired_jwt_is_rejected(api_client, signed_jwt):
    token = signed_jwt({
        "iss": "https://idp.test",
        "aud": "planly-api",
        "sub": "42",
        "exp": int(time.time()) - 60,  # expired
    })
    response = api_client.get(
        "/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    assert response.status_code == 401
```

This pattern means tests *exercise the whole validation pipeline* — the algorithm choice, audience check, issuer check, expiry math — without depending on an actual IdP being reachable.

---

## Deployment notes

### Required env vars in `.env.production`

```bash
# OIDC client
OIDC_DISCOVERY_URL=https://idp.corp.example.com/.well-known/openid-configuration
OIDC_CLIENT_ID=planly
OIDC_CLIENT_SECRET=<from-IdP-client-registration>

# Endpoints not in discovery (some IdPs don't publish them)
OIDC_JWKS_URL=https://idp.corp.example.com/jwks.json
OIDC_ISSUER=https://idp.corp.example.com
OIDC_API_AUDIENCE=planly-api

# Corporate CA bundle, if needed
REQUESTS_CA_BUNDLE=/etc/ssl/certs/corporate-ca.crt
```

The `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET` come from the IdP team when they register Planly as an OAuth client. Ask them to allow:

- **Redirect URI**: `https://planly.corp.example.com/oidc/callback/`
- **Post-logout redirect URI**: `https://planly.corp.example.com/`
- **Grant types**: `authorization_code` for the browser flow, plus `client_credentials` if you'll have service accounts
- **Required scopes**: `openid email profile` plus any custom scope that releases `employee_id` (the discovery document or your IdP's docs will tell you the exact name)
- **Token signing**: `RS256` (default for every modern IdP)
- **PKCE**: required (the library always sends a code challenge; an IdP that *requires* PKCE-or-no-PKCE works fine either way)

### GitLab CI implications

The bootstrap CI from Chapter 3 runs against a Postgres service; it does *not* talk to the corporate IdP. Two adjustments make CI continue to pass with SSO wired in:

1. **Stub the OIDC env vars** in the `pytest` job's `variables:` block — values just sufficient for `mozilla-django-oidc` to import without crashing. The OIDC integration tests use mocks (above), not real network calls.
2. **Drop `--no-migrations`-equivalent skip** — the OIDC migration (none in our case; `mozilla-django-oidc` is sessionless) doesn't need DB changes, but if you add one, CI's existing migration-on-fresh-DB flow handles it.

```yaml
# .gitlab-ci.yml — extend the existing pytest job
pytest:
  stage: test
  services:
    - name: postgres:17
      alias: db
  variables:
    POSTGRES_DB: planly
    POSTGRES_USER: planly
    POSTGRES_PASSWORD: planly
    DB_HOST: db
    DB_NAME: planly
    DB_USER: planly
    DB_PASSWORD: planly
    DJANGO_SECRET_KEY: ci-secret-not-for-production
    # Stub OIDC vars so settings load doesn't error. Tests mock these
    # endpoints; we never make real network calls in CI.
    OIDC_DISCOVERY_URL: https://idp.test/.well-known/openid-configuration
    OIDC_CLIENT_ID: ci-client
    OIDC_CLIENT_SECRET: ci-secret
    OIDC_JWKS_URL: https://idp.test/jwks.json
    OIDC_ISSUER: https://idp.test
    OIDC_API_AUDIENCE: planly-api
  script:
    - uv run pytest --cov
```

The `deploy-check` job (Chapter 16) needs the same stubs, plus the production-only ones; mirror the pattern.

---

## What stays unchanged

It's worth listing what *doesn't* change when SSO replaces the password flow, because the answer is "almost everything":

- **The `User` model** — same fields, same methods, same `employee_id` PK
- **The `Team` and `Membership` models** — unchanged
- **`for_user()` queryset method** on every model — unchanged
- **`IsTeamOwnerOrAdmin` and `IsAuthenticated` permissions** — unchanged
- **The kanban board, plan list, task detail, every other view** — all view-level code is identical; the only difference is *how* `request.user` was identified
- **The Django admin** — keeps working via `ModelBackend` for any local superuser you create explicitly. In a stricter posture, configure the admin to require OIDC too — but most teams keep one local superuser as a break-glass account for the day SSO breaks.
- **The full-text search, the API, the notifications, the background tasks** — unchanged
- **Tests for everything except the auth path** — unchanged

The whole point of layering SSO on top of a queryset-scoping authorization model is exactly this: *authorization* (who can see what) doesn't depend on *authentication* (how we proved who you are). The two are decoupled, so swapping one out doesn't ripple into the other.

---

## Suggested commit message (when you implement this)

```
add corporate SSO via OIDC; remove password and self-issued JWT auth

* uv add mozilla-django-oidc 'pyjwt[crypto]'; uv remove
  djangorestframework-simplejwt
* config/settings/base.py: OIDC_OP_DISCOVERY_ENDPOINT,
  OIDC_RP_*, OIDC_USE_PKCE, OIDC_OP_JWKS_ENDPOINT, OIDC_OP_ISSUER,
  OIDC_API_AUDIENCE; add mozilla_django_oidc to INSTALLED_APPS;
  AUTHENTICATION_BACKENDS list with PlanlyOIDCBackend first; remove
  SIMPLE_JWT block; LOGIN_URL → "oidc_authentication_init"
* apps/accounts/auth.py: PlanlyOIDCBackend mapping JWT claims onto
  the User model via employee_id (not email); set_unusable_password
  on every OIDC-created user; verify_claims rejects when
  employee_id is missing; provider_logout for RP-initiated IdP
  logout
* apps/accounts/api/authentication.py: OIDCJWTAuthentication
  validates Bearer tokens against the IdP's JWKS via pyjwt
  PyJWKClient (cached 1h); leeway=10 for NTP skew; auto-creates
  Users for first-contact API clients
* config/api_router.py: remove TokenObtainPairView /
  TokenRefreshView / TokenVerifyView; replace
  rest_framework_simplejwt.JWTAuthentication with
  apps.accounts.api.authentication.OIDCJWTAuthentication in
  REST_FRAMEWORK[DEFAULT_AUTHENTICATION_CLASSES]
* config/urls.py: add path("oidc/", include("mozilla_django_oidc.urls"));
  remove path("accounts/", include("django.contrib.auth.urls"))
* templates/registration/login.html: removed (browser flow now starts
  at /oidc/authenticate/)
* tests rewritten to mock get_userinfo + verify_token for the
  browser flow; the API auth tests use a session-scoped RSA keypair
  fixture that signs test tokens, with a monkeypatched JWKS client
* docs/tutorial/appendix-a-corporate-sso.md
```

---

## Where this leaves us

With this appendix applied, Planly authenticates entirely through the corporate IdP — passwords are never typed, never stored, never validated. The local `User` row is a *cache* of directory data; the IdP is the source of truth.

Add-on work that becomes natural to layer in next:

- **Group → Membership sync** (sketched above in "Group / role claims") — fully automate team membership from the corporate directory
- **Service-account JWTs** for the nightly batch jobs and any internal services that talk to Planly's API
- **Audit logging of authn events** — every successful and failed OIDC login written to a separate audit log so security can replay incidents
- **Re-enable Django admin SSO-only** by removing `ModelBackend` from `AUTHENTICATION_BACKENDS` and accepting that admin access requires a corporate cert too

Each of those is a focused additive change; none of them require revisiting the SSO core. The auth swap pays for itself the day the corporate password rotation policy changes and Planly doesn't have to care.
