# Local Kubernetes Deployment

This directory contains a ready-to-use template for deploying Rossum Agent locally on Kubernetes.

## Quick Start

### 1. Prerequisites

Install one of the following local Kubernetes distributions:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (easiest)
- [minikube](https://minikube.sigs.k8s.io/)
- [kind](https://kind.sigs.k8s.io/)
- [k3d](https://k3d.io/)

### 2. Build the Docker Image

**For Docker Desktop / kind:**
```bash
cd /Users/daniel.stancl/projects/rossum-agent-combo/rossum-mcp
docker build -t rossum-agent:local .
```

**For kind (additional step to load image):**
```bash
kind load docker-image rossum-agent:local
```

**For minikube:**
```bash
docker build -t rossum-agent:local .
minikube image load rossum-agent:local
```

### 3. Configure LLM API Keys (Optional)

**Note**: Rossum API credentials are entered in the application UI after deployment, not in the deployment configuration.

If you're using LLM providers that require API keys (Anthropic, OpenAI, HuggingFace), edit [kustomization.yaml](kustomization.yaml):

```yaml
secretGenerator:
  - name: rossum-agent
    literals:
      # Remove the DUMMY_SECRET line and add your actual secrets:
      # - ANTHROPIC_API_KEY=your-anthropic-key-here
      # - OPENAI_API_KEY=your-openai-key-here
      # - HF_TOKEN=your-hf-token-here
```

**⚠️ SECURITY NOTE**: For better security, create a separate `secrets.yaml` file (add to `.gitignore`):

```yaml
# Create: deployments/local/secrets.yaml (add to .gitignore!)
apiVersion: v1
kind: Secret
metadata:
  name: rossum-agent
type: Opaque
stringData:
  ANTHROPIC_API_KEY: "your-key"
  # Add other secrets...
```

Then update `kustomization.yaml`:
```yaml
resources:
  - ../base
  - secrets.yaml  # Add this line

# Remove or comment out the secretGenerator section
```

### 4. Deploy

```bash
kubectl apply -k deployments/local
```

### 5. Access the Application

```bash
# Forward port 8501 to localhost
kubectl port-forward service/rossum-agent 8501:8501
```

Open http://localhost:8501 in your browser and enter your Rossum API credentials in the application UI.

## Configuration

### Environment Variables

Customize the `configMapGenerator` section in [kustomization.yaml](kustomization.yaml):

```yaml
configMapGenerator:
  - name: rossum-agent
    behavior: merge
    literals:
      - LLM_MODEL_ID=anthropic/claude-3-5-sonnet-20241022  # Change model
      - BASE_URL=http://localhost:8501
      # Add custom variables:
      # - CUSTOM_VAR=value
```

### Resource Limits

The default local configuration uses reduced resources:
- CPU: 0.25 cores (request) / 0.5 cores (limit)
- Memory: 512Mi (request) / 1Gi (limit)

To adjust, modify the patch in [kustomization.yaml](kustomization.yaml).

### Using .env File (Alternative)

1. Copy the template:
   ```bash
   cp .env.template .env
   ```

2. Edit `.env` with your actual values

3. Generate secrets from `.env`:
   ```bash
   kubectl create secret generic rossum-agent \
     --from-env-file=.env \
     --dry-run=client -o yaml > secrets.yaml
   ```

4. Add `secrets.yaml` to resources in `kustomization.yaml`

5. **Important**: Add `.env` and `secrets.yaml` to `.gitignore`!

## Useful Commands

### View Logs
```bash
kubectl logs -l app=rossum-agent -f
```

### Check Pod Status
```bash
kubectl get pods -l app=rossum-agent
```

### Describe Deployment
```bash
kubectl describe deployment rossum-agent
```

### View ConfigMap
```bash
kubectl get configmap rossum-agent -o yaml
```

### Restart Deployment (after config changes)
```bash
kubectl rollout restart deployment rossum-agent
```

### Delete Deployment
```bash
kubectl delete -k deployments/local
```

## Troubleshooting

### Pod won't start (ImagePullBackOff)
```bash
# Check if image exists
docker images | grep rossum-agent

# For kind, reload the image
kind load docker-image rossum-agent:local

# For minikube, reload the image
minikube image load rossum-agent:local
```

### Pod crashes (CrashLoopBackOff)
```bash
# Check logs for errors
kubectl logs -l app=rossum-agent --tail=100

# Check if secrets are set correctly
kubectl get secret rossum-agent -o yaml
```

### Can't connect to localhost:8501
```bash
# Make sure port-forward is running
kubectl port-forward service/rossum-agent 8501:8501

# Check if service is running
kubectl get svc rossum-agent
```

## Development Workflow

1. Make code changes
2. Rebuild Docker image:
   ```bash
   docker build -t rossum-agent:local .
   # For kind:
   kind load docker-image rossum-agent:local
   # For minikube:
   minikube image load rossum-agent:local
   ```
3. Restart deployment:
   ```bash
   kubectl rollout restart deployment rossum-agent
   ```
4. Watch logs:
   ```bash
   kubectl logs -l app=rossum-agent -f
   ```

## Clean Up

```bash
# Delete the deployment
kubectl delete -k deployments/local

# For kind, delete the cluster
kind delete cluster

# For minikube, stop the cluster
minikube stop
```
