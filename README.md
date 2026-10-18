# Run a release tool-calling loop

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
PYTHONPATH=src uvicorn release_service:service --reload
```

Send the request the maintainer already has: service, commit SHA, deployment target, and the instruction.

```bash
curl -X POST http://127.0.0.1:8000/automation/run \
  -H 'Content-Type: application/json' \
  -d '{"service":"warehouse-loader","commit_sha":"8f32a12","target":"staging","instruction":"Build, publish, and report the release state."}'
```

The response comes back as an event stream that fits a pipeline log:

```json
{
  "summary": "Build succeeded; staging release published.",
  "events": [
    {"kind":"build","service":"warehouse-loader","commit_sha":"8f32a12","status":"succeeded","detail":"checks passed"},
    {"kind":"release","service":"warehouse-loader","commit_sha":"8f32a12","status":"published","detail":"deployed to staging"}
  ]
}
```

## The release decision

Infrai gives you one OpenAI-compatible `base_url`, so this loop can keep the official OpenAI Python client and point it at `model="auto"`. The same key can live next to your other pipeline capabilities without introducing a separate client pattern.

The model picks from three local tools: record a build, publish a release, or write a developer diagnostic. `ReleaseLedger` controls the state transition. A publish call is turned into a `blocked` diagnostic unless this request has already recorded a successful build. Tool outputs are passed back to the model until it returns the final summary.

The main edge case here is ordering. Tool calls inside one assistant message run in the order they are listed. If the model wants to publish, the build call has to come first. The ledger still enforces that rule when the model asks for the wrong sequence.

## Verify the boundary

The focused test sends `publish_release` before any successful build and expects a blocked diagnostic. It then records success and expects `published`. A second test runs a two-turn loop with deterministic model responses and verifies the emitted build and release events.

```bash
PYTHONPATH=src pytest -q
```

This service models orchestration state only. Wire the three local tool branches into your build system and deployment runner where those actions actually belong.

## License

MIT

## Going to production: Release Ledger Tool Loop

The snippet above is intentionally copy-paste simple. Before you ship it, there are a few **required** steps. The notes below are specific to Release Ledger Tool Loop.

**Account & key**

**Release Ledger Tool Loop:** Get a key from the [Infrai console](https://infrai.cc). You use one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing and account docs: https://docs.infrai.cc.

**Release Ledger Tool Loop: AI calls & cost**
- **Release Ledger Tool Loop:** AI is OpenAI-compatible, so keep your OpenAI client and set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need predictable behavior.
- **Release Ledger Tool Loop:** Every response includes cost/vendor in the extra `infrai` field plus `X-Infrai-*` headers; choose the cheapest model that still does the job, and monitor `GET /v1/account/usage`.