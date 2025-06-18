# Net Monitoring

A simple network monitoring tool. This project uses Python to perform network checks and can be run using Docker. Monitoring dashboards can be set up using the provided Grafana and Prometheus configurations.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Docker
- Docker Compose (if using the `docker-compose` setup)
- Python (if running locally without Docker)

### Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/yufeikang/netmon.git
    cd netmon
    ```

2. **Build and run with Docker (recommended for isolated environment):**

    ```bash
    # Build the Docker image
    docker build -t netmon .

    # Run the Docker container
    docker run netmon
    ```

3. **Alternatively, using Docker Compose (for multi-container setup including Grafana/Prometheus):**

    ```bash
    cd docker-compose
    docker-compose up -d
    ```

    cd docker-compose
    docker-compose up -d

    ```

    - Prometheus will be available at `http://localhost:9090`
    - Grafana will be available at `http://localhost:3000` (login with admin/admin, then change password. Datasource and dashboard should be auto-provisioned).

4. **To run locally without Docker (ensure Python and dependencies are installed):**

    ```bash
    # Create and activate a virtual environment (recommended)
    python -m venv venv
    source venv/bin/activate # On Windows use `venv\Scripts\activate`

    # Install dependencies
    pip install -r requirements.txt

    # Run the application (assuming net_monitor.py is the main script)
    python net_monitor.py
    ```

## Usage

Describe how to use your project. For example:

- If it's a script: `uv run python net_monitor.py --target example.com`
- If it's a service: "Access the service at `http://localhost:YOUR_PORT`"

## Docker

This project includes a `Dockerfile` to build a containerized version of the application.

- **Build the image:**

    ```bash
    docker build -t netmon .
    ```

- **Run the container:**

    ```bash
    docker run netmon
    ```

The `docker-compose/` directory contains a `docker-compose.yaml` file to orchestrate the main application along with Prometheus for metrics collection and Grafana for visualization.

## GitHub Actions

This repository is configured with a GitHub Actions workflow (`.github/workflows/deploy-docker.yml`) that automatically:

1. Builds the Docker image from the `Dockerfile`.
2. Pushes the image to GitHub Packages (ghcr.io) on every push to the `main` branch.

The image will be tagged as `ghcr.io/yufeikang/netmon:main`.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details (if you choose to add one).
