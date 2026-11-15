import hmac

from django.conf import settings
from django.http import JsonResponse


class ApiKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/") and request.path != "/api/health/":
            expected = settings.EARTHEREAL_API_KEY
            supplied = request.headers.get("X-EarthEReal-API-Key", "")
            if expected:
                valid = hmac.compare_digest(supplied, expected)
            else:
                valid = settings.DEBUG
            if not valid:
                return JsonResponse({"error": "Missing or invalid backend API key."},
                                    status=401)
        return self.get_response(request)
