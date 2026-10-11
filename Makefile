.PHONY: test lint run up down smoke pipeline k8s-up k8s-down tf-plan ansible-run

test:            ## run unit tests
	python3 -m unittest discover -s tests -v

lint:            ## static analysis
	python3 -m flake8 app tests --max-line-length=120

run:             ## run the app locally (SQLite, no Docker needed)
	CREATE_APP_ON_IMPORT=1 python3 -m app.app

up:              ## full stack: app + postgres + prometheus + grafana
	docker compose up -d --build

down:
	docker compose down

smoke:           ## end-to-end check of a running instance
	./scripts/smoke_test.sh http://localhost:5000

pipeline:        ## run the CI/CD stages locally (lint -> test -> build -> smoke)
	./scripts/local_pipeline.sh

k8s-up:          ## deploy to the current kubectl context (e.g. minikube)
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/

k8s-down:
	kubectl delete namespace student-mgmt

tf-plan:
	cd terraform && terraform init && terraform plan

ansible-run:
	cd ansible && ansible-galaxy collection install -r requirements.yml && ansible-playbook playbook.yml
