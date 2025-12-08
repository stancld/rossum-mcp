"""Tests for rossum_agent.bedrock_client module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.bedrock_client import (
    DEFAULT_MODEL_ID,
    create_bedrock_client,
    create_bedrock_client_from_sts_credentials,
    get_model_id,
)


class TestCreateBedrockClient:
    """Test create_bedrock_client function."""

    def test_creates_client_with_explicit_session(self):
        """Test creating client with explicitly provided boto3.Session."""
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test_access_key"
        mock_credentials.secret_key = "test_secret_key"
        mock_credentials.token = "test_token"

        mock_frozen_credentials = MagicMock()
        mock_frozen_credentials.access_key = "test_access_key"
        mock_frozen_credentials.secret_key = "test_secret_key"
        mock_frozen_credentials.token = "test_token"
        mock_credentials.get_frozen_credentials.return_value = mock_frozen_credentials

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = mock_credentials
        mock_session.region_name = "us-west-2"

        with patch("rossum_agent.bedrock_client.AnthropicBedrock") as mock_anthropic:
            create_bedrock_client(session=mock_session)

            mock_anthropic.assert_called_once_with(
                aws_access_key="test_access_key",
                aws_secret_key="test_secret_key",
                aws_session_token="test_token",
                aws_region="us-west-2",
            )

    def test_creates_client_with_profile_name(self):
        """Test creating client with AWS profile name."""
        mock_credentials = MagicMock()
        mock_frozen_credentials = MagicMock()
        mock_frozen_credentials.access_key = "profile_access_key"
        mock_frozen_credentials.secret_key = "profile_secret_key"
        mock_frozen_credentials.token = None
        mock_credentials.get_frozen_credentials.return_value = mock_frozen_credentials

        with (
            patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class,
            patch("rossum_agent.bedrock_client.AnthropicBedrock") as mock_anthropic,
        ):
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_session.region_name = "eu-central-1"
            mock_session_class.return_value = mock_session

            create_bedrock_client(aws_profile="my-profile", aws_region="eu-central-1")

            mock_session_class.assert_called_once_with(
                profile_name="my-profile",
                region_name="eu-central-1",
            )
            mock_anthropic.assert_called_once()

    def test_uses_default_region_from_environment(self):
        """Test that AWS_REGION environment variable is used as default."""
        mock_credentials = MagicMock()
        mock_frozen_credentials = MagicMock()
        mock_frozen_credentials.access_key = "key"
        mock_frozen_credentials.secret_key = "secret"
        mock_frozen_credentials.token = None
        mock_credentials.get_frozen_credentials.return_value = mock_frozen_credentials

        with (
            patch.dict(os.environ, {"AWS_REGION": "ap-southeast-1"}),
            patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class,
            patch("rossum_agent.bedrock_client.AnthropicBedrock"),
        ):
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_session.region_name = "ap-southeast-1"
            mock_session_class.return_value = mock_session

            create_bedrock_client()

            mock_session_class.assert_called_once_with(
                profile_name=None,
                region_name="ap-southeast-1",
            )

    def test_uses_none_region_when_no_env_var(self):
        """Test that None is passed to boto3.Session when AWS_REGION is not set."""
        mock_credentials = MagicMock()
        mock_frozen_credentials = MagicMock()
        mock_frozen_credentials.access_key = "key"
        mock_frozen_credentials.secret_key = "secret"
        mock_frozen_credentials.token = None
        mock_credentials.get_frozen_credentials.return_value = mock_frozen_credentials

        env_without_region = {k: v for k, v in os.environ.items() if k != "AWS_REGION"}

        with (
            patch.dict(os.environ, env_without_region, clear=True),
            patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class,
            patch("rossum_agent.bedrock_client.AnthropicBedrock"),
        ):
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_session.region_name = None
            mock_session_class.return_value = mock_session

            create_bedrock_client()

            mock_session_class.assert_called_once_with(
                profile_name=None,
                region_name=None,
            )

    def test_raises_error_when_no_credentials_found(self):
        """Test that RuntimeError is raised when no credentials are found."""
        with patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = None
            mock_session_class.return_value = mock_session

            with pytest.raises(RuntimeError, match="No AWS credentials found"):
                create_bedrock_client()

    def test_explicit_region_overrides_environment(self):
        """Test that explicit aws_region parameter overrides environment variable."""
        mock_credentials = MagicMock()
        mock_frozen_credentials = MagicMock()
        mock_frozen_credentials.access_key = "key"
        mock_frozen_credentials.secret_key = "secret"
        mock_frozen_credentials.token = None
        mock_credentials.get_frozen_credentials.return_value = mock_frozen_credentials

        with (
            patch.dict(os.environ, {"AWS_REGION": "ap-southeast-1"}),
            patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class,
            patch("rossum_agent.bedrock_client.AnthropicBedrock"),
        ):
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_session.region_name = "us-east-1"
            mock_session_class.return_value = mock_session

            create_bedrock_client(aws_region="us-east-1")

            mock_session_class.assert_called_once_with(
                profile_name=None,
                region_name="us-east-1",
            )


class TestCreateBedrockClientFromStsCredentials:
    """Test create_bedrock_client_from_sts_credentials function."""

    def test_creates_client_from_sts_credentials(self):
        """Test creating client from STS assumed role credentials."""
        sts_credentials = {
            "AccessKeyId": "ASIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY",
            "SessionToken": "FwoGZXIvYXdzEBYaDNYC4FeH...",
        }

        with patch("rossum_agent.bedrock_client.AnthropicBedrock") as mock_anthropic:
            create_bedrock_client_from_sts_credentials(
                credentials=sts_credentials,
                aws_region="eu-west-1",
            )

            mock_anthropic.assert_called_once_with(
                aws_access_key="ASIAIOSFODNN7EXAMPLE",
                aws_secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY",
                aws_session_token="FwoGZXIvYXdzEBYaDNYC4FeH...",
                aws_region="eu-west-1",
            )

    def test_passes_none_region_when_not_provided(self):
        """Test that aws_region is None when not explicitly provided."""
        sts_credentials = {
            "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "secret",
        }

        with patch("rossum_agent.bedrock_client.AnthropicBedrock") as mock_anthropic:
            create_bedrock_client_from_sts_credentials(credentials=sts_credentials)

            mock_anthropic.assert_called_once_with(
                aws_access_key="AKIAIOSFODNN7EXAMPLE",
                aws_secret_key="secret",
                aws_session_token=None,
                aws_region=None,
            )

    def test_handles_missing_session_token(self):
        """Test that missing SessionToken is handled gracefully."""
        sts_credentials = {
            "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "secret",
        }

        with patch("rossum_agent.bedrock_client.AnthropicBedrock") as mock_anthropic:
            create_bedrock_client_from_sts_credentials(
                credentials=sts_credentials,
                aws_region="us-east-1",
            )

            call_kwargs = mock_anthropic.call_args[1]
            assert call_kwargs["aws_session_token"] is None


class TestGetModelId:
    """Test get_model_id function."""

    def test_returns_default_model_id(self):
        """Test that default model ID is returned when no env vars are set."""
        env_without_model_vars = {
            k: v for k, v in os.environ.items() if k not in ("LLM_MODEL_ID", "AWS_BEDROCK_MODEL_ARN")
        }

        with patch.dict(os.environ, env_without_model_vars, clear=True):
            model_id = get_model_id()

            assert model_id == DEFAULT_MODEL_ID

    def test_returns_model_arn_when_set(self):
        """Test that AWS_BEDROCK_MODEL_ARN takes precedence."""
        model_arn = "arn:aws:bedrock:us-east-1:123456789012:provisioned-model/abc123"

        with patch.dict(
            os.environ,
            {
                "AWS_BEDROCK_MODEL_ARN": model_arn,
                "LLM_MODEL_ID": "bedrock/some-other-model",
            },
        ):
            result = get_model_id()

            assert result == model_arn

    def test_strips_bedrock_prefix_from_llm_model_id(self):
        """Test that 'bedrock/' prefix is stripped from LLM_MODEL_ID."""
        env_without_arn = {k: v for k, v in os.environ.items() if k != "AWS_BEDROCK_MODEL_ARN"}
        env_without_arn["LLM_MODEL_ID"] = "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"

        with patch.dict(os.environ, env_without_arn, clear=True):
            result = get_model_id()

            assert result == "anthropic.claude-3-sonnet-20240229-v1:0"

    def test_returns_llm_model_id_without_prefix_unchanged(self):
        """Test that LLM_MODEL_ID without prefix is returned unchanged."""
        env_without_arn = {k: v for k, v in os.environ.items() if k != "AWS_BEDROCK_MODEL_ARN"}
        env_without_arn["LLM_MODEL_ID"] = "anthropic.claude-3-haiku-20240307-v1:0"

        with patch.dict(os.environ, env_without_arn, clear=True):
            result = get_model_id()

            assert result == "anthropic.claude-3-haiku-20240307-v1:0"
