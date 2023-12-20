import os
import threading
import time
import schedule
from kubernetes import client, config
from flask import Flask, jsonify, request

app = Flask(__name__)

# Function to scale all deployments in a namespace to zero replicas
def scale_all_deployments(namespace, scale):
    apps_v1 = client.AppsV1Api()
    deployments = apps_v1.list_namespaced_deployment(namespace=namespace)
    for deploy in deployments.items:
        body = {'spec': {'replicas': scale}}
        apps_v1.patch_namespaced_deployment_scale(deploy.metadata.name, namespace, body)

# Cron job function
def cron_job():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Catch-all route to scale deployments based on 'X-Namespace' header
@app.route('/<path:any_path>', methods=['GET'])
def scale_deployments(any_path):
    namespace = request.headers.get('X-Namespace')
    if not namespace:
        return jsonify({"error": "Missing 'X-Namespace' header"}), 400

    try:
        scale_all_deployments(namespace, 1)
        return jsonify({"message": f"All deployments in namespace '{namespace}' scaled to zero."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Load Kubernetes config
    config.load_kube_config()

    # Schedule the cron job
    cron_minutes = int(os.getenv('CRON_MINUTES', '60'))
    schedule.every(cron_minutes).minutes.do(lambda: scale_all_deployments(os.getenv('CRON_NAMESPACE', 0)))  # Replace 'default' with your namespace

    # Start the cron job in a separate thread
    cron_thread = threading.Thread(target=cron_job)
    cron_thread.daemon = True  # Daemon threads are shut down immediately when the program exits
    cron_thread.start()

    # Run the Flask API server
    app.run(host='0.0.0.0', port=8080, debug=True)
