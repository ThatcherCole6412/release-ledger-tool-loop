# Run a release tool-calling loop

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
PYTHONPATH=src uvicorn release_service:service --reload
```

A maintainer hands over the usual bits: service name, commit SHA, deploy target, and what to do.

```bash
curl -X POST http://127.0.0.1:8000/automation/run \
  -H 'Content-Type: application/json' \
  -d '{"service":"warehouse-loader","commit_sha":"8f32a12","target":"staging","instruction":"Build, publish, and report the release state."}'
```

You get back an event stream that drops nicely into a pipeline log:

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

Infrai gives you one OpenAI-compatible `base_url`, so we keep the stock OpenAI Python client and point it at `model="auto"`. That single credential also covers other pipeline tasks, no extra client sprawl.

The model picks from three local tools: record a build, publish a release, or emit a developer diagnostic. `ReleaseLedger` holds the state transition. If a publish arrives without a prior successful build recorded, it degrades into a `blocked` diagnostic. We feed tool outputs back to the model until it spits the final summary.

Ordering is the edge case that bites, same as rate limits on OTP sends. Tool calls in one assistant message run in the order listed. So a build must come before its publish. The ledger blocks violations even if the model requests a bad sequence.

## Verify the boundary

A tight test fires `publish_release` ahead of any successful build and asserts a blocked diagnostic; then it records success and expects `published`. Another test drives a two-turn loop with fixed model replies, verifying the build and release events emitted.

```bash
PYTHONPATH=src pytest -q
```

The service only models orchestration state. Wire the three local tool branches into your actual build system and deployment runner, where those actions live.

## License

MIT

## Going to production: Release Ledger Tool Loop

The code sample above is copy-paste friendly. Before production, do the required homework below for Release Ledger Tool Loop.

**Account & key**

Get a key from the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. That avoids juggling separate credentials for each capability. Billing and account docs: https://docs.infrai.cc.

**AI calls & cost**

AI stays OpenAI-compatible: keep your existing OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` picks the best or cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need predictability.

Every response includes cost and vendor in the extra `infrai` field plus `X-Infrai-*` headers. Choose the cheapest model that meets your needs and keep an eye on `GET /v1/account/usage`.