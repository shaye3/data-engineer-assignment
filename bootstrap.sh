#!/usr/bin/env bash
set -euo pipefail

echo "==> Starting minikube"
minikube start --memory=4096 --cpus=4

echo "==> Installing KEDA"
kubectl apply --server-side --force-conflicts -f https://github.com/kedacore/keda/releases/download/v2.13.1/keda-2.13.1.yaml
kubectl wait --for=condition=ready pod -l app=keda-operator -n keda --timeout=120s

echo "==> Creating namespace and PVC"
kubectl apply -f generator/k8s/namespace.yaml
kubectl apply -f generator/k8s/pvc.yaml

echo "==> Building generator image"
eval "$(minikube docker-env)"
docker build -t sensor-pipeline/generator:latest generator/

echo "==> Deploying generator"
kubectl apply -f generator/k8s/deployment.yaml
kubectl rollout status deployment/generator -n sensor-pipeline --timeout=60s

echo ""
echo "Bootstrap complete. Generator is running."
echo "Files are landing on input-pvc inside the cluster."
echo ""
echo "To stop the generator:  kubectl scale deployment generator -n sensor-pipeline --replicas=0"
echo "To start the generator: kubectl scale deployment generator -n sensor-pipeline --replicas=1"
echo ""
echo "To verify your pipeline:"
echo "  1. Copy files locally: kubectl cp sensor-pipeline/\$(kubectl get pod -n sensor-pipeline -l app=generator -o jsonpath='{.items[0].metadata.name}'):/input ./input"
echo "  2. Run: python verify.py --input-dir ./input --output-dir ./output"
