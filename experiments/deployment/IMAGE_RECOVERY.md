# Image extraction recovery update

The frontend previously parsed every transcription HTTP 502 response as JSON. A gateway can return an empty body or an HTML error page instead; this caused the raw message `Expecting value: line 1 column 1 (char 0)` to reach the student.

The client now checks response shape before reading error fields and maps malformed responses to safe recovery messages. Provider responses and successful API responses must also contain the expected object/text shapes. Extraction failures preserve the existing question field so a student can retry or enter text manually. This fixes the parser failure; it does not eliminate Render gateway failures, provider outages or quotas.

## Activate the change

1. Deploy the latest main commit on the Render backend and wait for Live.
2. Reboot the Streamlit Community Cloud app, or deploy the latest commit on the Render frontend service.
3. Confirm `App build: image-recovery-v3` appears on the frontend. If it does not, the frontend is still running older code.
4. Upload a clear image and click Extract question from image. Review the question, then Run / retry.
5. If extraction reports temporary unavailability, check Render logs and memory/service status. Retry only after the backend is available. Do not regenerate keys for a gateway error. The student can type the same question while image extraction is unavailable.

The current natural-language solving flow and equation-format fixes remain active. It still uses an analyzer, solver and independent reviewer without requiring JSON model output.

Validation: 74 automated tests passed locally, including empty/HTML 502 responses, invalid JSON and invalid response shapes. No claim is made that these tests establish hosted availability or broad JEE accuracy.

## Run the complete code locally

Extract the ZIP into a new folder. Install Python 3.12 and uv. In the project folder run `uv sync --locked --no-dev`. Copy `.env.example` to `.env`, set your own GROQ_API_KEY, and leave JEE_API_URL blank for local operation. Run `uv run streamlit run app.py`. Never share the real .env file. To run tests: `uv run python -m unittest discover -s experiments/tests`.
