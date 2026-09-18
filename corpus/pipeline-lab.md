# Pipeline Lab

A small app pushed through a real delivery pipeline onto Kubernetes, with a
security gate on each side of the build and the three observability pillars
watching the result. The app is four HTTP routes and is beside the point;
**the pipeline and the platform are the subject.**

Everything runs locally against [Floci](https://github.com/floci-io/floci), an
AWS emulator, on an EKS cluster Terraform creates there. The pipeline is a
GitHub Actions workflow executed by a self-hosted runner on this machine, so
a `git push` really does end with a new version answering on the cluster.

```
 git push                       GitHub Actions  (runner/: self-hosted, on this machine)
    │      ┌──────────┬────────────┬─────────┬──────────────┬──────┬────────┬──────────┬─────────┐
    └─────▶│ semgrep  │ trivy      │ docker  │ trivy image  │ push │ helm   │ zap      │ publish │
           │ SAST     │ IaC scan   │ build   │ SBOM + vulns │ ECR  │ deploy │ DAST     │ S3      │
           └──────────┴─────┬──────┴─────────┴──────┬───────┴───┬──┴───┬────┴────┬─────┴────┬────┘
                      gate: CRITICAL          gate: CRITICAL    │      │         │          │
                                              with a fix        ▼      ▼         ▼          ▼
   AWS (Floci) ─────────────────────────────────────────────────────────────────────────────────
   ┌────────┐  ┌──────────────┐  ┌───────────────────────────────────────────────────┐  ┌──────┐
   │  ECR   │  │ Secrets Mgr  │  │  EKS                                              │  │  S3  │
   │ app:   │  │ app/api-key  │  │  ┌──────────┐   ┌─────────────┐  ┌─────────────┐  │  │ SBOM │
   │ <sha>  │──│ grafana/adm  │──│─▶│ ext.      │──▶│ app         │◀─│ ingress-    │◀─│  │ SAST │
   └────────┘  │ dast/token   │  │  │ secrets   │   │ (Helm)      │  │ nginx :30080│  │  │ DAST │
               └──────────────┘  │  └──────────┘   └──┬───┬───┬──┘  └─────────────┘  │  │ IaC  │
                                 │      metrics ◀──────┘   │   └──────▶ traces         │  └──────┘
                                 │  ┌────────────┐  ┌──────▼─────┐  ┌────────────┐    │
                                 │  │ Prometheus │  │ Loki       │  │ Tempo      │    │
                                 │  │ Alertmgr   │  │ (Promtail) │  │ (OTLP)     │    │
                                 │  └─────┬──────┘  └──────┬─────┘  └──────┬─────┘    │
                                 │        └───────────────▶ Grafana ◀──────┘          │
                                 └───────────────────────────────────────────────────┘
```

An interactive version of this diagram, with guided views for the pipeline,
the secrets path, and observability: open `docs/architecture.html` in a
browser (source: `docs/architecture.archify.json`).

## The decisions

| Decision | Why |
|---|---|
| **Thin workflow, thick scripts.** `pipeline.yml` only names stages; each is a script in `scripts/ci/`. | The same stage runs identically on a push, in the toolbox container, and in a terminal. When a stage fails, you re-run *that script*, not the workflow. |
| **Self-hosted runner in a container.** `runner/` builds one image with every tool; GitHub dispatches jobs to it. | GitHub-hosted runners cannot reach a cluster on this laptop. The same image is the "toolbox" for running the pipeline by hand. |
| **Two gates, both on CRITICAL.** IaC misconfigurations fail at CRITICAL; image vulnerabilities fail at CRITICAL *with a fix available*. HIGH is reported. | A gate you tune to zero findings gets disabled within a week. A CRITICAL with a fix is the case nobody argues about. `PLANT_VULN=1` proves both gates fire. |
| **Images in ECR, everything else in S3.** Immutable tags, the tag is the commit SHA. | The image is what is deployed; the SBOM and reports are what is known about it. Versioned bucket, keyed by tag: re-running a commit keeps both sets. |
| **Secrets in Secrets Manager, pulled by External Secrets.** Terraform generates them; ESO writes them into Kubernetes Secrets. | No secret in git, values files, or the image. Adding one is a Terraform resource plus one line in `helm/app/values.yaml`. |
| **Grafana is the only UI.** Prometheus, Loki and Tempo behind it, with a log line linking to its trace and a trace linking to its logs. | Three pillars, one place. The app emits all three itself: `/metrics`, JSON logs with a `trace_id`, OTLP spans. |
| **The app ships its own dashboard and alert rule.** A ConfigMap and a PrometheusRule in the app chart. | The platform never changes when an app is added. The app declares what "healthy" means for itself. |

## What is where

```
terraform/     VPC (2 public + 2 private), EKS, ECR, S3 (versioned, KMS), Secrets Manager, IAM
app/           Flask: /  /work (needs the API key)  /boom (500)  /healthz  /metrics  -- OpenTelemetry -> Tempo
helm/app/      the app chart: Deployment, Service, Ingress, ServiceMonitor, ExternalSecret,
               PrometheusRule (error rate > 5% for 1m), Grafana dashboard ConfigMap
platform/      Helm values: ingress-nginx, external-secrets, kube-prometheus-stack, loki-stack, tempo;
               SecretStores + the Grafana admin ExternalSecret
scripts/ci/    one script per pipeline stage, plus lib.sh (the only place addresses are decided)
scripts/       platform-up.sh  pipeline.sh  forward.sh  demo.sh  down.sh
runner/        the runner/toolbox image and its compose file
.github/       the workflow
.trivyignore.yaml   accepted IaC findings, each with its reason
```

## The pipeline, stage by stage

| Stage | Tool | Output to S3 | Fails when |
|---|---|---|---|
| `prepare` | git | — | — |
| `sast` | Semgrep (`p/python`, `p/secrets`, `p/dockerfile`) | `semgrep.json`, `semgrep.sarif` | any ERROR-severity finding |
| `iac-scan` | Trivy config on `terraform/`, `helm/`, `app/Dockerfile` | `trivy-config.json` | any CRITICAL not in `.trivyignore.yaml` |
| `build` | Docker | — | build error |
| `image-scan` | Trivy image: CycloneDX SBOM + vulnerabilities | `sbom.cdx.json`, `trivy-image.json` | any CRITICAL with a fixed version |
| `push` | Docker → ECR | — | tag already exists (immutable) |
| `deploy` | Helm `upgrade --install --wait`, then curl through the ingress | — | no `pushed.txt` from `push` (never deploys an unpublished tag); rollout fails; the new version does not answer |
| `dast` | OWASP ZAP baseline, authenticated with the DAST token | `zap-baseline.html`, `.json` | a FAIL-level rule (none by default; WARN is reported) |
| `publish-reports` | AWS CLI → `s3://pipeline-lab-reports/<tag>/` | everything above | — |

Pull requests run through `image-scan` and stop. Pushes to `main` run everything.

## Running it

Prerequisites: Docker, Terraform, kubectl, Helm. Commands are bash; on Windows
run them from Git Bash or `bash scripts/...` from PowerShell.

```powershell
# 1. Emulator + console (separate repo)
cd ..\floci-ui
docker compose up -d                       # emulator :4566, console :4500

# 2. Infrastructure: VPC, EKS, ECR, S3, Secrets Manager        (~90s)
cd ..\pipeline-lab
terraform -chdir=terraform init
terraform -chdir=terraform apply -auto-approve

# 3. The platform on the cluster: ingress, ESO, Prometheus, Loki, Tempo   (~8 min first time)
bash scripts/platform-up.sh

# 4. The pipeline, by hand, in the runner image      (~4 min; first run pulls the tool images)
docker compose -f runner/docker-compose.yml build toolbox
docker compose -f runner/docker-compose.yml run --rm toolbox scripts/pipeline.sh

# 5. Look at it
bash scripts/forward.sh                    # app :8080, Grafana :3000, Prometheus :9090, Alertmanager :9093
bash scripts/demo.sh                       # in another terminal

# 6. Tear down
bash scripts/down.sh
```

`scripts/demo.sh` proves each piece: the deployed version through the
ingress; `/work` refusing without the key and working with it (the key came
from Secrets Manager via ESO); Prometheus scraping the app; one request's
trace id in the pod log, in Loki, and in Tempo; the error-rate alert going
inactive → pending → firing after `/boom`; the image tags in ECR and the
reports in S3.

### Watching the gates fail

```bash
PLANT_VULN=1 docker compose -f runner/docker-compose.yml run --rm toolbox scripts/pipeline.sh scan
```

Semgrep finds three ERRORs in `scripts/ci/fixtures/planted.py` (command
injection, a hardcoded credential) and stops the pipeline. Skip past it to
the image gate and Trivy finds `CVE-2020-14343` (CRITICAL, fixed in PyYAML
5.4) in the image and stops it there. Nothing is pushed.

### The real pipeline: GitHub → this machine

```bash
cp runner/.env.example runner/.env         # REPO_URL and a PAT (see the file)
docker compose -f runner/docker-compose.yml up -d runner
```

Add two repository secrets on GitHub — `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY`, both `test` for the emulator — then push. The
runner shows up under Settings → Actions → Runners; the run shows up under
Actions; the new version shows up on `http://localhost:8080/`.

## Changing the app

Edit `app/app.py`, push. Nothing else changes. The image tag is the commit,
Helm rolls it out, the smoke test checks the new version answered.

When the app's *contract* changes, exactly one file changes:

| If you change… | …update | Because |
|---|---|---|
| the port | `helm/app/values.yaml` `containerPort` | Service, Ingress, probes, ServiceMonitor read it from there |
| the health path | `values.yaml` `probes.path` | |
| the metrics path | `values.yaml` `metrics.path` | |
| a secret it needs | `terraform/secrets.tf` (new resource) + one line under `externalSecrets.env` in `values.yaml` | ESO maps Secrets Manager → Kubernetes Secret key → env var |
| what "unhealthy" means | `values.yaml` `alerting.*`, or the rule in `helm/app/templates/prometheusrule.yaml` | |
| the language entirely | `app/Dockerfile` | Semgrep auto-detects; everything downstream consumes an image |

The platform (`platform/`), the workflow, and the stage scripts do not know
what the app is.

## Next steps

1. **The first real run.** Create the GitHub repo, push, start the runner (see "The real pipeline" above). Watch the Actions tab and then `http://localhost:8080/` answer with the commit SHA. Until this is done, gap 8 stands.
2. **Sign what you ship.** `cosign sign` the image in `push.sh` and a Kyverno `verifyImages` policy on the cluster, so an unsigned image cannot start — the gate on the *consuming* side.
3. **A second environment.** A `staging` namespace with a values overlay, deployed from pull requests to a PR-specific URL, and `main` promoting to `prod`. The chart already does not care which namespace it lands in.
4. **Pull-based delivery.** Replace `deploy.sh` with Argo CD watching a `deploy/` directory the pipeline commits the new tag into. The pipeline then never holds cluster credentials.
5. **Route the alert somewhere.** An Alertmanager receiver (Slack webhook, or just a `webhook` to a tiny logger pod) and a silence, so "the alert fired" becomes "someone was told".
6. **Load and scale.** An HPA on the app, `k6` from the toolbox against `/work`, and the dashboard showing replicas climb — the observability stack earning its keep.
7. **A "Nexus" after all.** Gitea's package registry (or Nexus if RAM allows) as a Helm chart and SBOM store, published from `publish-reports.sh` alongside S3.
8. **Keep the tools current.** Renovate (or Dependabot) on `runner/Dockerfile` ARGs, `platform-up.sh` chart versions, and `app/requirements.txt`; the image gate will tell you when an update matters.

## What the scanners found, and what happened

Worth recording, because it is what a pipeline is for:

- **IaC, first run:** CRITICAL — the EKS control plane security group allowed egress to `0.0.0.0/0`. Fixed: egress to the VPC CIDR only. Also HIGH: unencrypted S3 bucket → now SSE-KMS; EKS secrets encryption → *accepted* in `.trivyignore.yaml` because the emulator discards the setting (drift on every plan); public subnets assign public IPs → *accepted*, that is what public subnets are for.
- **Image, first run:** 3 CRITICAL in `perl-base` from the `python:3.12-slim` base, all with a Debian fix. Fixed: `apt-get upgrade` in the Dockerfile. 44 HIGH remain, none with a fix; reported, not blocking.
- **DAST, first run:** 5 warnings, all missing response headers. Fixed in the app (`X-Content-Type-Options`, CSP, `Permissions-Policy`, `Cross-Origin-Resource-Policy`). 2 remain: "non-storable content" (a property of `no-store`, not a problem) and a CSP fallback note.
- **Deploy of an unpushed tag:** after a `PLANT_VULN=1` scan run, `deploy.sh` tried to roll out the image the gate had (correctly) refused to push, and hung on `ImagePullBackOff`. Now `push.sh` writes `reports/pushed.txt` and `deploy.sh` refuses to run without it.
- **Hardened pod, first deploy:** `readOnlyRootFilesystem: true` crashed gunicorn — no `/tmp`. Fixed with an `emptyDir` at `/tmp`; the root stays read-only.

## What is real and what is not

- **EKS is a real cluster** (a k3s container Floci runs). Everything installed on it — ingress-nginx, External Secrets, Prometheus, Loki, Tempo, Grafana, the app — is genuinely running; `demo.sh` reads real samples, log lines, spans and alert states back out of them.
- **ECR is a real registry**, and the emulated node is preconfigured to pull from it by the real ECR URI. **S3 and Secrets Manager** are real; ESO fetches from Secrets Manager over the API.
- **The scanners are real** and their findings were real (above).

The gaps, stated here rather than left to be found:

1. **No load balancer.** The ingress is a NodePort on the emulated node; the runner and ZAP reach it by container name, you reach it through `scripts/forward.sh`. In AWS the AWS Load Balancer Controller would front it with an NLB. It is left out because it would be metadata locally and adds nothing to the story.
2. **The cluster does not survive a Docker restart.** The k3s node's IP changes and it refuses to start. `terraform -chdir=terraform apply -replace=aws_eks_cluster.this -auto-approve`, then `platform-up.sh` and the pipeline again.
3. **Pods cannot resolve the emulator by name**, so `platform-up.sh` pins its IP into the External Secrets values. If the emulator restarts with a new IP, re-run `platform-up.sh`.
4. **Node-exporter runs without the host root mount** (the emulated node's `/` is not a shared mount). Host filesystem metrics are missing locally; on in AWS.
5. **The registry has three names** (`localhost:5100` from here, the ECR URI from the cluster, `floci-ecr-registry:5000` inside the node). `lib.sh` handles the first; the node's preconfigured mirror handles the rest. In AWS there is one name.
6. **Static credentials.** ESO and the runner use `test`/`test`. In AWS: IRSA for ESO (drop the `auth` block in `platform/secret-stores.yaml`, annotate its ServiceAccount), and an IAM user or OIDC role for the runner.
7. **`max_retries` is not set** because there is no load balancer here; if you add one, see the note in `../order-lab/terraform/providers.tf`.
8. **The GitHub → runner hop is written, not exercised**: the repository had no remote when this was built. Every stage was run through the same image the runner uses, so what the runner does is what `pipeline.sh` does.
