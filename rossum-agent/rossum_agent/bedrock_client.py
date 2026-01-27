"""AWS Bedrock client module for direct communication with Anthropic models via boto3.Session."""

from __future__ import annotations

import os

import boto3
from anthropic import AnthropicBedrock

OPUS_MODEL_ID = "eu.anthropic.claude-opus-4-5-20251101-v1:0"
HAIKU_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"


def create_bedrock_client(
    aws_region: str | None = None, aws_profile: str | None = None, session: boto3.Session | None = None
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
        max_retries=5,
    )


def get_model_id() -> str:
    """Return AWS_BEDROCK_MODEL_ARN if set, otherwise default Opus model."""
    return os.environ.get("AWS_BEDROCK_MODEL_ARN", OPUS_MODEL_ID)


def get_small_model_id() -> str:
    """Return AWS_BEDROCK_MODEL_ARN_SMALL if set, otherwise default Haiku model."""
    return os.environ.get("AWS_BEDROCK_MODEL_ARN_SMALL", HAIKU_MODEL_ID)
