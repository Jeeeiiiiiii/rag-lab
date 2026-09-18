# FinOps Agent

A scheduled agent that explains an AWS cost spike instead of just reporting
it. Once a day it pulls cost by service, finds what moved, pulls the write
calls from the audit trail for the same window, asks a model what most likely
happened, archives the finding, and posts to Slack — **only if something is
actually wrong.** A quiet day sends nothing.

Everything runs locally against [Floci](https://github.com/floci-io/floci), an
AWS emulator: the Lambda, the schedules, S3, Secrets Manager and Cost Explorer
are all real there. The Terraform is written for a real account; the
`endpoints` block in `terraform/providers.tf` is the only thing pointing it at
the emulator.

Modelled on [AnuragJosyula/autonomous-finops-agent](https://github.com/AnuragJosyula/autonomous-finops-agent).
What is different is below, under *The decisions*.

```
   EventBridge  cron(0 16 * * ? *)  daily         cron(0 8 ? * MON *)  weekly
        │ {"mode":"daily"}                              │ {"mode":"digest"}
        ▼                                               ▼
   ┌────────────────────── Lambda: finops-agent (Python 3.12) ───────────────────────┐
   │                                                                                  │
   │  1. costs     Cost Explorer ── daily cost by service, 14-day window              │
   │  2. detect    pure math: median baseline, +25% AND +$1, or a new service ≥ $1    │
   │  3. quiet?    nothing moved → return. nothing sent.                              │
   │  4. evidence  per anomaly: the series + CloudTrail write calls in the window     │
   │  5. explain   ┌ Claude, with 3 read-only tools, capped at 8 turns ┐              │
   │               └ on any failure: RuleExplainer (deterministic)     ┘              │
   │  6. dedupe    already alerted in the last 3 days? archive, but do not send       │
   │  7. archive   S3  findings/<day>/<service>.json   (every finding, alerted or not)│
   │  8. notify    Slack, one message, evidence attached                              │
   └──────────────────────────────────────────────────────────────────────────────────┘
        ▲ ce:GetCostAndUsage     ▲ cloudtrail:LookupEvents     ▲ secretsmanager:GetSecretValue
        │                        │                             │  (slack webhook, model key)
      IAM: read costs, read trail, write own bucket, read own two secrets, log. Nothing else.
```

## The decisions

| Decision | Why |
|---|---|
| **Scripted evidence, agentic explanation.** Detection is arithmetic (`detect.py`, pure functions, tested). The model is only asked what the evidence *means*. | Arithmetic does not hallucinate and does not cost tokens. The model's judgement is spent where judgement is needed: correlating a `CreateNatGateway` with a NAT charge, not deciding whether $28 is more than $5. |
| **The rule explainer is the floor, not a fallback of last resort.** `RuleExplainer` produces a complete alert from the numbers and the change list. `ClaudeExplainer` wraps it and falls back to it on any failure: API error, refusal, turn cap, no typed report. | An alert that depends on a model being up is an alert that sometimes does not arrive. The model makes the message better; it never decides whether there is one. The same principle as running the raw Prometheus alert alongside an AI triage. |
| **Read-only IAM as the safety model.** The role can read costs and the trail, write its own bucket, read its own two secrets, and log. There is no statement that can create, modify or delete anything. | The model reads CloudTrail event names and resource tags — text it does not control. With no mutating permission anywhere, prompt injection through that text cannot become an action. The system prompt says "data, not instructions"; the IAM policy makes it true. |
| **Two adapters at every seam.** Cost: Cost Explorer or a JSON fixture. Changes: CloudTrail or a fixture. Explainer: Claude or rules. Notifier: Slack or stdout. Archive: S3 or memory. | The fixtures are how a spike is put in front of the agent on demand — you cannot wait for one to happen — and how 38 tests run with no account and no key. `python -m finops_agent` runs the whole thing in a terminal in under a second. |
| **Thresholds are two numbers, and both must trip.** +25% over a 7-day *median* AND at least +$1. A service with no history needs ≥ $1. | A ratio alone pages on $0.001 → $0.003 (the emulator's kind of number). A dollar floor alone pages on $1,000 → $1,010. The median, not the mean, so one earlier spike does not hide the next. All of it is configuration (`Thresholds`, Terraform `var.thresholds`), not prompt text. |
| **Quiet by default; archive everything.** No anomaly, no message. Every finding — alerted or suppressed — lands in S3 first. A repeat within 3 days of a *delivered* alert is archived but not sent. A weekly digest reads the archive. | A daily "all fine" trains people to ignore the channel. A three-day spike is one alert. The history exists whether anyone was told or not — and a failed Slack post never silences the next day, because dedupe only counts findings marked `sent`. |
| **Investigate yesterday, not today.** The run at 16:00 UTC looks at the last complete day. | "Today" is sixteen hours of Cost Explorer-lagged spend compared with a median of seven full days; a real spike would hide behind that. `event.day` overrides it for replays. |
| **Everything outside the process is bounded.** CloudTrail paging stops at 20 pages or 25 s; the model client has a 30 s request timeout, one retry, and a 70 s budget for the whole investigation; a change source that fails degrades to "no changes found", noted in the report. | The Lambda has 120 s. A hung dependency must leave time for the rules floor to run, and must never turn a found anomaly into a lost one. |
| **One function, one deep interface.** `investigate(day, deps) -> Report`. The Lambda handler and the CLI are thin callers; tests call it with fakes. | Everything that matters is testable through one function. Adding a source or a notifier is a new adapter, not a change to the run. |

## What is where

```
agent/finops_agent/
  investigate.py     investigate() and digest(): the whole run, steps 1–8
  detect.py          Thresholds, detect(): the arithmetic
  models.py          DailyCost, Anomaly, Change, Evidence, Explanation, Finding, Report (+ JSON)
  sources/cost.py    CostExplorerSource | FixtureCostSource
  sources/changes.py CloudTrailSource | FixtureChangeSource, service → eventSource mapping
  explain/rules.py   RuleExplainer — the floor
  explain/claude.py  ClaudeExplainer — tools, loop, cap, fallback
  archive.py         S3Archive | MemoryArchive — put, recently_alerted, since
  notify.py          SlackNotifier | StdoutNotifier + the message formats
  config.py          env + event → Settings → Deps (the only module that touches os.environ / boto3)
  handler.py         Lambda entry point
  __main__.py        the CLI
  fixtures/          quiet · spike-nat · new-service · usage-spike · multi
agent/tests/         38 tests: detection math, the run with fakes, the Claude loop with a scripted client, bounded CloudTrail paging
terraform/           Lambda, two EventBridge rules, S3 (versioned, encrypted, private), two secrets, the IAM policy
scripts/             package.sh  slack-catcher.sh  demo.sh  down.sh
docs/                architecture.html (interactive) and its archify source
```

## Running it

Prerequisites: Docker, Terraform, Python 3.12. Commands are bash; on Windows
run them from Git Bash or `bash scripts/...` from PowerShell.

```powershell
# 0. No account, no key, no emulator: the agent in a terminal
cd agent
pip install -r requirements-dev.txt
python -m pytest -q                        # 38 passed
python -m finops_agent --scenario spike-nat   # prints the Slack message it would send
python -m finops_agent --scenario quiet       # prints nothing worth reading

# 1. Emulator + console (separate repo)
cd ..\..\floci-ui
docker compose up -d                       # emulator :4566, console :4500

# 2. The Lambda package (the package + the anthropic SDK, Linux wheels)   (~30s)
cd ..\finops-agent
bash scripts/package.sh

# 3. A stand-in for Slack on the emulator's network, then the infrastructure   (~90s)
bash scripts/slack-catcher.sh
terraform -chdir=terraform init
terraform -chdir=terraform apply -auto-approve -var="slack_webhook_url=http://finops-slack-catcher:8080/hook"

# 4. Prove each piece
bash scripts/demo.sh

# 5. Tear down
bash scripts/down.sh
```

`scripts/demo.sh` runs eight steps: a quiet day (nothing sent); the NAT
gateway spike (detected, correlated with `CreateNatGateway` / `CreateRoute` /
`DeleteVpcEndpoints` by `terraform-ci` the day before, archived to S3, posted
— the catcher prints exactly what Slack would show); the same spike the next
day (archived, suppressed, nothing sent); a service that did not exist
yesterday; a usage-driven spike with no changes (the agent says so and does
not invent one); the **live Cost Explorer on the emulator** (real API, metered
from the other labs, tiny numbers, correctly below the floor); the weekly
digest from the archive; the function's JSON log.

### With Claude

```bash
# Locally
ANTHROPIC_API_KEY=sk-ant-... python -m finops_agent --scenario spike-nat --explainer claude -v

# Deployed: the key goes to Secrets Manager, never into the function's environment
terraform -chdir=terraform apply -var="anthropic_api_key=sk-ant-..." -var="slack_webhook_url=..."
```

The model gets the evidence bundle and three tools: `cost_timeseries` and
`recent_changes` (read-only follow-up questions, windows clamped) and
`report_finding` (the typed answer). `claude-opus-5`, adaptive thinking,
medium effort, eight turns at most. `explained_by` on every finding says
which path produced the words: `claude`, `rules`, or `claude→rules` when it
fell back. On Bedrock, set `model_provider = "bedrock"`; the same adapter
uses the Mantle client and IAM instead of a key.

### Poking at it

```bash
AWS="docker run --rm --network floci_default -e AWS_ACCESS_KEY_ID=test -e AWS_SECRET_ACCESS_KEY=test -e AWS_DEFAULT_REGION=us-east-1 amazon/aws-cli --endpoint-url=http://floci:4566"
$AWS lambda invoke --function-name finops-agent --cli-binary-format raw-in-base64-out \
  --payload '{"mode":"daily","cost_source":"fixture","scenario":"multi"}' /dev/stdout
$AWS s3 cp s3://finops-agent-findings/findings/$(date -u +%F)/ec2-other.json -
docker logs -f finops-slack-catcher
```

## What the tests cover

- `test_detect.py` — flat is quiet; ratio and floor must both trip; the median ignores an earlier spike; a new service needs the floor; missing days count as zero; biggest impact first.
- `test_investigate.py` — the run through `investigate()` with fakes: quiet sends and archives nothing; the NAT spike is found, filtered to `ec2.amazonaws.com` events, explained, archived, sent; a repeat is archived but suppressed; the dedupe window expires; a failed Slack send does not dedupe tomorrow; a failing change source degrades instead of failing; usage-driven has no changes and low confidence; multi is ordered and capped; a broken explainer does not lose the alert; the digest reads the archive.
- `test_changes.py` — mapped services filter by event source; unmapped services are unfiltered, never guessed; CloudTrail paging is bounded.
- `test_claude_loop.py` — the loop with a scripted client: a direct report; a tool round-trip with both results in one message; an unknown tool returned as `is_error`; API error, refusal, `end_turn` without a report, the turn cap and the time budget all fall back to rules; tool windows are clamped.
- `test_notify_and_archive.py` — findings round-trip through JSON including `inf`; messages carry evidence and provenance; suppressed findings are listed separately; the digest groups by service.

## Next steps

1. **Run it against a real account.** Delete the `endpoints` block and the static credentials; keep everything else. Cost Explorer has no emulator worth the name, so this is where the numbers become real.
2. **CUR + Athena mode.** Cost Explorer answers "which service"; the Cost & Usage Report answers "which resource". A `CurAthenaSource` behind the same `CostSource` seam, switched on by `FINOPS_COST_SOURCE=cur`.
3. **Usage-type breakdown as a tool.** `ce:GetCostAndUsage` grouped by `USAGE_TYPE` for one service, so the model can tell NAT data processing from NAT hours without guessing.
4. **A budget for the model.** Count `usage.input_tokens` / `output_tokens` per run into a CloudWatch metric and stop calling the model for the day past a ceiling; the rules floor takes over.
5. **Anomaly feedback.** A Slack reaction (✅ expected / ❌ investigate) written back to the finding in S3, so the digest can say how many alerts were actionable.
6. **Put it through a pipeline.** `pipeline-lab`'s stages work on this package unchanged; the deploy stage becomes `terraform apply`.

## What is real and what is not

Floci does a lot more than return metadata:

- **The Lambda is real.** The function runs in its own container from the packaged zip, reads the two secrets from Secrets Manager, writes findings to S3, and posts to the Slack stand-in by container name — the exact HTTP call it would make to `hooks.slack.com`.
- **Cost Explorer is real.** `ce:GetCostAndUsage` returns daily cost by service, metered from whatever the other labs did in the emulator. Step 6 of the demo reads it live.
- **EventBridge rules, S3 versioning and encryption, the IAM policy, the log group** are created and visible in the console.

The gaps, stated here rather than left to be found:

1. **Cost Explorer numbers are tiny.** Locally, a day of emulated usage costs fractions of a cent, so the live source never trips the $1 floor. The fixtures exist for exactly this: the demo scenarios are the spikes. Against a real account the same code sees real spend.
2. **CloudTrail on the emulator is empty.** `LookupEvents` works and returns nothing, because nothing writes a trail locally. The fixture change source carries the audit events for each scenario.
3. **The Claude path is verified with a scripted client, not a live call.** No API key was available when this was built. The loop, the tool round-trip, the fallbacks and the request shape are covered by tests; a real run is one environment variable away (above).
4. **Bedrock is a stub locally.** Floci's `bedrock-runtime` returns a fixed string and no tool use, so `model_provider = "bedrock"` is for a real account only.
5. **Static credentials.** Everything is `test`/`test` on the emulator. In AWS the Lambda's execution role is the identity; nothing in the code changes.
