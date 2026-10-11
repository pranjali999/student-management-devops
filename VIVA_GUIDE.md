# Viva Guide: Automated CI/CD Pipeline for a Student Management System

## 30-second summary (memorise this)
"My project automates the full software delivery lifecycle of a Student Management System. When a developer pushes code,
GitHub Actions (or Jenkins) automatically lints and tests it, builds a Docker image, runs a smoke test, and deploys it to Kubernetes.
Infrastructure on AWS is created with Terraform and configured with Ansible. Prometheus and Grafana monitor the running app and
raise alerts. Everything is defined as code, so it's repeatable and needs no manual steps."

## Core concepts
- **DevOps**: culture + practices that join development and operations to ship software faster and more reliably through automation.
- **CI (Continuous Integration)**: every commit is automatically built and tested so integration bugs are found early.
- **CD (Continuous Delivery/Deployment)**: every passing build is automatically released (delivery = ready to release, deployment = released automatically).
- **Cloud automation**: replacing manual provisioning, configuration and deployment with scripts/tools.
- **Infrastructure as Code (IaC)**: servers/networks described in version-controlled files (Terraform) rather than clicked in a console.
- **Immutable infrastructure/images**: we never patch a running server; we build a new image and replace it.

## Tool-by-tool: what, why, where in the project
| Tool | What it is | Why we used it | File |
|---|---|---|---|
| Docker | Packages app + dependencies into a portable image | "Works on my machine" problem; identical in dev, CI and prod | `Dockerfile` |
| Docker Compose | Defines multi-container apps in YAML | One command starts app+DB+monitoring | `docker-compose.yml` |
| GitHub Actions | CI/CD service built into GitHub | Automates test → build → push → deploy on each push | `.github/workflows/ci-cd.yml` |
| Jenkins | Self-hosted CI/CD server | Same pipeline, for orgs that self-host; shows tool-independence | `Jenkinsfile` |
| Kubernetes | Container orchestrator | Self-healing, rolling updates, scaling, service discovery | `k8s/` |
| HPA | Horizontal Pod Autoscaler | Adds/removes pods based on CPU | `k8s/hpa.yaml` |
| Terraform | Declarative IaC for cloud resources | Creates EC2, security group, key pair reproducibly | `terraform/` |
| Ansible | Agentless configuration management over SSH | Installs Docker, deploys stack, idempotent | `ansible/` |
| Prometheus | Time-series metrics database (pull model) | Scrapes `/metrics`, evaluates alert rules | `monitoring/` |
| Grafana | Dashboard tool | Visualises Prometheus data | `monitoring/grafana/` |

## Likely questions and answers

**Q: Why Docker instead of a virtual machine?**
Containers share the host kernel, so they start in seconds and use far less memory than VMs, which each run a full OS. VMs give stronger isolation; containers give speed and density.

**Q: Walk me through your pipeline.**
Push to `main` → checkout → install deps and run flake8 → run 15 unit tests → build the Docker image tagged with the git SHA → push to the registry → run the image and smoke test `/health` plus a create/read/delete round trip → `kubectl apply` with the new image tag → wait for `rollout status`. If any stage fails, later stages don't run, so broken code never deploys.

**Q: Why tag images with the git commit SHA instead of only `latest`?**
A SHA tag is unique and traceable: you know exactly which commit is running and can roll back to a specific version. `latest` is mutable and ambiguous.

**Q: Difference between Terraform and Ansible?**
Terraform *provisions* infrastructure (creates the server, network rules); it's declarative and keeps state. Ansible *configures* what runs on it (installs Docker, deploys containers); it's procedural-ish, agentless and idempotent. In my project Terraform creates the EC2 instance and even writes Ansible's inventory file, then Ansible deploys.

**Q: What does "idempotent" mean?**
Running it repeatedly gives the same end state without side effects. Running my Ansible playbook twice doesn't reinstall Docker or duplicate anything.

**Q: Declarative vs imperative?**
Declarative: describe the desired end state (Terraform, Kubernetes YAML) and the tool figures out how. Imperative: list the steps to run (a shell script).

**Q: How does Kubernetes keep the app available during an update?**
`RollingUpdate` with `maxUnavailable: 0, maxSurge: 1` starts a new pod, waits for its readiness probe to pass, then terminates an old one, so there's no downtime.

**Q: Liveness vs readiness probe?**
Readiness decides whether a pod receives traffic. Liveness decides whether a pod should be restarted. Both hit `/health`, which also checks the database connection.

**Q: How does autoscaling work?**
The HPA compares average CPU use to the 60% target (relative to the CPU *request* in the Deployment) and adjusts replicas between 2 and 6. It requires metrics-server.

**Q: Why does the HPA need `resources.requests`?**
Utilisation is a percentage of the requested CPU; without a request there's no baseline to compute it.

**Q: How does monitoring work here?**
The app exposes `/metrics` in Prometheus text format (request counts by status, latency sums, student count, uptime). Prometheus pulls it every 10 seconds, stores it, and evaluates `alert_rules.yml`. Grafana queries Prometheus to draw panels.

**Q: Pull vs push monitoring?**
Prometheus pulls (scrapes) targets, which makes it easy to detect a dead target (`up == 0`, my AppDown alert). Push-based systems rely on the app to report.

**Q: Why do you run gunicorn with 1 worker?**
My metrics counters live in process memory. Multiple workers would each keep separate counters and Prometheus would see inconsistent values. I scale by adding *pods* instead, which Prometheus tracks separately. (Alternative: multiprocess mode of prometheus_client.)

**Q: Why PostgreSQL in Compose/Kubernetes but SQLite in tests?**
SQLite needs no setup, so unit tests run anywhere with zero services. With several pods sharing one SQLite file you'd get inconsistent data, so Compose/K8s use PostgreSQL. The app switches via the `DATABASE_URL` environment variable (12-factor config).

**Q: What security measures did you apply?**
Non-root container user, minimal base image (`python:slim`), SSH/Grafana/Prometheus ports restricted via a Terraform variable, input validation and parameterised SQL (prevents SQL injection), secrets kept out of the image. Honest limitation: demo passwords are hard-coded and the API has no authentication; production would use a secrets manager and auth.

**Q: What would you improve?**
GitOps with ArgoCD, image vulnerability scanning (Trivy), blue-green/canary releases, managed database, authentication, centralised logging (ELK/Loki).

**Q: How is this "cloud automation"?**
Every step from commit to a monitored production deployment, including creating the cloud servers themselves, happens through code and pipelines with no manual console work.

**Q: What happens if a new commit breaks a test?**
The `test` job fails, `build`/`deploy` are skipped (they `need: test`), and the previous version keeps running.

**Q: How would you roll back?**
`kubectl -n student-mgmt rollout undo deployment/sms-app`, or redeploy an earlier SHA-tagged image.

## Live demo script (about 5 minutes)
1. Show the repo structure and name the tool behind each folder.
2. `make pipeline` (or push a commit and show the Actions tab): lint → tests → smoke test pass.
3. `docker compose up -d --build`, open the app at :5000 and add a student.
4. Open Grafana at :3000 and show requests rising on the dashboard.
5. `docker compose stop app`, then show the AppDown alert firing in Prometheus (:9090/alerts). Start it again.
6. (If using Kubernetes) `kubectl get pods`, delete a pod and watch it self-heal; show the HPA.
7. Show `terraform plan` output and the Ansible playbook as the "infrastructure from code" part.

## Be ready to admit
Docker/Kubernetes/Terraform/Ansible files follow standard practice but do a dry run before the presentation so you've seen each one work yourself. Examiners respect "I tested X, and here is what I learned" far more than a memorised answer.
