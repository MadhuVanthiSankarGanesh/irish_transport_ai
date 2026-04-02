# AWS Deployment Guide

This project is now structured around a single supported runtime:

- `dashboard/chat.py` for the user-facing app
- `src/mcp_server.py` for tool execution
- `otp` as the transit router
- `graphhopper` as the walking router

For an interview demo, the cleanest AWS setup is a single EC2 instance running Docker Compose.

## Recommended AWS Shape

- 1 EC2 instance
- Docker Engine + Compose plugin
- Security group open for:
  - `8501` Streamlit app
  - `8080` OTP
  - `8989` GraphHopper
  - `8990` GraphHopper admin, optional
  - `8765` MCP, optional internal-only

## Files Used

- `compose.yaml`
- `Dockerfile`
- `.env`
- `deploy/graphhopper/` for GraphHopper binaries/config
- `otp/` for OTP jar and graph files
- `data/` for events, GTFS extracts, and cached tourism datasets

## EC2 Flow

1. Launch Ubuntu or Amazon Linux with enough RAM for OTP + GraphHopper.
2. Install Docker and Docker Compose.
3. Copy this repository to the instance.
4. Create `.env` from `.env.example`.
5. Place your working GraphHopper files into `deploy/graphhopper/`.
6. Start the stack:

```bash
docker compose up --build -d
```

7. Open the app on:

```text
http://<ec2-public-ip>:8501
```

## Notes

- OTP uses the checked-in jar and prebuilt graph from `otp/`.
- GraphHopper is expected to use your already working jar/config, mounted from `deploy/graphhopper/`.
- This is optimized for demo reliability, not autoscaling.

## Suggested Interview Framing

You can honestly describe this as:

> A containerized multi-service AI mobility planner deployed on AWS EC2, with Streamlit for the UX, LangGraph + MCP for orchestration, OTP for transit routing, and GraphHopper for pedestrian routing.
