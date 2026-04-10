# Deployment Guide

This project is deployed as a Docker Compose stack with four main services plus an optional local LLM service:

- `app` for the Streamlit UI
- `mcp` for tool execution
- `otp` for transit routing
- `graphhopper` for walking routes
- `ollama` optionally, when self-hosting the LLM

For a portfolio or interview demo, the recommended production-like setup is a two-instance AWS EC2 deployment:

- one EC2 instance for the `app` and `mcp` services
- one EC2 instance for the `otp` and `graphhopper` services

This keeps the public-facing app lightweight while isolating the heavier routing workloads on a separate machine.

## Supported Deployment Model

Use:

- `compose.yaml`
- `Dockerfile`
- `Dockerfile.otp`
- `Dockerfile.graphhopper`
- `.env`

This keeps the architecture understandable and easy to explain.

For local development, the same services can still be run together on a single machine with Docker Compose.

## Local Docker Quick Start

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Configure either:

- `LLM_PROVIDER=ollama`
- or `LLM_PROVIDER=openai` with a valid `OPENAI_API_KEY`

3. Ensure the required runtime assets are present locally:

- `otp/otp-shaded-2.8.1.jar`
- `otp/graphs/default/graph.obj`
- `otp/graphs/default/ireland-and-northern-ireland-260318.osm.pbf`
- `otp/graphs/default/otp-config.json`
- `deploy/graphhopper/graphhopper-web-10.2.jar`
- `deploy/graphhopper/config-example.yml`
- `deploy/graphhopper/foot-custom.json`

4. Start the stack:

```bash
docker compose up --build -d
```

5. Open:

```text
http://localhost:8501
```

## AWS EC2 Deployment

Recommended for demo reliability:

- `1` EC2 instance
- Ubuntu 22.04 LTS
- `100 GB` gp3 storage
- enough RAM for OTP + GraphHopper + app stack

If using Ollama on the same machine, prefer a larger instance. If using OpenAI API, the infrastructure is lighter.

See:

- `deploy/aws/README.md`

## Hybrid GitHub + EC2 Asset Model

This repository is intentionally shaped for a hybrid deployment model:

- GitHub stores the code, Dockerfiles, configs, and docs
- EC2 receives large runtime artifacts separately before `docker compose build`

That keeps the repo reviewable and avoids pushing large generated or runtime files to GitHub.

Typical runtime files copied manually to EC2:

- `otp/otp-shaded-2.8.1.jar`
- `otp/graphs/default/graph.obj`
- `otp/graphs/default/ireland-and-northern-ireland-260318.osm.pbf`
- `otp/graphs/default/otp-config.json`
- `deploy/graphhopper/graphhopper-web-10.2.jar`
- `deploy/graphhopper/config-example.yml`
- `deploy/graphhopper/foot-custom.json`

These files must exist on EC2 before:

```bash
docker compose build
```

because the Dockerfiles copy them into the images.

## Service Summary

### App

- Streamlit UI
- entrypoint: `dashboard/chat.py`

### MCP

- tool server for the agent runtime
- entrypoint: `src/mcp_server.py`

### OTP

- Java transit router
- uses the prebuilt graph in `otp/graphs/default`

### GraphHopper

- Java walking router
- configured through `deploy/graphhopper/`

### Ollama

- optional self-hosted LLM runtime
- useful for fully self-contained demos

## Notes

- This deployment path is intentionally simpler than ECS or Kubernetes for interview use.
- It is still strong enough to demonstrate service orchestration, cloud deployment, and infrastructure ownership.
