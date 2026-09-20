from django.urls import path

from apiv1 import views

urlpatterns = [
    path('health', views.health),
    path('auth/signup', views.signup),
    path('auth/login', views.signin),
    path('auth/session', views.session),
    path('auth/logout', views.sign_out),
    path('workspace', views.workspace),
    path('images', views.images),
    path('images/<uuid:image_id>', views.image_detail),
    path('integrations/status', views.integrations_status),
    path('music/search', views.music_search),
    path('ai/status', views.ai_status),
    path('ai/chat', views.ai_chat),
]
