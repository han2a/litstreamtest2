from django.test import SimpleTestCase, override_settings


class ApiKeyMiddlewareTests(SimpleTestCase):
    @override_settings(EARTHEREAL_API_KEY="test-shared-key")
    def test_api_routes_require_the_shared_key(self):
        response = self.client.get("/api/not-a-real-endpoint/")
        self.assertEqual(response.status_code, 401)

        response = self.client.get(
            "/api/not-a-real-endpoint/",
            HTTP_X_EARTHEREAL_API_KEY="test-shared-key",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(EARTHEREAL_API_KEY="test-shared-key")
    def test_health_endpoint_is_public_for_host_health_checks(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
