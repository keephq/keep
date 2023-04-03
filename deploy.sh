#!/bin/bash
set -ex

docker buildx build --push --platform linux/amd64,linux/arm64 -f Dockerfile.api -t gcr.io/keephq-sandbox/keephq-sandbox .
docker tag keephq-sandbox-amd64 gcr.io/keephq-sandbox/keephq-sandbox
docker push gcr.io/keephq-sandbox/keephq-sandbox

secrets=$(gcloud secrets list --format="value(name)")
update_secrets=$(echo $secrets | awk 'BEGIN { printf "--update-secrets=" } { printf "%s=%s:latest%s",$1,$1,(NR!=3)?",":"" }')

gcloud run deploy keephq-sandbox ${update_secrets} --image gcr.io/keephq-sandbox/keephq-sandbox --region us-central1
