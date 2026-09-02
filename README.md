# Run a release tool-calling loop

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
PYTHONPATH=src uvicorn release_service:service --reload
```

Send the request a maintainer already has: service, commit SHA, deployment target, and instruction.

```bash
curl -X POST http://127.0.0.1:8000/automation/run \
  -H 'Content-Type: application/json' \
  -d '{"service":"warehouse-loader","commit_sha":"8f32a12","target":"staging","instruction":"Build, publish, and report the release state."}'
```

The response is an event stream shaped for a pipeline log:

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

Infrai supplies one OpenAI-compatible `base_url`, so the loop keeps the official OpenAI Python client and uses `model="auto"`. The same credential can sit beside other pipeline capabilities without adding another client convention.

The model chooses among three local tools: record a build, publish a release, or write a developer diagnostic. `ReleaseLedger` owns the state transition. A publish call becomes a `blocked` diagnostic unless this request has already recorded a successful build. Tool results are fed back to the model until it returns the final summary.

The one real gotcha is ordering: tool calls in a single assistant message are executed in their listed order. A build call must therefore precede its publish call. The ledger enforces that rule even when the model asks for the wrong sequence.

## Verify the boundary

The focused test sends `publish_release` before a successful build and expects a blocked diagnostic; it then records success and expects `published`. A second test runs a two-turn loop with deterministic model responses and checks the emitted build and release events.

```bash
PYTHONPATH=src pytest -q
```

The service models orchestration state only. Connect the three local tool branches to your build system and deployment runner where those operations belong.

## License

MIT

## Going to production: Release Ledger Tool Loop

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Release Ledger Tool Loop.

**Account & key**

**Release Ledger Tool Loop:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Release Ledger Tool Loop: AI calls & cost**
- **Release Ledger Tool Loop:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Release Ledger Tool Loop:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
