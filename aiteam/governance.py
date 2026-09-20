from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from accounts.models import Consent
from aiteam.models import ContextPreference, Feedback, Conversation, Message
from operations.services import audit


@login_required
@require_http_methods(["GET", "POST"])
def context_settings(request):
    class ContextForm(forms.ModelForm):
        class Meta:
            model = ContextPreference
            fields = ["profile", "brief", "releases", "royalties"]
            labels = {
                "profile": "Share my profile and goals",
                "brief": "Share my project brief",
                "releases": "Share my release plans",
                "royalties": "Share my royalty sources and income totals",
            }

    preference, _ = ContextPreference.objects.get_or_create(user=request.user)
    form = ContextForm(request.POST or None, instance=preference)
    if request.method == "POST" and form.is_valid():
        form.save()
        Consent.objects.create(
            user=request.user,
            purpose="ai-context",
            version="1",
            granted=any(form.cleaned_data.values()),
        )
        # Changing permissions discards old snapshots, so revoked data is not reused.
        request.user.ai_conversations.update(context={}, handoff=None)
        audit(request.user, "ai.context.permissions.updated", preference)
        messages.success(
            request, "Context permissions saved. Existing context snapshots cleared."
        )
        return redirect("/assistants")
    return render(
        request,
        "form.html",
        {
            "form": form,
            "title": "Choose AI context",
            "description": "Only selected account data will be shared with the model provider. Your messages are sent when you request a response. Previously sent messages may already contain information; delete those conversations if you no longer want to reuse their history.",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def feedback(request, message_id):
    row = get_object_or_404(
        Message, pk=message_id, conversation__owner=request.user, role="assistant"
    )

    class FeedbackForm(forms.ModelForm):
        class Meta:
            model = Feedback
            fields = ["rating", "details"]

    form = FeedbackForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.message = row
        item.user = request.user
        item.save()
        if item.rating == "harmful":
            row.conversation.safety_state = "flagged"
            row.conversation.save(update_fields=["safety_state"])
        audit(request.user, "ai.feedback.received", item)
        return redirect(
            f"/assistants?agent={row.conversation.agent_id}&session={row.conversation_id}"
        )
    return render(
        request, "form.html", {"form": form, "title": "Rate or report this response"}
    )


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    row = get_object_or_404(Conversation, pk=conversation_id, owner=request.user)
    audit(request.user, "ai.conversation.deleted", row)
    row.delete()
    messages.success(request, "Conversation and its saved deliverables deleted.")
    return redirect("/assistants")
