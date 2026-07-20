from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_expected_api_routes_exist():
    paths = {route.path for route in app.routes}
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/refresh" in paths
    assert "/api/v1/projects" in paths
    assert "/api/v1/projects/{project_id}/documents" in paths
    assert "/api/v1/projects/{project_id}/documents/{document_id}/status" in paths
    assert "/api/v1/projects/{project_id}/query" in paths
    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths
