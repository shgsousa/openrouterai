# OpenRouterAI

OpenRouterAI is a FastAPI-based application designed to manage and query metadata for AI models. It provides the following features:

- **Database Management**: Automatically updates the database daily and ensures freshness during runtime.
- **API Endpoints**: Offers endpoints for health checks, model searches, and database rebuilding.
- **Containerization**: Supports deployment via Docker with multi-architecture builds.

## Features

1. **Daily Database Updates**:
   - Ensures the database is updated daily using a background task.
   - Checks for database freshness during runtime.

2. **API Endpoints**:
   - `/health`: Health check endpoint.
   - `/models`: Search for AI models with advanced filtering options.
   - `/rebuild-database`: Rebuild the database by fetching fresh data from the OpenRouter API.

3. **Containerization**:
   - Dockerfile provided for containerization.
   - Multi-architecture builds supported (linux/amd64, linux/arm64).

## Model Context Protocol (MCP)
This application implements the Model Context Protocol (MCP), which allows Large Language Models (LLMs) to interact with external systems by providing them with access to tools. In this project, MCP is used to expose functionalities like searching for AI models and rebuilding the database as callable tools for LLMs.

The `/mcp` endpoint serves as the entry point for MCP interactions, supporting methods such as:
- `initialize`: To set up an MCP session.
- `tools/list`: To discover available tools.
- `tools/call`: To execute specific tools (e.g., `search_models`, `rebuild_database_tool`).

## Getting Started

### Prerequisites
- Python 3.12 or higher
- Docker (for containerization)
- uv (install with `pip install uv`)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/shgsousa/openrouterai.git
   cd openrouterai
   ```

2. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```

### Docker Deployment
1. Build and push the Docker image:
   ```bash
   ./build_and_push.sh
   ```

2. Alternatively, use PowerShell:
   ```powershell
   .\build_and_push.ps1
   ```

3. Run the Docker container:
   ```bash
   docker run -p 8000:8000 shgsousa/openrouterai:latest
   ```

### Kubernetes Deployment
To deploy the application to a Kubernetes cluster, follow these steps:

1.  **Ensure Nginx Ingress Controller is installed:**
    The provided Ingress configuration assumes you have an Nginx Ingress Controller running in your cluster.

2.  **Apply the deployment and service:**
    Navigate to the `k8s` directory (or wherever you saved the YAML files) and apply the deployment and service:
    ```bash
    kubectl apply -f k8s/kubernetes-deployment.yaml
    kubectl apply -f k8s/kubernetes-service.yaml
    ```

3.  **Configure and apply the Ingress:**
    Open `k8s/kubernetes-ingress.yaml` and change `openrouterai.example.com` to your desired hostname. Then apply the Ingress:
    ```bash
    kubectl apply -f k8s/kubernetes-ingress.yaml
    ```

4.  **Verify the deployment:**
    You can check the status of your deployment, pods, services, and ingress using:
    ```bash
    kubectl get deployments -n mcp-servers
    kubectl get pods -n mcp-servers
    kubectl get services -n mcp-servers
    kubectl get ingress -n mcp-servers
    ```

## License
This project is licensed under the MIT License.
