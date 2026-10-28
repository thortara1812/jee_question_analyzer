"""Render entrypoint: a single HTTP API process, with one bounded job worker."""
import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run("agentic_jee_system.api:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")),
                workers=1, access_log=False, log_level="warning")
