"""Tests for rossum_agent.bedrock_client module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.bedrock_client import OPUS_MODEL_ID, create_bedrock_client, get_model_id


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
                max_retries=5,
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


class TestGetModelId:
    """Test get_model_id function."""

    def test_returns_default_model_id(self):
        """Test that default model ID is returned when no env vars are set."""
        env_without_model_vars = {k: v for k, v in os.environ.items() if k != "AWS_BEDROCK_MODEL_ARN"}

        with patch.dict(os.environ, env_without_model_vars, clear=True):
            model_id = get_model_id()

            assert model_id == f"bedrock/{OPUS_MODEL_ID}"

    def test_returns_model_arn_when_set(self):
        """Test that AWS_BEDROCK_MODEL_ARN takes precedence."""
        model_arn = "arn:aws:bedrock:us-east-1:123456789012:provisioned-model/abc123"

        with patch.dict(os.environ, {"AWS_BEDROCK_MODEL_ARN": model_arn}):
            result = get_model_id()

            assert result == model_arn
