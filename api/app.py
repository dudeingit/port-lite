import subprocess
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "port-lite-api"}), 200

@app.route("/api/v1/environments", methods=["POST"])
def provision_environment():
    data = request.get_json() or {}
    env_name = data.get("environment_name")
    owner = data.get("owner", "developer")

    if not env_name:
        return jsonify({"error": "environment_name is required"}), 400

    try:
        # Step 1: Run Terraform to provision namespace & quotas
        tf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../terraform"))
        
        # For dynamic demo, update root tfvars or execute with vars
        init_cmd = ["terraform", "init"]
        apply_cmd = [
            "terraform", "apply", "-auto-approve",
            f"-var=environment_name={env_name}",
            f"-var=owner={owner}"
        ]
        
        subprocess.run(init_cmd, cwd=tf_dir, check=True, capture_output=True)
        subprocess.run(apply_cmd, cwd=tf_dir, check=True, capture_output=True)

        # Step 2: Deploy Helm release into the new namespace
        chart_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../helm/app-template"))
        helm_cmd = [
            "helm", "upgrade", "--install", f"pr-{env_name}", chart_dir,
            "--namespace", env_name, "--create-namespace"
        ]
        subprocess.run(helm_cmd, check=True, capture_output=True)

        return jsonify({
            "message": f"Environment {env_name} successfully provisioned and deployed!",
            "namespace": env_name,
            "release": f"pr-{env_name}"
        }), 201

    except subprocess.CalledProcessError as e:
        return jsonify({
            "error": "Provisioning failed",
            "details": e.stderr.decode("utf-8") if e.stderr else str(e)
        }), 500

@app.route("/api/v1/environments/<env_name>", methods=["DELETE"])
def teardown_environment(env_name):
    try:
        # Step 1: Uninstall Helm release first
        helm_cmd = ["helm", "uninstall", f"pr-{env_name}", "--namespace", env_name]
        subprocess.run(helm_cmd, capture_output=True) # Ignore error if already gone

        # Step 2: Run Terraform destroy to clean up namespace and quotas
        tf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../terraform"))
        destroy_cmd = [
            "terraform", "destroy", "-auto-approve",
            f"-var=environment_name={env_name}",
            f"-var=owner=developer"
        ]
        subprocess.run(destroy_cmd, cwd=tf_dir, check=True, capture_output=True)

        return jsonify({
            "message": f"Environment {env_name} successfully torn down and purged!",
            "namespace": env_name
        }), 200

    except subprocess.CalledProcessError as e:
        return jsonify({
            "error": "Teardown failed",
            "details": e.stderr.decode("utf-8") if e.stderr else str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
