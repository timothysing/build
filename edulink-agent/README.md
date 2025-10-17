# Edulink Agent

Automation service that signs in to [Edulink One](https://www.edulinkone.com/), captures the latest homework, behaviour, and mailbox information, and returns a concise daily summary. The service is designed to run inside Kubernetes and be orchestrated by n8n, but it can also be executed locally via the included CLI.

## Features

- Logs in to Edulink using Playwright (Chromium) to handle the JavaScript-heavy interface.
- Collects:
  - Outstanding homework items (submission status “Not Submitted”).
  - Current achievement points and behaviour entries added yesterday.
  - New mailbox messages received yesterday.
- Exposes a FastAPI endpoint (`POST /report`) that returns structured JSON and a ready-to-send text summary.
- Conversational interface (CLI `--ask` flag or `POST /chat`).
- CLI entry point (`edulink-agent`) for local testing or ad-hoc execution.

## Local development

1. **Install dependencies**

   ```bash
   cd build/edulink-agent
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -e .
   playwright install chromium
   ```

2. **Set environment variables**

   Copy `.env.example` to `.env` and populate the credentials (school code optional, username, and password are mandatory).

3. **Run the CLI**

   ```bash
   edulink-agent
   ```

   The command prints the generated summary and exits with a non-zero code if the automation fails. Pass `--ask "question"` to request conversational answers instead of the daily digest.

4. **Run the API locally**

   ```bash
   uvicorn edulink_agent.api:app --host 0.0.0.0 --port 8000
   ```

   - `POST http://localhost:8000/report` returns the structured report and summary text.
   - `POST http://localhost:8000/chat` accepts a JSON body such as `{"question": "Any outstanding homework?"}` and returns a conversational reply along with the latest report.

## Docker image

The supplied `Dockerfile` builds on the official Playwright base image and installs the project in production mode:

```bash
docker build -t edulink-agent:latest .
docker run --rm \
  --env-file .env \
  -p 8000:8000 \
  edulink-agent:latest
```

## Kubernetes deployment

`k8s/` contains manifests for:

- A `Secret` template (`secret-example.yaml`) for Edulink credentials and runtime options.
- A `Deployment` exposing the FastAPI service inside the cluster.
- A `CronJob` that can run the CLI directly if desired (optional).
- An Argo CD `Application` for GitOps-friendly rollouts.

See the comments inside the manifests for configuration specifics.

## n8n integration

Import `n8n/edulink-monitor.json` into n8n. The workflow:

1. Triggers daily at 09:00.
2. Calls the Kubernetes service (`http://edulink-agent.<namespace>.svc.cluster.local/report`).
3. Sends the textual summary to Telegram and email.

Update the HTTP node URL and the credential nodes/variables to match your cluster and messaging setup.

For conversational access, import `n8n/edulink-chat.json`. It listens for incoming Telegram messages, forwards the text to `/chat`, and replies with the generated answer. Configure the Telegram node credentials and ensure the bot token matches the conversational channel you intend to use.

## Environment variables

| Variable | Description |
| --- | --- |
| `EDULINK_SCHOOL_CODE` | Optional school/institution code required by your Edulink login flow. |
| `EDULINK_USERNAME` | Username used to sign in. |
| `EDULINK_PASSWORD` | Password used to sign in. |
| `EDULINK_BASE_URL` | Base URL for Edulink (defaults to `https://www.edulinkone.com`). |
| `EDULINK_HEADLESS` | `"true"`/`"false"` toggle for Playwright headless mode (default `true`). |
| `EDULINK_TIMEOUT_SECONDS` | Page interaction timeout (default `30`). |
| `EDULINK_TIMEZONE` | Timezone identifier for “yesterday” calculations (default `Europe/London`). |
| `EDULINK_CHILD_NAME` | Optional child name to include in the summary header. |

Configure Telegram and email delivery inside n8n; no additional variables are required for the service itself.

## Testing

* Unit tests are not included but the modular structure makes it easy to mock Playwright interactions.*

Manual sanity checks:

1. Run the CLI locally (`edulink-agent`) and verify the textual summary output.
2. Start the API (`uvicorn edulink_agent.api:app`) and `curl -X POST http://localhost:8000/report`.
3. Import the n8n workflow and execute it manually to confirm Telegram/email delivery.

## Troubleshooting

- **Login failures**: Inspect container logs; the automation surfaces the last DOM snapshot path in the error message. Ensure school code and credentials are correct.
- **Selectors out of date**: The scraper relies on table headers and text fragments. If Edulink’s UI changes, update the heuristics in `scraper.py`.
- **Playwright missing dependencies**: The Docker image already runs `playwright install --with-deps chromium`; if you run locally, execute `playwright install chromium`.

## License

MIT
