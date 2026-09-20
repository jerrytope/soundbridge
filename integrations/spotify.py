"""Spotify catalog search. Ported from server/spotify.js.

Client-credentials authentication, so this covers public catalog endpoints
only: it does not reach playlists, listening history or Spotify for Artists
analytics, which need user consent and an authorization-code flow. Tokens and
secrets never reach the browser.
"""
import base64
import threading
import time

import requests
from django.conf import settings

TOKEN_URL = 'https://accounts.spotify.com/api/token'
SEARCH_URL = 'https://api.spotify.com/v1/search'
TYPES = ('artist', 'album', 'track')
TIMEOUT = 15

_lock = threading.Lock()
_token = None
_expires = 0.0
_blocked_until = 0.0


class SpotifyError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status
        self.message = message


def configured():
    return bool(settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET)


def _access_token(session=requests, force=False):
    """Cached until shortly before expiry, as the Node adapter did."""
    global _token, _expires
    with _lock:
        if _token and not force and time.time() < _expires:
            return _token
    credentials = f'{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}'.encode('utf-8')
    try:
        response = session.post(
            TOKEN_URL,
            headers={
                'Authorization': 'Basic ' + base64.b64encode(credentials).decode('ascii'),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data='grant_type=client_credentials',
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        raise SpotifyError('Spotify could not be reached. Please retry.')
    if response.status_code != 200:
        raise SpotifyError('Spotify authentication failed. Check the server credentials and app access.')
    result = response.json()
    token = result.get('access_token')
    lifetime = result.get('expires_in')
    if not isinstance(token, str) or not isinstance(lifetime, (int, float)) or lifetime <= 0:
        raise SpotifyError('Spotify returned an invalid token response.')
    with _lock:
        _token = token
        _expires = time.time() + max(0, lifetime - 60)
    return token


def search(query, kind='artist', market='NG', session=requests):
    global _blocked_until
    if not configured():
        raise SpotifyError(
            'Spotify is not connected. Add the Spotify client ID and secret on the server.', 503
        )
    query = (query or '').strip()
    if not query or len(query) > 150 or kind not in TYPES or not (len(market) == 2 and market.isalpha() and market.isupper()):
        raise SpotifyError('Enter a search term, valid type and two-letter market.', 400)
    if time.time() < _blocked_until:
        raise SpotifyError('Spotify is rate-limiting requests. Please try again later.', 429)
    params = {'q': query, 'type': kind, 'market': market, 'limit': '10'}
    response = None
    for attempt in range(2):
        try:
            response = session.get(
                SEARCH_URL,
                params=params,
                headers={'Authorization': f'Bearer {_access_token(session, force=attempt > 0)}'},
                timeout=TIMEOUT,
            )
        except requests.RequestException:
            raise SpotifyError('Spotify could not be reached. Please retry.')
        if response.status_code != 401:
            break
    if response.status_code == 429:
        seconds = response.headers.get('retry-after')
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = 30
        with _lock:
            _blocked_until = time.time() + min(3600, max(1, seconds))
        raise SpotifyError('Spotify is rate-limiting requests. Please try again later.', 429)
    if response.status_code != 200:
        if response.status_code == 403:
            raise SpotifyError(
                'Spotify denied access. Check your Spotify developer app permissions and quota mode.'
            )
        raise SpotifyError('Spotify search is unavailable. Please retry.')
    payload = response.json()
    items = payload.get(f'{kind}s', {}).get('items')
    if not isinstance(items, list):
        raise SpotifyError('Spotify returned an unreadable search response.')
    results = []
    for item in items:
        if not item or not isinstance(item.get('name'), str):
            continue
        url = (item.get('external_urls') or {}).get('spotify', '')
        if not url.startswith('https://open.spotify.com/'):
            continue
        results.append(
            {
                'id': item.get('id'),
                'name': item['name'],
                'type': kind,
                'url': url,
                'artists': [
                    artist.get('name')
                    for artist in item.get('artists', [])
                    if isinstance(artist.get('name'), str)
                ],
                'releaseDate': item.get('release_date') or (item.get('album') or {}).get('release_date', ''),
            }
        )
    return {'source': 'Spotify', 'items': results}
