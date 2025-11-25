#!/usr/bin/env python3
"""Post-generation hook to clean up unnecessary files based on configuration."""

import os

# Get configuration values
CREATE_NAMESPACE = "{{ cookiecutter.create_namespace }}"
USE_SECRETS_MANAGER = "{{ cookiecutter.use_secrets_manager }}"

# Remove namespace.yaml if not creating namespace
if CREATE_NAMESPACE == "no":
    namespace_file = "namespace.yaml"
    if os.path.exists(namespace_file):
        os.remove(namespace_file)
        print(f"✓ Removed {namespace_file} (not creating namespace)")

# Print helpful next steps
print("\n" + "=" * 80)
print("🎉 Rossum Agent deployment configuration generated successfully!")
print("=" * 80)

print("\nGenerated files:")
print("  • kustomization.yaml")
if CREATE_NAMESPACE == "yes":
    print("  • namespace.yaml")
print("  • README.md")

print("\n📝 Next steps:")
print("  1. Review and update the generated files (especially API keys!)")
print("  2. Build and load your Docker image")
print("  3. Deploy: kubectl apply -k deployments/{{ cookiecutter.environment_name }}")
print("  4. See README.md for detailed instructions")

if USE_SECRETS_MANAGER == "no":
    print("\n⚠️  WARNING: API keys are in plain text! Never commit to git.")
    print("   Consider using a secrets manager for production deployments.")

print("=" * 80 + "\n")
