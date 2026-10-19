"""Smoke test of the FastAPI shell after the legacy modules were removed."""

import pytest


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.parametrize(
    "path",
    ["/api/pole/calculate", "/api/load-object/calculate", "/api/opening-part/calculate"],
)
def test_legacy_endpoints_are_gone(client, path):
    assert client.post(path, json={}).status_code == 404