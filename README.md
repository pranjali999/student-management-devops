# Automated CI/CD Pipeline for a Student Management System

A Student Management System (Flask REST API + web UI) wrapped in a complete **cloud automation / DevOps toolchain**:
every `git push` is automatically linted, tested, containerised, smoke-tested, deployed, and monitored.

Topic chosen: **"Automated CI/CD Pipeline for a Student Management System"**

## Architecture

```
 Developer ──git push──▶ GitHub ──▶ CI/CD pipeline (GitHub Actions  or  Jenkins)
                                      │ 1. Lint (flake8)
                                      │ 2. Unit tests (15 tests)
                                      │ 3. Build Docker image  (tag = git SHA)
                                      │ 4. Push to registry (GHCR / Docker Hub)
                                      │ 5. Smoke test the image
                                      │ 6. Deploy ──┬─▶ Kubernetes (rolling update + HPA autoscaling)
                                      │             └─▶ AWS EC2 server (provisioned by Terraform,
                                      │                                  configured by Ansible)
                                      ▼
                         Running app ──/metrics──▶ Prometheus ──▶ Grafana dashboard
                                                       └──▶ Alert rules (AppDown, HighErrorRate, HighLatency)
```

## Cloud automation tools used

| Area | Tool | Where | What it automates |
|---|---|---|---|
| Version control | Git / GitHub | repo | Single source of truth, triggers the pipeline |
| CI/CD | **GitHub Actions** | `.github/workflows/ci-cd.yml` | lint → test → build → push → smoke test → deploy |
| CI/CD | **Jenkins** | `Jenkinsfile` | Same pipeline as declarative stages (alternative to Actions) |
| Containers | **Docker** | `Dockerfile` | Reproducible, non-root image with a HEALTHCHECK |
| Multi-container | **Docker Compose** | `docker-compose.yml` | App + PostgreSQL + Prometheus + Grafana in one command |
| Orchestration | **Kubernetes** | `k8s/` | Deployment (rolling updates), Service, StatefulSet DB, probes |
| Auto-scaling | **Kubernetes HPA** | `k8s/hpa.yaml` | 2 → 6 pods when CPU > 60% |
| Infrastructure as Code | **Terraform** | `terraform/` | Creates EC2 + security group + key pair on AWS |
| Config management | **Ansible** | `ansible/` | Installs Docker, deploys the stack, waits for health |
| Monitoring | **Prometheus** | `monitoring/prometheus.yml` | Scrapes `/metrics` every 10 s |
| Dashboards | **Grafana** | `monitoring/grafana/` | Auto-provisioned datasource + dashboard |
| Alerting | **Prometheus alert rules** | `monitoring/alert_rules.yml` | App down, high 5xx rate, high latency |
| Testing | unittest + shell smoke test | `tests/`, `scripts/smoke_test.sh` | Automated verification before and after deploy |

## Quick start

### 1. Run locally, no Docker needed
```bash
pip install Flask
make test        # 15 unit tests
make run         # http://localhost:5000
make pipeline    # runs lint -> test -> (build) -> smoke test, like the real CI
```

### 2. Full stack with Docker Compose
```bash
docker compose up -d --build
```
| Service | URL |
|---|---|
| Student app | http://localhost:5000 |
| Prometheus | http://localhost:9090 (Status → Rules shows the alerts) |
| Grafana | http://localhost:3000 (admin / admin) → dashboard "Student Management System" |

Then `make smoke` to run the end-to-end check.

### 3. Kubernetes (minikube)
```bash
minikube start
minikube addons enable metrics-server          # needed by the HPA
docker build -t student-management:local .
minikube image load student-management:local
# point the deployment at the local image:
sed -i 's|image: ghcr.io/.*|image: student-management:local|' k8s/deployment.yaml
kubectl apply -f k8s/namespace.yaml && kubectl apply -f k8s/
kubectl -n student-mgmt get pods,svc,hpa
minikube service sms-app -n student-mgmt --url
```
Demo autoscaling: generate load (`kubectl run -it load --rm --image=busybox -- sh -c "while true; do wget -q -O- http://sms-app.student-mgmt/api/students; done"`) and watch `kubectl -n student-mgmt get hpa -w`.

### 4. AWS with Terraform + Ansible
```bash
cd terraform && terraform init && terraform apply     # creates EC2, writes ansible/inventory.ini
cd ../ansible && ansible-galaxy collection install -r requirements.yml
ansible-playbook playbook.yml -e image=ghcr.io/<you>/student-management-devops:latest
terraform -chdir=../terraform output app_url
```
Remember `terraform destroy` afterwards to avoid charges.

### 5. Enable the real CI/CD pipeline
1. Push this folder to a GitHub repo (branch `main`). Actions runs lint + tests + build + push to GHCR + smoke test automatically.
2. Replace `YOUR_GITHUB_USER` in `k8s/deployment.yaml` and `ansible/playbook.yml`.
3. For the deploy job: add repo secret `KUBE_CONFIG` (base64 kubeconfig) and repo variable `DEPLOY_ENABLED=true`.
4. For Jenkins: create a Pipeline job from SCM, add credentials `dockerhub-creds` and `kubeconfig`, edit `IMAGE_REPO`.

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness/readiness probe |
| GET | `/metrics` | Prometheus metrics |
| GET/POST | `/api/students` | List (supports `?q=`) / create |
| GET/PUT/DELETE | `/api/students/<id>` | Read / update / delete |

## Project structure
```
app/            Flask app + HTML UI          tests/       15 unit tests
Dockerfile      container image              k8s/         Kubernetes manifests
docker-compose.yml  full local stack         terraform/   AWS infrastructure (IaC)
.github/workflows/  GitHub Actions CI/CD     ansible/     server config + deploy
Jenkinsfile     Jenkins CI/CD                monitoring/  Prometheus, alerts, Grafana
scripts/        smoke test + local pipeline  Makefile     shortcuts
```

## Verification status (be upfront about this in your viva)
| Part | Status |
|---|---|
| Flask app, REST API, validation, metrics | Run and tested: 15/15 unit tests pass |
| Local pipeline (`make pipeline`) incl. live smoke test | Run end-to-end successfully |
| YAML/JSON configs (compose, k8s, workflow, Ansible, Prometheus, Grafana) | Parsed and syntax-checked |
| PostgreSQL mode (`DATABASE_URL`) | Code path written but **not executed** in the build environment, so run `docker compose up` once to confirm |
| Docker build, Kubernetes, Terraform, Ansible, GitHub Actions, Jenkins | Written to standard practice but **not executed** (build environment had no Docker/cloud/network access). Do a dry run before presenting |

## Known limitations / future work
- Demo passwords are hard-coded; production should use Kubernetes Secrets from a vault / Terraform-managed secrets.
- No authentication on the API.
- Single-node Postgres; a managed database (RDS) would be the next step.
- Could add GitOps (ArgoCD), Trivy image scanning, and blue-green deployment.
