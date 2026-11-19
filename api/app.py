import logging
import os
import re
import subprocess
import sys
import time
from flask import Flask, jsonify, request
from pythonjsonlogger.json import JsonFormatter

app = Flask(__name__)

ENV_NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
OWNER_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")
SUBPROCESS_TIMEOUT_SECONDS = 180


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("port-lite-api")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = JsonFormatter(
            ["asctime", "levelname", "name", "message"],
            static_fields={"service": "port-lite-api"},
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()


def validate_inputs(env_name: object, owner: object) -> tuple[bool, str | None]:
    if not isinstance(env_name, str) or not ENV_NAME_PATTERN.match(env_name):
        return (
            False,
            "environment_name must be 1-63 lowercase alphanumeric characters or hyphens, "
            "starting and ending with an alphanumeric character",
        )

    if not isinstance(owner, str) or not OWNER_PATTERN.match(owner):
        return (
            False,
            "owner must be 1-64 characters containing only letters, numbers, dots, underscores, or hyphens",
        )

    return True, None


def run_cmd(
    cmd: list[str],
    cwd: str | None = None,
    timeout: int = SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def get_paths() -> tuple[str, str]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tf_dir = os.path.abspath(os.path.join(base_dir, "../terraform"))
    chart_dir = os.path.abspath(os.path.join(base_dir, "../helm/app-template"))
    return tf_dir, chart_dir


def select_or_create_workspace(tf_dir: str, env_name: str) -> None:
    # 'terraform workspace new' fails if the workspace already exists, so select first
    select_res = subprocess.run(
        ["terraform", "workspace", "select", env_name],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if select_res.returncode != 0:
        run_cmd(["terraform", "workspace", "new", env_name], cwd=tf_dir, timeout=60)


def cleanup_workspace(tf_dir: str, env_name: str) -> None:
    if env_name == "default":
        return
    subprocess.run(
        ["terraform", "workspace", "select", "default"],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    subprocess.run(
        ["terraform", "workspace", "delete", "-force", env_name],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )


def format_subprocess_error(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, subprocess.TimeoutExpired):
        return 504, "Command timed out", f"Timed out after {exc.timeout}s: {' '.join(exc.cmd)}"
    if isinstance(exc, FileNotFoundError):
        missing = exc.filename or "required CLI binary"
        return 500, "Missing CLI dependency", f"Executable not found: {missing}"
    if isinstance(exc, subprocess.CalledProcessError):
        details = (exc.stderr or exc.stdout or str(exc)).strip()
        return 500, "Orchestration command failed", details
    return 500, "Unexpected error", str(exc)


@app.route("/health", methods=["GET"])
def health_check():
    logger.info(
        "Health check requested",
        extra={"action": "health_check", "outcome": "ok"},
    )
    return jsonify({"status": "healthy", "service": "port-lite-api"}), 200


@app.route("/api/v1/environments", methods=["POST"])
def provision_environment():
    start_time = time.monotonic()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        logger.warning(
            "Provisioning rejected: invalid JSON payload",
            extra={"action": "provision", "outcome": "bad_request"},
        )
        return jsonify({"error": "Request body must be a JSON object"}), 400

    env_name = data.get("environment_name")
    owner = data.get("owner", "developer")

    is_valid, validation_error = validate_inputs(env_name, owner)
    if not is_valid:
        logger.warning(
            "Provisioning rejected: input validation failed",
            extra={
                "action": "provision",
                "outcome": "bad_request",
                "environment_name": str(env_name),
                "owner": str(owner),
                "reason": validation_error,
            },
        )
        return jsonify({"error": validation_error}), 400

    release_name = f"pr-{env_name}"
    tf_dir, chart_dir = get_paths()

    logger.info(
        "Starting environment provisioning",
        extra={
            "action": "provision",
            "outcome": "started",
            "environment_name": env_name,
            "owner": owner,
            "release": release_name,
        },
    )

    try:
        run_cmd(["terraform", "init", "-input=false"], cwd=tf_dir)
        select_or_create_workspace(tf_dir, env_name)
        run_cmd(
            [
                "terraform",
                "apply",
                "-input=false",
                "-auto-approve",
                f"-var=environment_name={env_name}",
                f"-var=owner={owner}",
            ],
            cwd=tf_dir,
        )
        run_cmd(
            [
                "helm",
                "upgrade",
                "--install",
                release_name,
                chart_dir,
                "--namespace",
                env_name,
                "--create-namespace",
                "--wait",
                "--timeout",
                "2m",
            ]
        )

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info(
            "Environment provisioned successfully",
            extra={
                "action": "provision",
                "outcome": "success",
                "environment_name": env_name,
                "owner": owner,
                "release": release_name,
                "duration_ms": duration_ms,
            },
        )
        return jsonify(
            {
                "message": f"Environment {env_name} successfully provisioned and deployed!",
                "namespace": env_name,
                "release": release_name,
            }
        ), 201

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        status_code, error_title, details = format_subprocess_error(exc)
        logger.error(
            "Environment provisioning failed",
            extra={
                "action": "provision",
                "outcome": "error",
                "environment_name": env_name,
                "owner": owner,
                "release": release_name,
                "duration_ms": duration_ms,
                "error": details,
            },
        )
        return jsonify({"error": error_title, "details": details}), status_code


@app.route("/api/v1/environments/<env_name>", methods=["DELETE"])
def teardown_environment(env_name):
    start_time = time.monotonic()
    is_valid, validation_error = validate_inputs(env_name, "developer")
    if not is_valid:
        logger.warning(
            "Teardown rejected: invalid environment_name",
            extra={
                "action": "teardown",
                "outcome": "bad_request",
                "environment_name": str(env_name),
                "reason": validation_error,
            },
        )
        return jsonify({"error": validation_error}), 400

    release_name = f"pr-{env_name}"
    tf_dir, _ = get_paths()

    logger.info(
        "Starting environment teardown",
        extra={
            "action": "teardown",
            "outcome": "started",
            "environment_name": env_name,
            "release": release_name,
        },
    )

    try:
        # Uninstall Helm release if present; ignore if already absent
        subprocess.run(
            ["helm", "uninstall", release_name, "--namespace", env_name],
            capture_output=True,
            text=True,
            timeout=120,
        )

        run_cmd(["terraform", "init", "-input=false"], cwd=tf_dir)
        select_or_create_workspace(tf_dir, env_name)
        run_cmd(
            [
                "terraform",
                "destroy",
                "-input=false",
                "-auto-approve",
                f"-var=environment_name={env_name}",
                "-var=owner=developer",
            ],
            cwd=tf_dir,
        )
        cleanup_workspace(tf_dir, env_name)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info(
            "Environment torn down successfully",
            extra={
                "action": "teardown",
                "outcome": "success",
                "environment_name": env_name,
                "release": release_name,
                "duration_ms": duration_ms,
            },
        )
        return jsonify(
            {
                "message": f"Environment {env_name} successfully torn down and purged!",
                "namespace": env_name,
            }
        ), 200

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        status_code, error_title, details = format_subprocess_error(exc)
        logger.error(
            "Environment teardown failed",
            extra={
                "action": "teardown",
                "outcome": "error",
                "environment_name": env_name,
                "release": release_name,
                "duration_ms": duration_ms,
                "error": details,
            },
        )
        return jsonify({"error": error_title, "details": details}), status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
