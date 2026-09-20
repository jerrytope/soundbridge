"""Music Search screen and the integration status it reads."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apiv1.limits import limit_request
from integrations.spotify import SpotifyError, configured, search


@login_required
def music_search(request):
    """Port of src/backend/MusicSearch.jsx."""
    error = ''
    items = None
    query = request.GET.get('q', '')
    kind = request.GET.get('type', 'artist')
    market = request.GET.get('market', 'NG')
    if query:
        try:
            limit_request(f'music:{request.user.id}', 20)
            items = search(query, kind, market)['items']
        except SpotifyError as problem:
            error = problem.message
        except ValueError as problem:
            error = str(problem)
    return render(
        request,
        'music_search.html',
        {
            'status': {
                'openai': bool(settings.OPENAI_API_KEY and settings.OPENAI_MODEL),
                'spotify': configured(),
            },
            'items': items,
            'error': error,
            'q': query,
            'type': kind,
            'market': market,
            'current_page': 'Music Search',
        },
    )
