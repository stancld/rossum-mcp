# Rossum Agent - dev-eu Environment

> **Note:** This is an example deployment generated with the cookiecutter template.

**Deployment Type:** `aws-eks`
**Namespace:** `tools-rossum-agent`
**LLM Provider:** `bedrock`

## Quick Start

### 1. Use Docker Image

**Option A: GitHub Container Registry (Recommended)**
The deployment uses `ghcr.io/stancld/rossum-mcp:master` by default.
- Image is automatically built and published by CI on every push to master
- Available tags: `master`, `v*`, `sha-*`

**Option B: Build and Push to ECR (Custom Builds)**
```bash
# Build and push to ECR
aws ecr get-login-password --region eu-west-1 | \
  docker login --username AWS --password-stdin .dkr.ecr.eu-west-1.amazonaws.com

docker build -t /rossum-agent:latest .
docker push /rossum-agent:latest
```

Then update the image in kustomization.yaml accordingly.

### 2. Deploy to Kubernetes

```bash
kubectl apply -k deployments/dev-eu
```

### 3. Verify Deployment

```bash
kubectl get pods -n tools-rossum-agent -l app=rossum-agent
kubectl logs -n tools-rossum-agent -l app=rossum-agent -f
```

### 4. Access the Application

The application is available at: https://rossum-agent.tools.r8.lol
**Note:** TLS is enabled. Ensure your certificate is properly configured.

## Configuration

### Environment Variables

Configuration is managed via ConfigMap and Secrets in the kustomization.yaml file.

### Secrets Management

Secrets are managed via External Secrets Operator.

Configure your secrets in your Vault/AWS Secrets Manager/etc. at:
- Path: `tools-rossum-agent-rossum-agent/rossum-agent`

### Resource Configuration

Current settings:
- **Replicas:** 1
- **CPU Request:** 0.5
- **Memory Request:** 2Gi
- **CPU Limit:** 1
- **Memory Limit:** 2Gi

To adjust, edit the resource patches in kustomization.yaml.

## Troubleshooting

### Check pod status
```bash
kubectl get pods -n tools-rossum-agent -l app=rossum-agent
```

### View logs
```bash
kubectl logs -n tools-rossum-agent -l app=rossum-agent -f
```

### Describe deployment
```bash
kubectl describe deployment -n tools-rossum-agent rossum-agent
```

### Check events
```bash
kubectl get events -n tools-rossum-agent --sort-by='.lastTimestamp'
```

## Cleanup

```bash
kubectl delete -k deployments/dev-eu
kubectl delete namespace tools-rossum-agent
```

## Next Steps

1. **Configure Rossum API:** Open the app UI and enter your Rossum API credentials
2. **Test the agent:** Try uploading a document and testing the AI capabilities
3. **Monitor logs:** Keep an eye on the logs for any issues
4. **Set up monitoring:** Configure CloudWatch dashboards for production monitoring
