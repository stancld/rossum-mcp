from rossum_agent.agent import _parse_aws_role_based_params


class TestParseAwsRoleBasedParams:
    """Test _parse_aws_role_based_params function."""

    def test_returns_empty_dict_when_no_env_vars_set(self, monkeypatch):
        """Test that empty dict is returned when no AWS env vars are set."""
        monkeypatch.delenv("AWS_ROLE_NAME", raising=False)
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

        result = _parse_aws_role_based_params()

        assert result == {}

    def test_returns_all_keys_when_all_env_vars_set(self, monkeypatch):
        """Test that all keys are returned when all AWS env vars are set."""
        monkeypatch.setenv("AWS_ROLE_NAME", "test-role")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key-id")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key")

        result = _parse_aws_role_based_params()

        assert result == {
            "aws_role_name": "test-role",
            "aws_access_key_id": "test-key-id",
            "aws_secret_access_key": "test-secret-key",
        }

    def test_returns_only_set_keys(self, monkeypatch):
        """Test that only set env vars are included in the result."""
        monkeypatch.delenv("AWS_ROLE_NAME", raising=False)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key-id")
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

        result = _parse_aws_role_based_params()

        assert result == {"aws_access_key_id": "test-key-id"}

    def test_keys_are_lowercased(self, monkeypatch):
        """Test that returned keys are lowercase versions of env var names."""
        monkeypatch.setenv("AWS_ROLE_NAME", "my-role")

        result = _parse_aws_role_based_params()

        assert "aws_role_name" in result
        assert "AWS_ROLE_NAME" not in result
