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

## License
This project is licensed under the MIT License.
