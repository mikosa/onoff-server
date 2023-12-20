import os
import threading
import time
import schedule
from kubernetes import client, config
from flask import  Flask, jsonify, request, render_template
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

#load kubeconfig
def load_kubernetes_config():
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
        
# Function to scale all deployments in a namespace 
def scale_all_deployments(namespace, scale):
    apps_v1 = client.AppsV1Api()
    try:
        deployments = apps_v1.list_namespaced_deployment(namespace=namespace)
        for deploy in deployments.items:
            if deploy.metadata.name not in ['default-http-backend', 'nginx-ingress-controller']:
                body = {'spec': {'replicas': scale}}
                apps_v1.patch_namespaced_deployment_scale(deploy.metadata.name, namespace, body)
                logging.info(f"Deployment '{deploy.metadata.name}' in namespace '{namespace}' scaled to '{scale}'.")
    except Exception as e:
        logging.error(f"Error scaling deployments in namespace '{namespace}': {e}")
        
# Cron job function
def cron_job():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Catch-all route to scale deployments based on 'X-Namespace' header
@app.route('/', defaults={'any_path': ''})
@app.route('/<path:any_path>', methods=['GET'])
def scale_deployments(any_path):
    redirect_host = request.headers.get('Host', 'default-hostname.com')  # Fallback to a default hostname
    namespace = request.headers.get('X-Namespace')
    if not namespace:
        logging.warning("Missing 'X-Namespace' header in request")
        return jsonify({"error": "Missing 'X-Namespace' header"}), 400

    try:
        scale_all_deployments(namespace, 1)
        print(f"Redirecting to: {redirect_host}")  # Debugging line
        return render_template('response.html', redirect_url=redirect_host), 200
    except Exception as e:
        logging.error(f"Error scaling or rendering '{namespace}': {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Load Kubernetes config
    load_kubernetes_config()
    # Schedule the cron job
    cron_minutes = int(os.getenv('CRON_MINUTES', '2'))
    schedule.every(cron_minutes).minutes.do(lambda: scale_all_deployments(os.getenv('POD_NAMESPACE', 0),0))  # Replace 'default' with your namespace

    # Start the cron job in a separate thread
    cron_thread = threading.Thread(target=cron_job)
    cron_thread.daemon = True  # Daemon threads are shut down immediately when the program exits
    cron_thread.start()

    # Run the Flask API server
    app.run(host='0.0.0.0', port=8080, debug=True)
