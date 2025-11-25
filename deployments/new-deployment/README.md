# Rossum Agent Deployment Template (Cookiecutter)

This is a [cookiecutter](https://github.com/cookiecutter/cookiecutter) template for generating Rossum Agent Kubernetes deployment configurations for **any environment** (local, dev, staging, production, etc.).

## Features

✅ **Multi-environment support:** local, AWS EKS, or generic Kubernetes
✅ **Namespace management:** Create or use existing namespaces
✅ **LLM provider flexibility:** Anthropic, OpenAI, HuggingFace, or AWS Bedrock
✅ **Secrets management:** Local secrets, External Secrets Operator, or AWS Secrets Manager
✅ **Ingress configuration:** Optional with TLS support
✅ **Resource customization:** Adjust CPU, memory, and replicas per environment
✅ **Automated setup:** Interactive prompts guide you through configuration

## Prerequisites

```bash
uv tool install cookiecutter
```

## Quick Start

### Option 1: Interactive Mode (Recommended)

```bash
cd deployments
cookiecutter cookiecutter-template
```

You'll be prompted for:
- Environment name (e.g., `local`, `dev-us`, `prod-eu`)
- Namespace
- Deployment type (local, AWS EKS, generic K8s)
- LLM provider and model
- Docker image settings
- Resource limits
- And more...

### Option 2: Non-Interactive Mode

Create a config file `my-env-config.yaml`:
```yaml
environment_name: "staging-eu"
namespace: "rossum-agent-staging"
create_namespace: "yes"
deployment_type: "aws-eks"
llm_provider: "anthropic"
llm_model_id: "anthropic/claude-3-5-sonnet-20241022"
use_secrets_manager: "external-secrets"
docker_registry: "123456789.dkr.ecr.eu-west-1.amazonaws.com"
docker_image_name: "rossum-agent"
docker_image_tag: "v1.2.3"
base_url: "https://rossum-agent-staging.example.com"
use_ingress: "yes"
ingress_host: "rossum-agent-staging.example.com"
ingress_tls: "yes"
aws_region: "eu-west-1"
aws_account_id: "123456789"
cluster_name: "staging-cluster"
cpu_request: "1"
memory_request: "4Gi"
cpu_limit: "2"
memory_limit: "8Gi"
replicas: "2"
```

Then generate:
```bash
cd deployments
cookiecutter cookiecutter-template --no-input --config-file my-env-config.yaml
```

## Configuration Options

### Environment Settings

| Option | Description | Example Values |
|--------|-------------|----------------|
| `environment_name` | Name of the environment | `local`, `dev-us`, `prod-eu` |
| `namespace` | Kubernetes namespace | `default`, `rossum-agent-dev` |
| `create_namespace` | Create namespace.yaml | `yes`, `no` |

### Deployment Type

| Option | Description | When to Use |
|--------|-------------|-------------|
| `local` | Local K8s (minikube, kind, Docker Desktop) | Development on laptop |
| `aws-eks` | AWS Elastic Kubernetes Service | Production on AWS |
| `generic-k8s` | Any other Kubernetes cluster | GKE, AKS, on-prem, etc. |

### LLM Provider

| Provider | Model Example | Required Secret |
|----------|---------------|-----------------|
| `anthropic` | `anthropic/claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` |
| `openai` | `openai/gpt-4o` | `OPENAI_API_KEY` |
| `huggingface` | `huggingface/meta-llama/Llama-3-70b-chat-hf` | `HF_TOKEN` |
| `bedrock` | `bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0` | AWS IAM (no key) |

### Secrets Management

| Option | Description | Best For |
|--------|-------------|----------|
| `no` | Store secrets in kustomization.yaml | Local development only |
| `external-secrets` | External Secrets Operator | Production with Vault/etc. |
| `aws-secrets` | AWS Secrets Manager | AWS EKS production |

### Ingress

| Setting | Description |
|---------|-------------|
| `use_ingress: no` | Use `kubectl port-forward` (local dev) |
| `use_ingress: yes` | Configure Ingress with hostname |
| `ingress_tls: yes` | Enable TLS/HTTPS |

## Example Scenarios

### Scenario 1: Local Development

```bash
cookiecutter cookiecutter-template \
  environment_name=local \
  namespace=default \
  deployment_type=local \
  llm_provider=anthropic \
  api_key=sk-ant-your-key \
  docker_image_tag=local \
  use_ingress=no \
  cpu_request=0.25 \
  memory_request=512Mi
```

### Scenario 2: AWS Development Environment

```bash
cookiecutter cookiecutter-template \
  environment_name=dev-us \
  namespace=rossum-agent-dev \
  create_namespace=yes \
  deployment_type=aws-eks \
  llm_provider=bedrock \
  use_secrets_manager=external-secrets \
  docker_registry=123456789.dkr.ecr.us-east-1.amazonaws.com \
  docker_image_tag=dev-latest \
  use_ingress=yes \
  ingress_host=rossum-agent-dev.tools.example.com \
  aws_region=us-east-1 \
  aws_account_id=123456789 \
  cluster_name=dev-cluster
```

### Scenario 3: Production with High Availability

```bash
cookiecutter cookiecutter-template \
  environment_name=prod-eu \
  namespace=rossum-agent-prod \
  deployment_type=aws-eks \
  use_secrets_manager=external-secrets \
  replicas=3 \
  cpu_request=2 \
  memory_request=8Gi \
  cpu_limit=4 \
  memory_limit=16Gi \
  use_ingress=yes \
  ingress_tls=yes
```

## After Generation

1. **Review generated files** in `deployments/<environment_name>/`
2. **Update API keys** if using local secrets
3. **Build Docker image:**
   ```bash
   docker build -t <image-name>:<tag> .
   ```
4. **Deploy:**
   ```bash
   kubectl apply -k deployments/<environment_name>
   ```
5. **Follow environment-specific README** for detailed instructions

## Directory Structure After Generation

```
deployments/
├── cookiecutter-template/     # This template
├── base/                      # Base K8s resources (shared)
├── _shared/                   # Common labels
└── <environment_name>/        # Your generated environment
    ├── kustomization.yaml     # Main config
    ├── namespace.yaml         # (optional) Namespace definition
    └── README.md              # Environment-specific docs
```

## Tips

💡 **API Key Security:** For local dev only! Production should use proper secrets management.
💡 **Multiple Environments:** Run cookiecutter multiple times for dev, staging, prod, etc.
💡 **Version Control:** Generated configs can be committed (except those with plain-text secrets).
💡 **Customization:** Generated files can be manually edited after creation.
💡 **Re-generation:** Delete old environment and regenerate if you need to change settings.

## Troubleshooting

**Q: I made a mistake in configuration. Can I regenerate?**
A: Yes! Delete the generated directory and run cookiecutter again.

**Q: Can I use a different base path?**
A: Yes, the template references `../base` and `../_shared` which work from `deployments/<env>/`.

**Q: How do I add custom patches?**
A: Edit the generated `kustomization.yaml` and add your patches to the `patches:` section.

**Q: Can I use this with GitOps (ArgoCD/Flux)?**
A: Absolutely! Commit the generated configs to git and point your GitOps tool to them.

## Support

See the main [deployment README](../README.md) for general Kubernetes deployment documentation.
