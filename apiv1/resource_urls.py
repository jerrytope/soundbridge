from django.urls import path

from apiv1 import resources as api

urlpatterns = [
    path("profiles/me", api.profile),
    path("goals", api.goals),
    path("credits", api.credits),
    path("connections", api.connections),
    path("connections/<uuid:connection_id>", api.connection_action),
    path("connections/<uuid:connection_id>/messages", api.messages),
    path("collaborations", api.collaborations),
    path("opportunities", api.opportunities),
    path("royalty-calculations", api.calculations),
    path("release-projects", api.releases),
    path("manual-income", api.income),
    path("notifications", api.notifications),
    path("royalty-statements", api.statements),
    path("royalty-statements/<uuid:statement_id>/transactions", api.statement_rows),
    path("ai-conversations", api.ai_conversations),
    path("ai-conversations/<uuid:conversation_id>", api.ai_conversation),
    path("subscriptions/me", api.subscriptions),
    path("entitlements", api.entitlements),
    path("reports", api.reports),
]
