> Current Django setup, versioned resource APIs, workers and release limitations are documented in [MVP operations](docs/MVP_OPERATIONS.md) and [implementation status](plans/mvp_implementation_status.md). The legacy workspace write API described below is retired (410).

# SoundBridge backend and API setup

## Run the app

Requires Python 3.12 or newer.

```sh
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_creators
python manage.py runserver 127.0.0.1:8000
```

Accounts, profiles, connections, collaborations, releases, royalty data, images, AI conversations and
session records all live in `.data/django.sqlite3`. No separate database service is needed. Use the
same hostname consistently: `localhost` and `127.0.0.1` keep separate cookies.

Development accepts loopback connections only. A deployment must set `SOUNDBRIDGE_PUBLIC_ORIGIN`; the
origin middleware then rejects any other host, cookies become `Secure`, HSTS and the HTTPS redirect
switch on, and registration closes unless `SOUNDBRIDGE_ALLOW_SIGNUP=true`.

## Connect OpenAI

1. Create a project API key in the [OpenAI API platform](https://platform.openai.com/api-keys) and set
   up billing or credits for that project.
2. Copy `.env.example` to `.env.local` if it does not exist, then edit it without removing other
   settings.
3. Set the server-only values:

```dotenv
OPENAI_API_KEY=your_actual_project_key
OPENAI_MODEL=gpt-4.1
```

The model must be one your project can use and must support structured output through the Responses
API.

4. Restart the server, sign in, open `/assistants` and send a short message. The status indicator only
   reports whether credentials are present; only a real request proves the key, billing and model
   access work.

Request path:

```text
/assistants → aiteam.gateway → OpenAI Responses API → the conversation thread
```

`aiteam/gateway.py` selects the specialist instructions, validates the request, sends the key as a
Bearer token, and uses `store: false`, a request timeout, a concurrency cap and a short-window
request cap. Each account also has an allowance of 30 request attempts per UTC day
(`SOUNDBRIDGE_AI_DAILY_LIMIT`). That is a request allowance, not a spending guarantee — set spending
controls with the provider as well.

Keys belong on the server only: never in a template, a static file, browser storage, a screenshot or a
chat message. `.env.local` is ignored by git.

## Connect Spotify catalog search

1. Create an app in the [Spotify developer dashboard](https://developer.spotify.com/dashboard).
2. Add its credentials to `.env.local`:

```dotenv
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
```

3. Restart the server, sign in, open `/music-search`, choose a market and search.

`integrations/spotify.py` exchanges the credentials for a short-lived token, caches it until shortly
before expiry, retries once on an expired token, and handles upstream rate limiting with a cool-off.
Tokens and secrets never reach the browser.

This is [client-credentials authentication](https://developer.spotify.com/documentation/web-api/tutorials/client-credentials-flow),
which covers public catalog endpoints only. Personal playlists, listening history and Spotify for
Artists analytics need user consent through an authorization-code flow, which is not implemented.

## Adding another provider

Put the adapter in its own module under `integrations/`, calling a fixed provider URL and translating
the response into the fields a screen needs. Read credentials from settings, never from a template.
Add the route in `config/urls.py` (or `apiv1/urls.py` for the JSON API), and add tests with mocked
responses covering success, authorization failure and rate limiting.

For personal account connections, add a server-side authorization-code flow with state validation,
PKCE where supported, minimal scopes, encrypted token storage, refresh and disconnect. For payments,
keep secret keys on the server, verify webhook signatures and make fulfilment idempotent. Neither is
implemented; adding a key is not the same as completing those flows.

## API contract

The JSON API from the earlier Node server is preserved, so existing clients — including the React app
in `src/` — work against this server unchanged.

| Route | Method | Purpose |
| --- | --- | --- |
| `/api/health` | GET | Liveness and storage kind |
| `/api/auth/signup` | POST | Create an account and a session |
| `/api/auth/login` | POST | Verify a password and create a session |
| `/api/auth/session` | GET | Restore the session and workspace |
| `/api/auth/logout` | POST | Revoke the current session |
| `/api/workspace` | GET, PUT | Read and save the workspace with a revision check |
| `/api/images` | POST | Decode, resize and store a private image |
| `/api/images/<id>` | GET, DELETE | Owner-only read; delete refuses an image still in use |
| `/api/integrations/status` | GET | Whether OpenAI and Spotify are configured |
| `/api/music/search` | GET | Spotify catalog search |
| `/api/ai/status` | GET | Whether the AI connection is configured |
| `/api/ai/chat` | POST | Specialist response |

Preserved behaviour: a stale revision on `PUT /api/workspace` returns 409; a write whose
`X-Soundbridge-Account` header does not match the signed-in account returns 409; authentication is
capped at 10 requests a minute and catalog search at 20; workspace field limits and error strings are
unchanged; and a workspace may only reference images its own account owns.

## Architecture

- `config/` — settings, URL map, origin policy middleware, legacy page serving.
- `accounts/` — the email-login user, profile, private image storage, and a password hasher that
  accepts the `salt:scrypt-hex` format the Node server wrote, so imported accounts sign in unchanged.
- `network/`, `releases/`, `royalties/`, `aiteam/` — the product entities, modelled per section 13.1 of
  the PRD, with every monetary column a decimal carrying its own currency.
- `apiv1/serializers.py` — translates those models to and from the workspace JSON contract.
- `templates/` and `static/` — the screens, using the original stylesheets unchanged.

## Data protection

Uploads are limited by type and size, re-encoded through Pillow rather than stored as received, capped
at 20 MB per account, and served only to their owner with `Cache-Control: private, no-store`. Original
statement CSVs are retained with the statement for traceability and are removed when it is deleted.
Sessions are `HttpOnly`, `SameSite=Strict` cookies with a seven-day lifetime. Uploaded documents and
saved context are treated as untrusted data when they reach the model gateway.
