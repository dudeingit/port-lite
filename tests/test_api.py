import subprocess
from unittest.mock import MagicMock, patch
import pytest

from api.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "service": "port-lite-api",
    }


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"environment_name": ""},
        {"environment_name": "Invalid_Env_Name"},
        {"environment_name": "-starts-with-hyphen"},
        {"environment_name": "ends-with-hyphen-"},
        {"environment_name": "a" * 64},
        {"environment_name": "preview-1", "owner": "bad owner!"},
    ],
)
def test_provision_environment_invalid_input(client, payload):
    with patch("api.app.subprocess.run") as mock_run:
        if payload is None:
            response = client.post(
                "/api/v1/environments",
                data="not-json",
                content_type="text/plain",
            )
        else:
            response = client.post("/api/v1/environments", json=payload)

    assert response.status_code == 400
    assert "error" in response.get_json()
    mock_run.assert_not_called()


def test_provision_environment_success_creates_workspace(client):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        # Simulate workspace not existing yet on 'select'
        if cmd[:3] == ["terraform", "workspace", "select"]:
            result.returncode = 1
        return result

    with patch("api.app.subprocess.run", side_effect=fake_run) as mock_run:
        response = client.post(
            "/api/v1/environments",
            json={"environment_name": "preview-pr-42", "owner": "rajkamal"},
        )

    assert response.status_code == 201
    assert response.get_json() == {
        "message": "Environment preview-pr-42 successfully provisioned and deployed!",
        "namespace": "preview-pr-42",
        "release": "pr-preview-pr-42",
    }

    executed_cmds = [call.args[0] for call in mock_run.call_args_list]
    assert ["terraform", "init", "-input=false"] in executed_cmds
    assert ["terraform", "workspace", "select", "preview-pr-42"] in executed_cmds
    assert ["terraform", "workspace", "new", "preview-pr-42"] in executed_cmds
    assert any(cmd[:3] == ["terraform", "apply", "-input=false"] for cmd in executed_cmds)
    assert any(cmd[:3] == ["helm", "upgrade", "--install"] for cmd in executed_cmds)


def test_provision_environment_subprocess_failure(client):
    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["terraform", "apply"]:
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                output="",
                stderr="Error: cluster unreachable",
            )
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("api.app.subprocess.run", side_effect=fake_run):
        response = client.post(
            "/api/v1/environments",
            json={"environment_name": "preview-pr-99", "owner": "rajkamal"},
        )

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "Orchestration command failed"
    assert "cluster unreachable" in body["details"]


def test_provision_environment_timeout(client):
    with patch(
        "api.app.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["helm", "upgrade"], timeout=180),
    ):
        response = client.post(
            "/api/v1/environments",
            json={"environment_name": "preview-slow", "owner": "rajkamal"},
        )

    assert response.status_code == 504
    assert response.get_json()["error"] == "Command timed out"


def test_teardown_environment_invalid_name(client):
    with patch("api.app.subprocess.run") as mock_run:
        response = client.delete("/api/v1/environments/Bad_Name!")

    assert response.status_code == 400
    assert "error" in response.get_json()
    mock_run.assert_not_called()


def test_teardown_environment_success(client):
    with patch("api.app.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        response = client.delete("/api/v1/environments/preview-pr-42")

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Environment preview-pr-42 successfully torn down and purged!",
        "namespace": "preview-pr-42",
    }

    executed_cmds = [call.args[0] for call in mock_run.call_args_list]
    assert ["helm", "uninstall", "pr-preview-pr-42", "--namespace", "preview-pr-42"] in executed_cmds
    assert any(cmd[:3] == ["terraform", "destroy", "-input=false"] for cmd in executed_cmds)
    assert ["terraform", "workspace", "select", "default"] in executed_cmds
    assert ["terraform", "workspace", "delete", "-force", "preview-pr-42"] in executed_cmds


def test_teardown_environment_destroy_failure(client):
    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["terraform", "destroy"]:
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                output="",
                stderr="Error: destroy failed",
            )
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("api.app.subprocess.run", side_effect=fake_run):
        response = client.delete("/api/v1/environments/preview-pr-42")

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "Orchestration command failed"
    assert "destroy failed" in body["details"]
