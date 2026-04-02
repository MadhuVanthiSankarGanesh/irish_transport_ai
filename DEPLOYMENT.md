# Deployment Guide

This project is now organized around a single supported deployment target:

- `dashboard/chat.py`
- `src/mcp_server.py`
- OTP
- GraphHopper

The recommended deployment for portfolio and interview demos is a single AWS EC2 host running Docker Compose.

## Supported Deployment Model

Use:

- `Dockerfile`
- `compose.yaml`
- `.env`
- `deploy/aws/README.md`

This keeps the full stack in the cloud while avoiding unnecessary orchestration complexity.

## Services

### 1. App

- Containerized Streamlit app
- Runs `dashboard/chat.py`

### 2. MCP

- Containerized tool server
- Runs `src/mcp_server.py`

### 3. OTP

- Java service using the checked-in OTP jar
- Loads the prebuilt graph from `otp/graphs/default`

### 4. GraphHopper

- Java service using your validated GraphHopper runtime files
- Mounted from `deploy/graphhopper/`

## Quick Start

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Fill in:

- `OPENAI_API_KEY`
- any memory overrides if needed

3. Put your working GraphHopper files into `deploy/graphhopper/`:

- `graphhopper-web-10.2.jar`
- `config-example.yml`
- `foot.json` if your config needs it

4. Start the stack:

```bash
docker compose up --build -d
```

5. Open:

```text
http://localhost:8501
```

## AWS EC2 Recommendation

For this project, EC2 is the cleanest option because OTP and GraphHopper are long-running Java services and the demo needs predictable connectivity between containers.

Recommended demo setup:

- one EC2 instance
- Docker Engine
- Docker Compose
- security group opening `8501`

Internal container-to-container traffic can stay private.

## Data Layout

- `data/` is mounted read-only into the Python services
- `otp/` is mounted into the OTP container
- `deploy/graphhopper/` is mounted into the GraphHopper container

## Notes

- This layout is optimized for clarity and demo reliability.
- It is intentionally simpler than Kubernetes or ECS for interview use.
- If you later want ECS, the service split in `compose.yaml` maps cleanly onto ECS task definitions.
