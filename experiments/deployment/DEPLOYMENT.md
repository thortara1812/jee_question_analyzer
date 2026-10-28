# Deploy the JEE app to Render and Streamlit Community Cloud

## Shared repository

- Repository: https://github.com/thortara1812/jee_question_analyzer
- Deployment branch: `main`
- Streamlit frontend entry point: `app.py`
- Render backend entry point: `api_server.py`
- Python: 3.12 (Render pins 3.12.14)
- Dependency source: `pyproject.toml` and `uv.lock`; no extra requirements file

The deployment is now split: Render hosts the authenticated HTTP backend;
Streamlit Community Cloud hosts the student interface and calls Render from its
server. Groq/Tavily credentials are kept on Render. Streamlit only needs the
backend URL and a matching shared API token.

## Existing Render service: migrate from Streamlit to the API

The original service at https://jee-question-analyzer.onrender.com served the
entire Streamlit app. Merely copying that URL into a frontend does not create an
API. After the latest code is deployed, change the existing service settings:

| Field | Value |
|---|---|
| Build command | `uv sync --locked --no-dev` |
| Start command | `.venv/bin/python api_server.py` |
| Health check path | `/health` |
| Python version | `3.12.14` |

Add `JEE_API_TOKEN` in Render's Environment settings. Choose a long random secret;
this must be the same value used in Streamlit Secrets. It is separate from your
Groq API key. Keep `GROQ_API_KEY` and optional `TAVILY_API_KEY` on Render. Leave
`JEE_API_URL` unset on Render. Save the changes and redeploy.

Verify `/health` returns JSON with `service: agentic-jee-api`. `/openapi.json`
must return JSON and `/docs` must show the backend API documentation. A Streamlit
HTML page at these paths means the old start command is still running. Job
submission fails closed until the shared token has been configured.

## Render: Blueprint route

1. Sign in to Render.
2. Open https://render.com/deploy?repo=https://github.com/thortara1812/jee_question_analyzer
3. If prompted, connect GitHub and grant access to this repository.
4. Confirm branch `main` and review the service described by `render.yaml`.
5. Supply `GROQ_API_KEY` and your private `JEE_API_TOKEN` in Render's secret fields,
   never in GitHub. Keep the same API token for Streamlit in the next section.
6. Keep the **Free** service plan for this initial demo. Do not select a paid plan
   unless you deliberately approve the billing change.
7. Create/deploy the Blueprint and watch the build logs until the service is Live.
8. Open the generated `onrender.com/health` URL and verify the JSON API response.
9. Optional: add `TAVILY_API_KEY` under the service's Environment settings for
   evidence retrieval, then redeploy if required.

The Blueprint sets these values automatically:

| Setting | Value |
|---|---|
| Runtime | Python |
| Build command | `uv sync --locked --no-dev` |
| Start command | `.venv/bin/python api_server.py` |
| Health check | `/health` |
| Python version | `3.12.14` |
| uv version | `0.12.16` |
| History mode | `session` |

If creating a Web Service manually instead of a Blueprint, copy these fields
and the non-secret environment variables from `render.yaml`. Add the API key
using Render's Environment page. The service root is the repository root.
Free hosts have resource and idle-start limitations; a cold start is different
from a workflow failure. Review logs before changing plans.

## Streamlit Community Cloud

1. Sign in at https://share.streamlit.io/ and select **Create app**.
2. Choose **Yup, I have an app** if that question appears.
3. Set repository to `thortara1812/jee_question_analyzer`.
4. Set branch to `main` and main file path to `app.py`.
5. Open **Advanced settings**, select Python **3.12**.
6. Copy `.streamlit/secrets.toml.example` into the **Secrets** field. Replace the
   backend-token placeholder there with the exact same `JEE_API_TOKEN` set on
   Render. The URL is already set to https://jee-question-analyzer.onrender.com.
   Do not put Groq or Tavily keys in the frontend's Secrets for this setup.
7. Keep `JEE_HISTORY_MODE = "session"`. Save the settings and click **Deploy**.
8. Wait for the app to build. Open its generated `streamlit.app` URL.
9. Review the app logs if dependency installation or startup fails.

The secrets field uses TOML: keys and values need the format
`JEE_API_TOKEN = "your-shared-token"`, not dotenv's unquoted `KEY=value` format.
The app reads Streamlit secrets before constructing agents, so root-level
settings are available as environment variables. `.env` is only for local use.

## Verification after each deployment

1. Confirm Render's `/health` returns API JSON, and the Streamlit frontend shows
   the title and both workflow modes.
2. Submit an empty input; expect a validation message without an API request.
3. Load the Physics example and submit it once. The expected answer is 400 J;
   inspect the actual verification status and calculation records.
4. Select fact checking. Without a Tavily key, expect an explicit inconclusive
   result. With retrieval configured, inspect the actual source links.
5. Save a request in session history. In a separate private browser session,
   confirm that the first visitor's question is not visible.

The live question consumes provider quota. A 429 is a provider limit, not proof
that hosting is broken. Separate deployments or API keys in the same Groq
organization do not establish separate organization-level quotas.

The API also returns 429 when its bounded queue is full. The API runs one job at
a time with room for three active/queued jobs total. Completed records expire
after 30 minutes; a restart clears all in-memory jobs. Run one backend process
and instance. The frontend waits up to 10 minutes using short polling requests.
It does not retry uncertain submissions automatically. HTTP requests originate
from the Streamlit server, so browser CORS configuration is not required.

## Local deployment validation

```powershell
.\.venv-validation\Scripts\python.exe -m unittest discover -s experiments/tests -v
docker build -f experiments/deployment/linux-test.Dockerfile -t jee-deploy-check .
docker run --rm jee-deploy-check
```

The clean Linux image deliberately receives neither `.env` nor any real cloud
secrets. It installs locked dependencies and runs offline tests. It is a
verification image, not the Render runtime configuration.

## References

- Render Blueprints: https://render.com/docs/blueprint-spec
- Render Python versions: https://render.com/docs/python-version
- Streamlit deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Streamlit secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- Streamlit dependency files: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
