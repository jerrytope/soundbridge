from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from accounts.forms import ProfileForm, CreditForm, ProfileLinkForm
from accounts.models import CreatorProfile, StoredImage
from accounts.security import verified, verified_filter
from operations.services import audit


@login_required
@require_http_methods(["GET", "POST"])
def professional_profile(request):
    profile = request.user.profile
    form = ProfileForm(request.POST or None, instance=profile)
    credit_form = CreditForm()
    link_form = ProfileLinkForm()
    if request.method == "POST":
        action = request.POST.get("action", "profile")
        if action == "profile" and form.is_valid():
            form.save()
            audit(request.user, "profile.updated", profile)
            messages.success(request, "Profile updated.")
            return redirect(request.path)
        elif action in ("credit", "link"):
            form = ProfileForm(instance=profile)
            child = (
                CreditForm(request.POST)
                if action == "credit"
                else ProfileLinkForm(request.POST)
            )
            if child.is_valid():
                obj = child.save(commit=False)
                obj.profile = profile
                obj.save()
                audit(request.user, f"profile.{action}.added", obj)
                return redirect(request.path)
            if action == "credit":
                credit_form = child
            else:
                link_form = child
        elif action in ("delete-credit", "delete-link"):
            manager = profile.credits if action == "delete-credit" else profile.links
            obj = get_object_or_404(manager, pk=request.POST.get("id"))
            audit(request.user, "profile.item.deleted", obj)
            obj.delete()
            return redirect(request.path)
    return render(
        request,
        "accounts/professional.html",
        {"form": form, "credit_form": credit_form, "link_form": link_form},
    )


def public_profile(request, username):
    profile = get_object_or_404(
        CreatorProfile.objects.select_related("user"), username=username
    )
    owner = request.user.is_authenticated and request.user.pk == profile.user_id
    if not owner and (
        not profile.published
        or not verified(profile.user)
        or not profile.user.is_active
    ):
        raise Http404
    if request.user.is_authenticated and not owner:
        from network.services import blocked

        if blocked(request.user, profile.user):
            raise Http404
    return render(
        request,
        "accounts/public_profile.html",
        {
            "creator_profile": profile,
            "is_owner": owner,
            "public_links": profile.links.filter(public=True),
        },
    )


def public_photo(request, username):
    profile = get_object_or_404(
        CreatorProfile,
        verified_filter("user__"),
        username=username,
        published=True,
        photo_public=True,
        user__is_active=True,
    )
    if not profile.photo.startswith("/api/images/"):
        raise Http404
    image = get_object_or_404(
        StoredImage, id=profile.photo.rsplit("/", 1)[-1], user=profile.user
    )
    response = HttpResponse(image.data(), content_type="image/jpeg")
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
