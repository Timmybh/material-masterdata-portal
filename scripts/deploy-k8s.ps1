$ErrorActionPreference='Stop'
kubectl apply -f ./k8s/secret.yaml
kubectl apply -f ./k8s/postgres.yaml
kubectl rollout status deployment/postgres
kubectl apply -f ./k8s/app.yaml
kubectl rollout status deployment/masterdata-backend
kubectl rollout status deployment/masterdata-frontend
kubectl get svc masterdata-frontend
