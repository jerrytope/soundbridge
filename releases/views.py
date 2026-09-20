"""Release planner screen (also used for the /release-setup onboarding step)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from accounts.images import ImageError, store_upload
from accounts.models import StoredImage
from accounts.views import _bump
from releases.models import CHECKLIST, ReleaseProject, ReleaseTask


@login_required
def planner(request):
    """Port of the Releases component in src/main.jsx."""
    if request.method == 'POST':
        action = request.POST.get('action', 'create')
        if action == 'create':
            _create(request)
        elif action == 'toggle-task':
            task = get_object_or_404(ReleaseTask, pk=request.POST.get('task'), release__owner=request.user)
            task.done = not task.done
            task.save(update_fields=['done'])
        elif action == 'add-task':
            release = get_object_or_404(ReleaseProject, pk=request.POST.get('release'), owner=request.user)
            title = (request.POST.get('task') or '').strip()
            if title:
                ReleaseTask.objects.create(
                    release=release,
                    title=title[:2000],
                    position=release.tasks.count(),
                )
        elif action == 'artwork':
            _artwork(request)
        elif action == 'remove-artwork':
            release = get_object_or_404(ReleaseProject, pk=request.POST.get('release'), owner=request.user)
            _clear_artwork(request, release)
        _bump(request.user)
        return redirect(request.path)
    releases = []
    for release in ReleaseProject.objects.filter(owner=request.user).prefetch_related('tasks'):
        tasks = list(release.tasks.all())
        release.task_list = tasks
        release.total = len(tasks)
        release.done = sum(1 for task in tasks if task.done)
        release.percent = round(100 * release.done / release.total) if release.total else 0
        releases.append(release)
    return render(
        request,
        'releases.html',
        {
            'releases': releases,
            'types': ['Single', 'EP', 'Album'],
            'current_page': 'Release Planner',
        },
    )


def _create(request):
    title = (request.POST.get('title') or '').strip()
    date = parse_date(request.POST.get('date') or '')
    kind = request.POST.get('type') or 'Single'
    if not title or not date or kind not in ('Single', 'EP', 'Album'):
        messages.info(request, 'Enter a release title, date and type.')
        return
    from billing.services import EntitlementRequired, check

    try:
        check(
            request.user,
            'release_plans',
            ReleaseProject.objects.filter(owner=request.user).count(),
            'Release plans',
        )
    except EntitlementRequired as limited:
        messages.info(request, limited.message)
        return
    release = ReleaseProject.objects.create(owner=request.user, title=title[:300], date=date, type=kind)
    ReleaseTask.objects.bulk_create(
        [
            ReleaseTask(release=release, title=item, position=index)
            for index, item in enumerate(CHECKLIST)
        ]
    )


def _artwork(request):
    release = get_object_or_404(ReleaseProject, pk=request.POST.get('release'), owner=request.user)
    upload = request.FILES.get('image')
    if not upload:
        return
    try:
        image = store_upload(request.user, upload)
    except ImageError as problem:
        messages.info(request, str(problem))
        return
    previous = release.artwork
    release.artwork = image.url
    release.save(update_fields=['artwork'])
    if previous.startswith('/api/images/'):
        StoredImage.objects.filter(user=request.user, id=previous.rsplit('/', 1)[-1]).delete()


def _clear_artwork(request, release):
    previous = release.artwork
    release.artwork = ''
    release.save(update_fields=['artwork'])
    if previous.startswith('/api/images/'):
        StoredImage.objects.filter(user=request.user, id=previous.rsplit('/', 1)[-1]).delete()
