# Groq cache_breakpoint compatibility fix - 28 October 2026

## Confirmed failure

The supplied Render log showed the first analyzer request failing with HTTP 400:
`messages.0 ... property 'cache_breakpoint' is unsupported`.
The backend and job routing were running. This was an unsupported message field,
not evidence of a rate limit or a need to replace API keys.

## Reproduction

The clean Linux image using the locked CrewAI 1.15.22 dependency added
`cache_breakpoint` to system messages. Its standard LiteLLM request preparation
retained that field. This reproduced the invalid outgoing payload without making
a model request. The existing local installed cache module already suppressed
the marker, explaining why earlier local live tests did not expose the issue.
Earlier mocked tests did not exercise this provider serialization boundary.

## Change

`GroqCompatibleLLM` removes the internal marker from the final completion
parameters for Groq requests only. It works on copied messages, preserves tool
call fields, and leaves global CrewAI functions and other provider instances
unchanged. The factory selects it for every `groq/` stage, including the analyzer,
solver, verifier and fact-checking roles. No installed dependency file is changed
by this fix; it is committed application code and survives fresh deployments.

Safe failure categories now travel through backend job results. The frontend
uses a fixed local message allowlist to distinguish authentication, rate limits,
transient errors, invalid requests, compatibility errors and invalid structured
outputs. It never displays arbitrary provider exception text.

## Actual validation

- 55 offline tests passed on Windows and in clean Linux.
- Regression tests inject marked system, assistant/tool-call and tool-result
  messages into real CrewAI request preparation and inspect the outgoing fields.
- Tests confirm the original messages and global marker function are unchanged.
- One real claim-extraction agent request succeeded against Groq from the clean
  Linux image, using the new factory and normal agent kickoff path.
- That live smoke check tests the formerly failing provider path, not overall
  solution accuracy or the full deployed Render-to-Streamlit pipeline.

## Rollout

Deploy the latest `main` commit on Render; keep the current build/start commands
and environment keys. Reboot/update the Streamlit frontend so it uses the matching
job contract and improved failure messages. Once both deployments are ready,
submit the question once. The actual hosted result still needs to be checked;
the small live Linux smoke request does not prove every later workflow stage.
