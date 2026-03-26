# GEMINI Project Context: Microservices Performance Lab

## Project Overview

This repository contains a complete, containerized microservices ecosystem designed for educational purposes, specifically for performance analysis and observability. The primary goal is to measure, compare, and optimize different data transfer strategies and architectural patterns in a controlled environment.

The architecture consists of two main Java services, a comprehensive observability stack (Prometheus, Grafana), and a load testing tool (k6).

### Core Components:
*   **`ms-files-managment`**: The main API service (consumer) that exposes endpoints for fetching image data. It's a standard Spring Boot Web (blocking) application.
*   **`ms-files-management-reactive`**: A reactive version of the files service using Spring WebFlux, used for comparison experiments.
*   **`ms-producer-picture`**: A simple provider service that serves static image files of various sizes.
*   **`Prometheus`**: Scrapes and stores time-series metrics from all services.
*   **`Grafana`**: Provides dashboards for visualizing the metrics collected by Prometheus.
*   **`k6` (Local)**: Load testing tool executed directly from the host machine to eliminate Docker networking overhead during tests.
*   **`cAdvisor`**: Collects container-level metrics (CPU, memory, etc.).

### Key Technologies:
*   **Backend**: Java 21, Spring Boot 3.5.6
*   **Build Tool**: Maven
*   **Containerization**: Docker, Docker Compose
*   **Load Testing**: k6
*   **Observability**: Prometheus, Grafana, Micrometer

> **Important Note:** There is a known, consistent typo in the project. The primary consumer service is named `ms-files-managment` instead of the correct `ms-files-management`. This is reflected in service names, directory structures, and configuration files.

## Building and Running

The entire ecosystem is managed via Docker Compose, which is the primary method for running experiments.

### Primary Workflow (Docker Compose)

1.  **Start the Environment:**
    *   This command builds the images and starts all services in the background.
    ```bash
    docker compose up -d --build
    ```

2.  **Run Performance Tests:**
    *   Tests are executed locally using the Python orchestrator (requires `k6` installed on your machine).
    ```bash
    python ./tests/run-k6.py <warmup|load|stress> <blocking|reactive|both|raw|base64|mixed> <label>
    ```
    *   **`<label>`** (optional): appended to filenames to identify the run.

3.  **Stop the Environment:**
    ```bash
    docker compose down
    ```

### Accessing Services
*   **Grafana (Dashboards)**: `http://localhost:3000` (admin/admin)
*   **Prometheus (Metrics UI)**: `http://localhost:9090`
*   **Main API (`ms-files-managment`)**: `http://localhost:8080`
*   **Reactive API (`ms-files-management-reactive`)**: `http://localhost:8083`
*   **Provider Service (`ms-producer-picture`)**: `http://localhost:8081`

### Local Development (Without Docker)

It's also possible to run the Java services locally using Maven.

1.  **Start Provider Service:**
    ```bash
    cd app/providers/ms-producer-picture
    ./mvnw spring-boot:run
    ```

2.  **Start Consumer Service:**
    ```bash
    cd app/consumers/ms-files-managment
    export FILE_SERVICE_BASE_URL=http://localhost:8081
    ./mvnw spring-boot:run
    ```

## Development Conventions

*   **Experiment-Driven:** The project's workflow is centered around running controlled experiments. Any change (e.g., enabling a feature, refactoring code) should be validated by running a baseline test and a test with the change, then comparing the results in Grafana and the k6 output.
*   **Metrics are Key:** All backend services are instrumented with Micrometer to expose detailed metrics (HTTP, JVM, etc.) to Prometheus via the `/actuator/prometheus` endpoint. This is a required convention.
*   **Test Results:** The `tests/run-k6.py` orchestrator automatically handles:
    *   **k6 Summaries**: JSON summaries are saved to the `/results` directory.
    *   **Prometheus Timeseries**: After a test completes, it exports the relevant time-series data from Prometheus into `/results/prometheus-exports`, enabling offline analysis.
*   **Branching Strategy:** For new experiments, it is recommended to use a branch name that describes the experiment, for example: `exp/enable-virtual-threads`.
