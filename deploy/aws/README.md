# AWS Deployment Guide

This project is structured around a split AWS runtime:

- an app instance running:
  - `dashboard/chat.py` for the user-facing app
  - `src/mcp_server.py` for tool execution
- a routing instance running:
  - `otp` as the transit router
  - `graphhopper` as the walking router

For an interview demo, the cleanest AWS setup is two EC2 instances:

- `1` app EC2 instance for Streamlit + MCP
- `1` routing EC2 instance for OTP + GraphHopper

## Recommended AWS Shape

- app instance:
  - Docker Engine + Compose plugin
  - security group open for `8501` to the browser
  - `8765` for MCP only if you need external access; otherwise keep it internal-only
- routing instance:
  - Docker Engine + Compose plugin
  - security group open for `8080` from the app instance
  - security group open for `8989` from the app instance
  - `8990` GraphHopper admin only if you explicitly need it

If both instances are in the same VPC, prefer private IP communication from the app instance to the routing instance.

## Files Used

- `compose.yaml`
- `Dockerfile`
- `.env`
- `deploy/graphhopper/` for GraphHopper binaries/config
- `otp/` for OTP jar and graph files
- `data/` for events, GTFS extracts, and cached tourism datasets

## EC2 Flow

1. Launch Ubuntu or Amazon Linux with enough RAM for OTP + GraphHopper.
2. Launch a second, lighter app instance for Streamlit + MCP.
3. Install Docker and Docker Compose on both instances.
4. Copy this repository to both instances.
5. Create `.env` from `.env.example` on the app instance and point `OTP_BASE_URL`, `OTP_GRAPHQL_URL`, and `GRAPHHOPPER_URL` at the routing instance.
6. Place your working OTP and GraphHopper files on the routing instance.
7. Start the routing services first, then start the app/MCP services.

```bash
docker compose up --build -d
```

8. Open the app on:

```text
http://<ec2-public-ip>:8501
```

## Notes

- `compose.yaml` is still useful for local development or a single-host fallback.
- In AWS, you can split the same services across two EC2 instances by setting the service URLs in `.env`.
- OTP uses the checked-in jar and prebuilt graph from `otp/`.
- GraphHopper is expected to use your already working jar/config, mounted from `deploy/graphhopper/`.
- This is optimized for demo reliability, not autoscaling.

## Suggested Interview Framing

You can honestly describe this as:

> A split, two-instance AWS deployment for an AI mobility planner, with Streamlit + MCP on the app tier and OTP + GraphHopper on a dedicated routing tier.
