# Rossum Agent Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the Rossum Agent application using Kustomize.

## 🚀 Quick Start (Recommended)

**Use the cookiecutter template to generate deployment configurations for any environment in seconds!**

```bash
# Install cookiecutter
uv tool install cookiecutter

# Generate a new environment configuration (interactive)
cd deployments
cookiecutter new-deployment

# Deploy
kubectl apply -k deployments/<your-environment-name>
```

See [new-deployment/README.md](new-deployment/README.md) for full documentation.

## Directory Structure

```
deployments/
├── new-deployment/         # 🎯 Template for generating any environment
│   ├── cookiecutter.json
│   ├── {{cookiecutter.environment_name}}/
│   └── README.md
├── base/                   # Base Kubernetes resources
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── service-account.yaml
│   ├── externalsecret.yaml
│   └── kustomization.yaml
├── _shared/                # Shared component with common labels
│   └── kustomization.yaml
├── local/                  # Pre-configured local development
│   └── kustomization.yaml
├── dev-eu/                 # Environment-specific overlays
│   └── tools-rossum-agent/
└── README.md
```

## Prerequisites

- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [kustomize](https://kustomize.io/) (or use `kubectl` with `-k` flag)
- [cookiecutter](https://github.com/cookiecutter/cookiecutter) (recommended for new deployments)
- Local Kubernetes cluster (choose one):
  - [minikube](https://minikube.sigs.k8s.io/)
  - [kind](https://kind.sigs.k8s.io/)
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - [k3d](https://k3d.io/)

## Configuration Variables

The deployment uses the following variables that need to be configured:

### Required Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `image_tag` | Docker image tag for the application | `not_set` | `v1.0.0` |
| `aws_account_id` | AWS Account ID for IAM role ARN | - | `123456789012` |
| `aws_region` | AWS region for services | - | `eu-west-1` |
| `cluster_name` | Name of the Kubernetes cluster | - | `dev-cluster` |
| `tools_base_domain` | Base domain for ingress | - | `tools.example.com` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_MODEL_ID` | Language model identifier | `bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `BASE_URL` | Base URL for the application | - |

## Deployment Methods

### Method 1: Cookiecutter Template (⭐ Recommended)

**Best for:** Any environment (local, dev, staging, production)

Generate a custom configuration interactively:
```bash
cd deployments
cookiecutter new-deployment
```

Or use a config file for automation:
```bash
cookiecutter new-deployment --no-input --config-file my-config.yaml
```

**Benefits:**
- ✅ Supports all environments and namespaces
- ✅ Secrets management options
- ✅ Ingress and TLS configuration
- ✅ Resource customization
- ✅ Generates environment-specific README

See [new-deployment/README.md](new-deployment/README.md) for detailed documentation.

### Method 2: Pre-configured Local Deployment

**Best for:** Quick local testing with minimal configuration

1. Edit [local/kustomization.yaml](local/kustomization.yaml) with your API key
2. Deploy using published image (recommended):
   ```bash
   kubectl apply -k deployments/local
   kubectl port-forward service/rossum-agent 8501:8501
   ```

   Or build locally first:
   ```bash
   docker build -t rossum-agent:local .
   kubectl apply -k deployments/local
   kubectl port-forward service/rossum-agent 8501:8501
   ```

### Method 3: Manual Kustomize Overlays

**Best for:** Advanced users who need full control

Create your own overlay in a new directory following the structure of existing environments.

## Local Deployment

> **Note:** Local Kubernetes deployment (minikube, kind, k3d) is complex when connecting to AWS Bedrock. For local development, we recommend using Docker Compose instead. See the [main README](../README.md) for Docker Compose setup instructions.

### Example: Using kind (Non-Working Example for Reference)

This is kept as a reference example only. The configuration is complex due to AWS Bedrock credential management. For actual local development, use Docker Compose.

1. **Create a cluster**:
   ```bash
   kind create cluster --name rossum-agent
   ```

2. **Configure AWS credentials** - This is the complex part that makes local K8s deployment impractical

3. **Deploy** (reference only):
   ```bash
   kubectl apply -k deployments/local
   kubectl port-forward service/rossum-agent 8501:8501
   ```

## AWS Logging Configuration

The application logs to AWS CloudWatch when deployed in AWS EKS. The logging is configured through:

1. **Service Account**: Annotated with IAM role ARN in [service-account.yaml](base/service-account.yaml)
   ```yaml
   annotations:
     eks.amazonaws.com/role-arn: arn:aws:iam::${aws_account_id}:role/app-${cluster_name}-tools-rossum-agent
   ```

2. **IAM Role Permissions**: The IAM role should have the following permissions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "logs:CreateLogGroup",
           "logs:CreateLogStream",
           "logs:PutLogEvents",
           "logs:DescribeLogStreams"
         ],
         "Resource": "arn:aws:logs:${aws_region}:${aws_account_id}:log-group:/aws/eks/${cluster_name}/rossum-agent*"
       }
     ]
   }
   ```

3. **Application Configuration**: The app uses environment variables:
   - `AWS_REGION` - Set via ConfigMap
   - `REGION_NAME` - Set via ConfigMap
   - AWS credentials - Obtained via IRSA (IAM Roles for Service Accounts)

For local development, logging goes to stdout/stderr and can be viewed with:
```bash
kubectl logs -l app=rossum-agent -f
```

## Deployment to AWS EKS

1. **Set up environment-specific variables**:
   Create a new overlay directory (e.g., `deployments/prod-us/tools-rossum-agent/kustomization.yaml`):
   ```yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization

   resources:
     - ../../base

   components:
     - ../../_shared

   configMapGenerator:
     - name: rossum-agent
       behavior: merge
       literals:
         - LLM_MODEL_ID=bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0
         - BASE_URL=https://rossum-agent.tools.example.com

   images:
     - name: app-image
       newName: ${ECR_REGISTRY}/rossum-agent
       newTag: ${IMAGE_TAG}

   # Set cluster-specific variables
   replacements:
     - source:
         kind: ConfigMap
         fieldPath: data.aws_account_id
       targets:
         - select:
             kind: ServiceAccount
           fieldPaths:
             - metadata.annotations.[eks.amazonaws.com/role-arn]
   ```

2. **Deploy**:
   ```bash
   kubectl apply -k deployments/prod-us/tools-rossum-agent
   ```

## Secrets Management

### AWS EKS (Production)

Secrets are managed via [External Secrets Operator](https://external-secrets.io/) with Vault backend:
- See [externalsecret.yaml](base/externalsecret.yaml)
- Secrets are synced from Vault path: `tools-rossum-agent/rossum-agent`

**Note**: `ROSSUM_API_TOKEN` and `ROSSUM_API_BASE_URL` are entered in the application UI, not stored in deployment secrets.

Required secrets (for LLM providers):
- `ANTHROPIC_API_KEY` - Anthropic API key (if using Anthropic directly)
- `OPENAI_API_KEY` - OpenAI API key (if using OpenAI models)
- `HF_TOKEN` - HuggingFace token (if using HF models)
- Additional model-specific credentials as needed

### Local Development

Use Kubernetes secrets directly. See the [local deployment template](local/README.md) for details.

## Customization

### Resource Limits

Modify [deployment.yaml](base/deployment.yaml) to adjust CPU/memory:
```yaml
resources:
  limits:
    cpu: 1
    memory: 2Gi
  requests:
    cpu: 0.5
    memory: 2Gi
```

### Replicas

Adjust the replica count in your overlay:
```yaml
patches:
  - patch: |-
      - op: replace
        path: /spec/replicas
        value: 3
    target:
      kind: Deployment
      name: rossum-agent
```

## Troubleshooting

### Check pod status
```bash
kubectl get pods -l app=rossum-agent
```

### View logs
```bash
kubectl logs -l app=rossum-agent -f
```

### Describe deployment
```bash
kubectl describe deployment rossum-agent
```

### Check ConfigMap
```bash
kubectl get configmap rossum-agent -o yaml
```

### Check secrets (redacted)
```bash
kubectl get secret rossum-agent -o yaml
```

## Monitoring

When deployed to AWS EKS:
- **CloudWatch Logs**: Application logs are sent to CloudWatch Logs group `/aws/eks/${cluster_name}/rossum-agent`
- **CloudWatch Metrics**: Container metrics via Container Insights (if enabled)
- **Kubernetes Events**: `kubectl get events --sort-by='.lastTimestamp'`

## Clean Up

### Local deployment
```bash
kubectl delete -k deployments/local
```

### AWS EKS deployment
```bash
kubectl delete -k deployments/dev-eu/tools-rossum-agent
```

### Delete local cluster (kind)
```bash
kind delete cluster --name rossum-agent
```

### Stop minikube
```bash
minikube stop
```
