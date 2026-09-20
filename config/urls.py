"""URL map.

Every path the React router served is served here, so existing links, bookmarks
and the legacy pages keep working.
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from billing import views as billing_views
from operations import views as operations_views
from accounts import access_views, profile_views, onboarding
from network import people_views, collaboration_views, opportunity_views
from django.urls import include, path, re_path

from accounts import views as accounts_views
from aiteam import views as ai_views
from aiteam import governance as ai_governance
from config import legacy
from integrations import views as integrations_views
from network import views as network_views
from releases import views as releases_views
from releases import detail_views as release_detail_views
from royalties import views as royalties_views
from royalties import money_views, import_views

urlpatterns = [
    path("assistants/context", ai_governance.context_settings),
    path("assistants/feedback/<uuid:message_id>", ai_governance.feedback),
    path("assistants/delete/<uuid:conversation_id>", ai_governance.delete_conversation),
    path("setup/continue/<str:step>", onboarding.complete_step),
    path("releases/<uuid:release_id>", release_detail_views.detail),
    path("releases/tasks/<uuid:task_id>", release_detail_views.task),
    path("collaborations/invitations", collaboration_views.invitations),
    path("collaborations/files/<uuid:file_id>", collaboration_views.file_download),
    path("collaborations/<uuid:project_id>", collaboration_views.workspace),
    path("royalties/imports/<uuid:batch_id>", import_views.review),
    path("royalties/statements/<uuid:statement_id>/export", import_views.export),
    path("royalties/calculations/<uuid:calculation_id>", money_views.calculation),
    path("royalties/income", money_views.manual_income),
    path("royalties/income/<uuid:income_id>", money_views.manual_income),
    path("royalties/summary", money_views.summaries),
    path("royalties/education", money_views.education),
    path("notifications", operations_views.notifications),
    path("settings/privacy", operations_views.privacy),
    path("privacy/downloads/<uuid:artifact_id>", operations_views.download_artifact),
    path("legal/<str:document>", operations_views.legal),
    path("settings/professional", profile_views.professional_profile),
    path("people/<slug:username>", profile_views.public_profile),
    path("people/<slug:username>/photo", profile_views.public_photo),
    path("connections", people_views.connections),
    path("connections/request/<uuid:user_id>", people_views.connect),
    path("connections/block/<uuid:user_id>", people_views.block),
    path("connections/<uuid:connection_id>", people_views.connection_action),
    path("messages/<uuid:connection_id>", people_views.thread),
    path("reports/new", people_views.report),
    path("admin/", admin.site.urls),
    path("verify-email", access_views.verification),
    path("verify-email/<str:token>", access_views.confirm_email),
    path("password-reset", access_views.PasswordResetView.as_view()),
    path(
        "password-reset/sent",
        TemplateView.as_view(
            template_name="accounts/recovery.html",
            extra_context={
                "title": "Check your email",
                "recovery_message": "If this address has an active account, a recovery email has been sent.",
            },
        ),
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/recovery.html",
            success_url="/password-reset/complete",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete",
        TemplateView.as_view(
            template_name="accounts/recovery.html",
            extra_context={
                "title": "Password updated",
                "recovery_message": "Sign in with your new password.",
            },
        ),
    ),
    path("api/v1/", include("apiv1.resource_urls")),
    path("api/", include("apiv1.urls")),
    # Public and access
    path("", accounts_views.landing),
    path("signup", accounts_views.signup),
    path("sign-out", accounts_views.sign_out),
    # Onboarding
    path("onboarding", accounts_views.setup, {"step": "onboarding"}),
    path("goals", accounts_views.setup, {"step": "goals"}),
    path("genres", accounts_views.setup, {"step": "genres"}),
    path("profile-setup", profile_views.professional_profile),
    path("royalty-setup", royalties_views.setup),
    path("release-setup", releases_views.planner),
    # Workspace
    path("portal", network_views.dashboard),
    path("discover", people_views.discover),
    path("discover/save/<int:external_id>", network_views.save_creator),
    path("creators/<int:external_id>", network_views.creator_detail),
    path("collaborations", network_views.collaborations),
    path("opportunities", opportunity_views.directory),
    path("analytics", network_views.analytics),
    path("release-planner", releases_views.planner),
    path("royalties", royalties_views.overview),
    path("royalty-calculator", money_views.calculator),
    path("royalty-upload", import_views.upload),
    path("royalty-upload/sample", royalties_views.sample_csv),
    path("music-search", integrations_views.music_search),
    path("membership", billing_views.membership),
    path("membership/checkout", billing_views.checkout),
    path("membership/cancel", billing_views.cancel),
    path("billing/webhook", billing_views.webhook),
    path("settings", accounts_views.profile_view),
    path("settings/export", accounts_views.export_workspace),
    # AI Team
    path("assistants", ai_views.studio),
    path("assistants/start", ai_views.start_session),
    path("assistants/send", ai_views.send_message),
    path("assistants/draft", ai_views.save_draft),
    path("assistants/save", ai_views.save_deliverable),
    path("assistants/handoff", ai_views.handoff),
    path("assistants/refresh", ai_views.refresh_context),
    path("assistants/brief", ai_views.save_brief),
    path("assistants/actions", ai_views.apply_actions),
    path("assistants/work/<uuid:deliverable_id>.txt", ai_views.download_work),
    # The original static prototype, as the React Legacy route served it.
    re_path(r"^(?P<page>[a-z-]+)\.html$", legacy.page),
    re_path(r"^legacy/(?P<asset>[a-z-]+\.(?:css|js))$", legacy.asset),
    # The prototype pages link their stylesheets and scripts from the site root.
    re_path(r"^(?P<asset>[a-z-]+\.(?:css|js))$", legacy.asset),
]

handler404 = "config.legacy.not_found"
