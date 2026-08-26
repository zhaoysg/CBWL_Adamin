"""应用入口健康探针测试。"""

from fastapi.testclient import TestClient


def test_check_readiness(test_client: TestClient) -> None:
    response = test_client.get("/common/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] is not None
    assert body["data"]["status"] == 1
    assert body["data"]["dependencies"]["database"]["status"] == 1
    assert body["data"]["dependencies"]["redis"]["status"] == 1


def test_check_health(test_client: TestClient) -> None:
    response = test_client.get("/common/health/check")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == 1
    assert body["data"]["version"]
    assert body["data"]["uptime_seconds"] >= 0


def test_liveness_probe(test_client: TestClient) -> None:
    response = test_client.get("/common/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == 1
