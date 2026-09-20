"""Template context shared by every signed-in screen."""
from accounts.navigation import NAVIGATION


def shell(request):
    profile = None
    if getattr(request, 'user', None) and request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
    page = request.path.strip('/').replace('-', ' ')
    for item in NAVIGATION:
        if request.path == '/' + item['path']:
            page = item['label']
    return {'navigation': NAVIGATION, 'current_path': request.path, 'profile': profile, 'current_page': page}
