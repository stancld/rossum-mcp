# Rossum Agent - {{ cookiecutter.environment_name }} Environment

**Deployment Type:** `{{ cookiecutter.deployment_type }}`
**Namespace:** `{{ cookiecutter.namespace }}`
**LLM Provider:** `bedrock`

## Quick Start

### 1. Build and Load Docker Image

{%- if cookiecutter.deployment_type == "local" %}

#### For minikube:
```bash
eval $(minikube docker-env)
docker build -t {{ cookiecutter.docker_image_name }}:{{ cookiecutter.docker_image_tag }} .
```

#### For kind:
```bash
docker build -t {{ cookiecutter.docker_image_name }}:{{ cookiecutter.docker_image_tag }} .
kind load docker-image {{ cookiecutter.docker_image_name }}:{{ cookiecutter.docker_image_tag }}
```

#### For Docker Desktop:
```bash
docker build -t {{ cookiecutter.docker_image_name }}:{{ cookiecutter.docker_image_tag }} .
```
{%- elif cookiecutter.deployment_type == "aws-eks" %}

```bash
# Build and push to ECR
aws ecr get-login-password --region {{ cookiecutter.aws_region }} | \
  docker login --username AWS --password-stdin {{ cookiecutter.aws_account_id }}.dkr.ecr.{{ cookiecutter.aws_region }}.amazonaws.com

docker build -t {{ cookiecutter.docker_registry }}/{{ cookiecutter.docker_image_name }}:{{ cookiecutter.docker_image_tag }} .
docker push {{ cookiecutter.docker_registry }}/{{ cookiecutter.docker_image_name }}:{{ cookiecutter.docker_image_tag }}
```
{%- else %}

```bash
docker build -t {% if cookiecutter.docker_registry %}{{ cookiecutter.docker_registry }}/{% endif %}{{ cookiecutter.docker_image_name }}:{{ cookiecutter.docker_image_tag }} .
{% if cookiecutter.docker_registry %}docker push {{ cookiecutter.docker_registry }}/{{ cookiecutter.docker_image_name }}:{{ cookiecutter.docker_image_tag }}{% endif %}
```
{%- endif %}

### 2. Deploy to Kubernetes

```bash
kubectl apply -k deployments/{{ cookiecutter.environment_name }}
```

### 3. Verify Deployment

```bash
kubectl get pods -n {{ cookiecutter.namespace }} -l app=rossum-agent
kubectl logs -n {{ cookiecutter.namespace }} -l app=rossum-agent -f
```

### 4. Access the Application

{%- if cookiecutter.use_ingress == "yes" %}

The application is available at: {{ cookiecutter.base_url }}

{%- if cookiecutter.ingress_tls == "yes" %}
**Note:** TLS is enabled. Ensure your certificate is properly configured.
{%- endif %}
{%- else %}

Use port-forwarding to access locally:
```bash
kubectl port-forward -n {{ cookiecutter.namespace }} service/rossum-agent 8501:8501
```

Then open: {{ cookiecutter.base_url }}
{%- endif %}

## Configuration

### Environment Variables

Configuration is managed via ConfigMap and Secrets in the kustomization.yaml file.

{%- if cookiecutter.use_secrets_manager == "no" %}

### Authentication

Current configuration:
- **LLM Provider:** bedrock
- **Auth:** Uses AWS IAM credentials (no API key needed)
{%- elif cookiecutter.use_secrets_manager == "external-secrets" %}

### Secrets Management

Secrets are managed via External Secrets Operator.

Configure your secrets in your Vault/AWS Secrets Manager/etc. at:
- Path: `{{ cookiecutter.namespace }}-rossum-agent/rossum-agent`
{%- elif cookiecutter.use_secrets_manager == "aws-secrets" %}

### Secrets Management

Secrets are managed via AWS Secrets Manager.

Create a secret in AWS Secrets Manager:
```bash
aws secretsmanager create-secret \
  --name {{ cookiecutter.namespace }}/rossum-agent \
  --secret-string '{"ANTHROPIC_API_KEY":"your-key-here"}' \
  --region {{ cookiecutter.aws_region }}
```
{%- endif %}

### Resource Configuration

Current settings:
- **Replicas:** {{ cookiecutter.replicas }}
- **CPU Request:** {{ cookiecutter.cpu_request }}
- **Memory Request:** {{ cookiecutter.memory_request }}
- **CPU Limit:** {{ cookiecutter.cpu_limit }}
- **Memory Limit:** {{ cookiecutter.memory_limit }}

To adjust, edit the resource patches in kustomization.yaml.

## Troubleshooting

### Check pod status
```bash
kubectl get pods -n {{ cookiecutter.namespace }} -l app=rossum-agent
```

### View logs
```bash
kubectl logs -n {{ cookiecutter.namespace }} -l app=rossum-agent -f
```

### Describe deployment
```bash
kubectl describe deployment -n {{ cookiecutter.namespace }} rossum-agent
```

### Check events
```bash
kubectl get events -n {{ cookiecutter.namespace }} --sort-by='.lastTimestamp'
```

## Cleanup

```bash
kubectl delete -k deployments/{{ cookiecutter.environment_name }}
{%- if cookiecutter.create_namespace == "yes" %}
kubectl delete namespace {{ cookiecutter.namespace }}
{%- endif %}
```

## Next Steps

1. **Configure Rossum API:** Open the app UI and enter your Rossum API credentials
2. **Test the agent:** Try uploading a document and testing the AI capabilities
3. **Monitor logs:** Keep an eye on the logs for any issues
{%- if cookiecutter.deployment_type == "aws-eks" %}
4. **Set up monitoring:** Configure CloudWatch dashboards for production monitoring
{%- endif %}
