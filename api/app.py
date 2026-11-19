import logging
import os
import subprocess
import sys
import time
from flask import Flask, jsonify, request
from pythonjsonlogger.json import JsonFormatter

app = Flask(__name__)


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


@app.route("/health", methods=["GET"])
def health_check():
    logger.info("Health check requested", extra={"action": "health_check", "outcome": "ok"})
    return jsonify({"status": "healthy", "service": "port-lite-api"}), 200


@app.route("/api/v1/environments", methods=["POST"])
def provision_environment():
    start_time = time.monotonic()
    data = request.get_json(silent=True) or {}
    env_name = data.get("environment_name")
    owner = data.get("owner", "developer")

    if not env_name:
        logger.warning(
            "Provisioning rejected: missing environment_name",
            extra={"action": "provision", "outcome": "bad_request", "owner": owner},
        )
        return jsonify({"error": "environment_name is required"}), 400

    logger.info(
        "Starting environment provisioning",
        extra={"action": "provision", "outcome": "started", "environment_name": env_name, "owner": owner},
    )

    try:
        tf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../terraform"))
        init_cmd = ["terraform", "init"]
        apply_cmd = [
            "terraform",
            "apply",
            "-auto-approve",
            f"-var=environment_name={env_name}",
            f"-var=owner={owner}",
        ]

        subprocess.run(init_cmd, cwd=tf_dir, check=True, capture_output=True)
        subprocess.run(apply_cmd, cwd=tf_dir, check=True, capture_output=True)

        chart_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../helm/app-template"))
        helm_cmd = [
            "helm",
            "upgrade",
            "--install",
            f"pr-{env_name}",
            chart_dir,
            "--namespace",
            env_name,
            "--create-namespace",
        ]
        subprocess.run(helm_cmd, check=True, capture_output=True)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info(
            "Environment provisioned successfully",
            extra={
                "action": "provision",
                "outcome": "success",
                "environment_name": env_name,
                "owner": owner,
                "release": f"pr-{env_name}",
                "duration_ms": duration_ms,
            },
        )

        return jsonify(
            {
                "message": f"Environment {env_name} successfully provisioned and deployed!",
                "namespace": env_name,
                "release": f"pr-{env_name}",
            }
        ), 201

    except subprocess.CalledProcessError as e:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        stderr_output = e.stderr.decode("utf-8") if e.stderr else str(e)
        logger.error(
            "Environment provisioning failed",
            extra={
                "action": "provision",
                "outcome": "error",
                "environment_name": env_name,
                "owner": owner,
                "duration_ms": duration_ms,
                "error": stderr_output,
            },
        )
        return jsonify({"error": "Provisioning failed", "details": stderr_output}), 500


@app.route("/api/v1/environments/<env_name>", methods=["DELETE"])
def teardown_environment(env_name):
    start_time = time.monotonic()
    logger.info(
        "Starting environment teardown",
        extra={"action": "teardown", "outcome": "started", "environment_name": env_name},
    )

    try:
        helm_cmd = ["helm", "uninstall", f"pr-{env_name}", "--namespace", env_name]
        subprocess.run(helm_cmd, capture_output=True)

        tf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../terraform"))
        destroy_cmd = [
            "terraform",
            "destroy",
            "-auto-approve",
            f"-var=environment_name={env_name}",
            "-var=owner=developer",
        ]
        subprocess.run(destroy_cmd, cwd=tf_dir, check=True, capture_output=True)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info(
            "Environment torn down successfully",
            extra={
                "action": "teardown",
                "outcome": "success",
                "environment_name": env_name,
                "duration_ms": duration_ms,
            },
        )

        return jsonify(
            {
                "message": f"Environment {env_name} successfully torn down and purged!",
                "namespace": env_name,
            }
        ), 200

    except subprocess.CalledProcessError as e:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        stderr_output = e.stderr.decode("utf-8") if e.stderr else str(e)
        logger.error(
            "Environment teardown failed",
            extra={
                "action": "teardown",
                "outcome": "error",
                "environment_name": env_name,
                "duration_ms": duration_ms,
                "error": stderr_output,
            },
        )
        return jsonify({"error": "Teardown failed", "details": stderr_output}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
