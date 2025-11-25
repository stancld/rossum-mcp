# Local Kubernetes Deployment (Non-Working Example)

> **⚠️ IMPORTANT:** This configuration is kept as a reference example only. Local Kubernetes deployment is overly complex when connecting to AWS Bedrock due to credential management challenges. **For local development, use Docker Compose instead** - see the [main README](../../README.md#-docker-compose-local).

This directory shows how a local Kubernetes deployment would be configured, but is not recommended for actual use.

## Why Not Use This?

Connecting to AWS Bedrock from local Kubernetes requires:
- Manually obtaining temporary AWS credentials via `aws sts assume-role`
- Updating `kustomization.yaml` with these credentials
- Credentials expire after a few hours, requiring manual renewal
- Complex debugging when credentials fail

**Docker Compose is simpler:** Just mount your `~/.aws` directory and it works automatically.

## Reference Configuration (If You Really Want To Try)

### 1. Prerequisites

Install one of the following local Kubernetes distributions:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [kind](https://kind.sigs.k8s.io/)
- [k3d](https://k3d.io/)

**Get temporary AWS credentials:**
```bash
aws sts assume-role \
  --role-arn arn:aws:iam::494114742120:role/app-dev-eu-tools-rossum-agent \
  --role-session-name local-dev
```

Copy the `AccessKeyId`, `SecretAccessKey`, and `SessionToken` from the output and paste them into [kustomization.yaml](kustomization.yaml) under `secretGenerator`.

### 2. Build or Pull Image

The deployment uses `ghcr.io/stancld/rossum-mcp:master` by default (automatically pulled).

For local development:
```bash
docker build -t rossum-agent:local .
# For kind: kind load docker-image rossum-agent:local
# For k3d: k3d image import rossum-agent:local
```

### 3. Configure Secrets

**Note**: Rossum API credentials are entered in the application UI after deployment, not in the deployment configuration.

**AWS Bedrock**: Update the secretGenerator in [kustomization.yaml](kustomization.yaml) with the credentials from step 1:

```yaml
secretGenerator:
  - name: rossum-agent
    literals:
      - AWS_ACCESS_KEY_ID=ASIA...  # From assume-role output
      - AWS_SECRET_ACCESS_KEY=wJa...  # From assume-role output
      - AWS_SESSION_TOKEN=IQo...  # From assume-role output
```

If you're using other LLM providers that require API keys (Anthropic, OpenAI, HuggingFace), add them to [kustomization.yaml](kustomization.yaml):

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

Common issues when using this configuration (reminder: use Docker Compose instead):

### AWS Credentials Expired
```bash
# Re-run assume-role and update kustomization.yaml
aws sts assume-role \
  --role-arn arn:aws:iam::494114742120:role/app-dev-eu-tools-rossum-agent \
  --role-session-name local-dev
```

### Pod won't start
```bash
kubectl logs -l app=rossum-agent --tail=100
kubectl describe pod -l app=rossum-agent
```

## Clean Up

```bash
kubectl delete -k deployments/local
kind delete cluster  # if using kind
```
