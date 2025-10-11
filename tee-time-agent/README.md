# Tee Time Agent

Automation for checking BRS Golf member tee sheet availability exactly 10 days ahead and sending a status report to Telegram. The agent is built on the Google Agent Development Kit (ADK): Playwright captures the JavaScript-heavy tee sheet, an Ollama-hosted model produces a structured summary, and the result is delivered to Telegram. The repo includes Kubernetes manifests so the workflow can be managed through GitOps (Argo CD) inside your cluster.

## Features
- Logs into the BRS member site with Playwright and captures the tee sheet HTML/text once per run.
- Uses Google ADK with a custom Ollama-backed summariser to turn the capture into structured availability data.
- Publishes a concise summary plus detailed tee time list to a Telegram channel/chat.
- Default scheduling logic mirrors the existing n8n flow: only runs when the date that is 10 days ahead is a Friday, Saturday, or Sunday. Use `--force-date` to override when testing.
- Container image and Kubernetes CronJob manifest for GitOps-friendly deployment managed by Argo CD.

## Project layout
```
tee-time-agent/
├── Dockerfile
├── pyproject.toml
├── .env.example
├── src/
│   └── tee_time_agent/
│       ├── adk_agent.py
│       ├── config.py
│       ├── date_window.py
│       ├── main.py
│       ├── models.py
│       ├── ollama_client.py
│       ├── playwright_client.py
│       └── telegram.py
└── k8s/
    ├── argocd-application.yaml
    ├── cronjob.yaml
    └── secret-example.yaml
```

## Local setup
1. **Install dependencies**
   ```bash
   cd tee-time-agent
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install .
   playwright install chromium
   ```
2. **Configure environment**
   ```bash
   cp .env.example .env
   # Populate credentials + tokens. Secrets can also be injected via the environment.
   ```
3. **Run the agent**
   ```bash
   tee-time-agent
   # or target a specific ISO date regardless of the 10-day rule:
   tee-time-agent --force-date 2024-08-17
   ```

### Environment variables
The CLI reads configuration from environment variables (prefixed with `TEE_AGENT_`). The most important settings are:

| Variable | Description |
| --- | --- |
| `TEE_AGENT_BRS_USERNAME` / `TEE_AGENT_BRS_PASSWORD` | Member login credentials. |
| `TEE_AGENT_CLUB_SLUG` | Club identifier in the BRS URL (e.g. `aylesburyvale`). |
| `TEE_AGENT_COURSE_ID` | Course number used in the tee sheet path (default `1`). |
| `TEE_AGENT_TELEGRAM_BOT_TOKEN` / `TEE_AGENT_TELEGRAM_CHAT_ID` | Telegram Bot API credentials. |
| `TEE_AGENT_OLLAMA_BASE_URL` | Base URL for your Ollama instance (`http://ollama.ollama.svc.cluster.local:11434`). |
| `TEE_AGENT_OLLAMA_MODEL` | Ollama model tag to use for summarisation (e.g. `gemma3:12b`). |
| `TEE_AGENT_HEADLESS` | Whether Playwright runs headless (default `true`). |

Secrets can be supplied at runtime via Kubernetes Secrets, GitHub Actions, or other secret managers.

## Docker usage
Build and run the container locally (Chromium is included via the Playwright base image):
```bash
docker build -t tee-time-agent .
docker run --rm --env-file .env tee-time-agent
```

Push the image to your registry (example):
```bash
docker tag tee-time-agent ghcr.io/<org>/tee-time-agent:<tag>
docker push ghcr.io/<org>/tee-time-agent:<tag>
```

Update `k8s/cronjob.yaml` with the pushed image reference before syncing through Argo CD.

## Kubernetes & Argo CD
The `k8s` folder contains manifests to deploy the agent as a CronJob:
- `secret-example.yaml`: Template for the runtime secrets (convert to `ExternalSecret` if needed).
- `cronjob.yaml`: Runs the agent daily at `06:05` UTC, matching the existing n8n cadence.
- `argocd-application.yaml`: Points Argo CD at the `tee-time-agent/k8s` folder for reconciliation.

Workflow:
1. Create `tee-time-agent-secrets` in your cluster (or manage it via External Secrets).
2. Build & push the container image, updating `cronjob.yaml` with the correct image path/tag.
3. Commit changes to the Git repo (`build` repo). Argo CD will detect the update and sync.
4. Monitor execution through Kubernetes jobs or Telegram notifications.

## Suggested GitFlow
To align with the cluster Git server and Argo CD:
1. Work in feature branches under `build/tee-time-agent` (e.g. `feature/tee-agent-playwright`).
2. Merge into `develop` for integration testing (optional staging environment).
3. Promote to `main` once verified. Argo CD `targetRevision` in `argocd-application.yaml` tracks `main`.
4. Tag releases (e.g. `v0.1.0`) and update your image builds to use the tag for reproducibility.

CI/CD idea:
- Use your cluster Git server (or GitHub) to trigger a build pipeline (GitLab CI, GitHub Actions, Argo Workflows).
- Pipeline steps: lint/test, build container, push to registry, create merge request / update `cronjob.yaml` image tag, rely on Argo CD for deployment.

## Integrating with n8n
If you want to keep n8n as the orchestrator:
1. Expose the agent as a simple HTTP service (e.g. wrap `tee_time_agent.main.run` behind FastAPI) or run the CLI via n8n's Execute Command node inside the cluster.
2. The Telegram message is already formatted; alternatively, capture `analysis.model_raw_response` for additional downstream processing.

## Troubleshooting
- **Login loops** – confirm the Playwright selectors still match the BRS login form (inspect in headed mode or update `playwright_client.py`).
- **No tee times parsed** – check the Ollama `model_raw_response` in logs to understand the completion; tweak the prompt or model if the JSON is malformed.
- **Telegram failures** – ensure the bot has access to the chat/channel and that the `chat_id` includes the correct prefix (negative IDs for groups).

## Next steps
- Add DOM-based parsing as a fallback to reduce reliance on the LLM.
- Capture screenshots on failure and push to object storage for debugging.
- Extend the CronJob schedule or run multiple jobs to cover bank holidays/competitions automatically.
