"""Port of server/request-policy.js.

Development serves loopback only; a deployment must declare its public origin
and is then held to it.
"""
from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse


def _is_local(host: str) -> bool:
    name = host.split(':')[0].strip('[]')
    return name in ('127.0.0.1', 'localhost', '::1')


class RequestPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.public_origin = settings.PUBLIC_ORIGIN

    def __call__(self, request):
        host = request.META.get('HTTP_HOST', '')
        if self.public_origin:
            expected = self.public_origin.split('://', 1)[-1].split(':')[0]
            if host and host.split(':')[0] != expected:
                return self._reject(request, 'This host is not configured for SoundBridge.')
        elif host and not _is_local(host):
            return self._reject(request, 'SoundBridge accepts local connections only in development.')
        return self.get_response(request)

    @staticmethod
    def _reject(request, message):
        if request.path.startswith('/api/'):
            return JsonResponse({'error': message}, status=403)
        return HttpResponseForbidden(message)
