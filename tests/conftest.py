import pytest
from fastapi.testclient import TestClient

from app import create_app


@pytest.fixture
def app():
    # Membuat instance aplikasi untuk testing
    return create_app()


@pytest.fixture
def client(app):
    # Menggunakan "with" agar startup/shutdown aplikasi dijalankan per test
    with TestClient(app) as client:
        yield client
