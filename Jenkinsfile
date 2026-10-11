// Declarative Jenkins pipeline - the same stages as the GitHub Actions workflow.
// Jenkins needs: Docker, Python 3, kubectl, and credentials 'dockerhub-creds' + 'kubeconfig'.
pipeline {
    agent any

    environment {
        IMAGE_REPO = 'YOUR_DOCKERHUB_USER/student-management'
        IMAGE_TAG  = "${env.GIT_COMMIT?.take(7) ?: env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Install & Lint') {
            steps {
                sh '''
                  python3 -m venv .venv
                  . .venv/bin/activate
                  pip install -r requirements.txt flake8
                  flake8 app tests --max-line-length=120
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                sh '. .venv/bin/activate && python -m unittest discover -s tests -v'
            }
        }

        stage('Build Image') {
            steps {
                sh "docker build --build-arg APP_VERSION=${IMAGE_TAG} -t ${IMAGE_REPO}:${IMAGE_TAG} -t ${IMAGE_REPO}:latest ."
            }
        }

        stage('Smoke Test') {
            steps {
                sh '''
                  docker rm -f sms-smoke || true
                  docker run -d --name sms-smoke -p 5055:5000 ${IMAGE_REPO}:${IMAGE_TAG}
                  ./scripts/smoke_test.sh http://localhost:5055
                '''
            }
            post { always { sh 'docker rm -f sms-smoke || true' } }
        }

        stage('Push Image') {
            when { branch 'main' }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
                    sh '''
                      echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin
                      docker push ${IMAGE_REPO}:${IMAGE_TAG}
                      docker push ${IMAGE_REPO}:latest
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when { branch 'main' }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh '''
                      sed -i "s|image: ghcr.io/.*|image: ${IMAGE_REPO}:${IMAGE_TAG}|" k8s/deployment.yaml
                      kubectl apply -f k8s/
                      kubectl -n student-mgmt rollout status deployment/sms-app --timeout=120s
                    '''
                }
            }
        }
    }

    post {
        success { echo "Pipeline succeeded: ${IMAGE_REPO}:${IMAGE_TAG}" }
        failure { echo 'Pipeline failed - check the stage logs above.' }
    }
}
