"""AWS Bedrock client module for direct communication with Anthropic models via boto3.Session."""

from __future__ import annotations

import os
from typing import TypedDict

import boto3
from anthropic import AnthropicBedrock


class STSCredentials(TypedDict, total=False):
    """TypedDict representing STS credentials from assume_role response."""

    AccessKeyId: str
    SecretAccessKey: str
    SessionToken: str


DEFAULT_MODEL_ID = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"


def create_bedrock_client(
    aws_region: str | None = None,
    aws_profile: str | None = None,
    session: boto3.Session | None = None,
) -> AnthropicBedrock:
    """Create AnthropicBedrock client using boto3.Session credentials.

    This function supports multiple credential sources:
    1. Explicit boto3.Session passed as argument
    2. AWS profile name (uses named profile from ~/.aws/credentials)
    3. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
    4. IAM role credentials (when running on AWS infrastructure)

    Args:
        aws_region: AWS region for Bedrock service. Defaults to AWS_REGION env var
            or 'eu-central-1'.
        aws_profile: AWS profile name from ~/.aws/credentials. Overridden if session
            is provided.
        session: Pre-configured boto3.Session. If provided, aws_profile is ignored.

    Returns:
        Configured AnthropicBedrock client ready for API calls.
    """
    region = aws_region or os.environ.get("AWS_REGION")

    if session is None:
        session = boto3.Session(profile_name=aws_profile, region_name=region)

    if (credentials := session.get_credentials()) is None:
        raise RuntimeError(
            "No AWS credentials found. Please configure AWS credentials via environment "
            "variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY), AWS profile, or IAM role."
        )

    frozen_credentials = credentials.get_frozen_credentials()

    return AnthropicBedrock(
        aws_access_key=frozen_credentials.access_key,
        aws_secret_key=frozen_credentials.secret_key,
        aws_session_token=frozen_credentials.token,
        aws_region=session.region_name or region,
    )


def create_bedrock_client_from_sts_credentials(
    credentials: STSCredentials, aws_region: str | None = None
) -> AnthropicBedrock:
    """Create AnthropicBedrock client from STS assumed role credentials.

    This is useful when assuming a role via STS and passing the temporary
    credentials directly.

    Args:
        credentials: STS credentials dictionary containing AccessKeyId, SecretAccessKey,
            and SessionToken.
        aws_region: AWS region for Bedrock service. Defaults to AWS_REGION

    Returns:
        Configured AnthropicBedrock client ready for API calls.

    """
    return AnthropicBedrock(
        aws_access_key=credentials["AccessKeyId"],
        aws_secret_key=credentials["SecretAccessKey"],
        aws_session_token=credentials.get("SessionToken"),
        aws_region=aws_region,
    )


def get_model_id() -> str:
    """Get the Bedrock model ID from environment or return default.

    The model ID can be configured via:
    - LLM_MODEL_ID environment variable (without 'bedrock/' prefix)
    - AWS_BEDROCK_MODEL_ARN for cross-account model access

    Returns:
        Model ID string suitable for AnthropicBedrock client.
    """
    if model_arn := os.environ.get("AWS_BEDROCK_MODEL_ARN"):
        return model_arn

    model_id = os.environ.get("LLM_MODEL_ID", f"bedrock/{DEFAULT_MODEL_ID}")
    if model_id.startswith("bedrock/"):
        model_id = model_id[len("bedrock/") :]

    return model_id
