"""
Tests for alpha_agent.collector module.

Tests IAM Access Analyzer policy generation functionality.
"""
import pytest
from unittest.mock import MagicMock, patch
import json
import time

from alpha_agent.collector import (
    PolicyGenerationError,
    start_policy_generation,
    wait_for_policy_json,
    generate_policy,
)
from alpha_agent.models import PolicyGenerationRequest, PolicyDocument


class TestStartPolicyGeneration:
    """Tests for start_policy_generation function."""

    def test_successful_start(self):
        mock_client = MagicMock()
        mock_client.start_policy_generation.return_value = {"jobId": "test-job-123"}

        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=["arn:aws:cloudtrail:us-east-1:123456789012:trail/test"],
            usage_period_days=30
        )

        job_id = start_policy_generation(request, client=mock_client)
        assert job_id == "test-job-123"
        mock_client.start_policy_generation.assert_called_once()

    def test_client_error_raises(self):
        mock_client = MagicMock()
        from botocore.exceptions import ClientError
        mock_client.start_policy_generation.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameterException"}},
            "StartPolicyGeneration"
        )

        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=["arn:aws:cloudtrail:us-east-1:123456789012:trail/test"],
        )

        with pytest.raises(PolicyGenerationError):
            start_policy_generation(request, client=mock_client)

    def test_request_format(self):
        mock_client = MagicMock()
        mock_client.start_policy_generation.return_value = {"jobId": "job-1"}

        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=[
                "arn:aws:cloudtrail:us-east-1:123456789012:trail/trail1",
                "arn:aws:cloudtrail:us-east-1:123456789012:trail/trail2"
            ],
            usage_period_days=7
        )

        start_policy_generation(request, client=mock_client)

        call_args = mock_client.start_policy_generation.call_args
        assert "cloudTrailDetails" in call_args.kwargs
        assert "policyGenerationDetails" in call_args.kwargs
        assert len(call_args.kwargs["cloudTrailDetails"]["trails"]) == 2


class TestWaitForPolicyJson:
    """Tests for wait_for_policy_json function."""

    def test_immediate_success(self):
        mock_client = MagicMock()
        policy_doc = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "*"}]}
        mock_client.get_generated_policy.return_value = {
            "jobDetails": {"status": "SUCCEEDED"},
            "generatedPolicyResult": {"policy": json.dumps(policy_doc)}
        }

        result = wait_for_policy_json("job-123", client=mock_client, poll_interval=0)
        assert result == policy_doc

    def test_polling_until_success(self):
        mock_client = MagicMock()
        policy_doc = {"Version": "2012-10-17", "Statement": []}

        mock_client.get_generated_policy.side_effect = [
            {"jobDetails": {"status": "IN_PROGRESS"}},
            {"jobDetails": {"status": "IN_PROGRESS"}},
            {
                "jobDetails": {"status": "SUCCEEDED"},
                "generatedPolicyResult": {"policy": json.dumps(policy_doc)}
            }
        ]

        with patch('time.sleep'):  # Skip actual sleeping
            result = wait_for_policy_json("job-123", client=mock_client, poll_interval=0)
        assert result == policy_doc
        assert mock_client.get_generated_policy.call_count == 3

    def test_job_failed(self):
        mock_client = MagicMock()
        mock_client.get_generated_policy.return_value = {
            "jobDetails": {"status": "FAILED", "failureReason": "Access denied"}
        }

        with pytest.raises(PolicyGenerationError) as exc_info:
            wait_for_policy_json("job-123", client=mock_client, poll_interval=0)
        assert "failed" in str(exc_info.value).lower()
        assert "Access denied" in str(exc_info.value)

    def test_timeout(self):
        mock_client = MagicMock()
        mock_client.get_generated_policy.return_value = {
            "jobDetails": {"status": "IN_PROGRESS"}
        }

        with pytest.raises(PolicyGenerationError) as exc_info:
            wait_for_policy_json(
                "job-123",
                client=mock_client,
                poll_interval=0,
                timeout_seconds=0  # Immediate timeout
            )
        assert "timed out" in str(exc_info.value).lower()

    def test_client_error_during_polling(self):
        mock_client = MagicMock()
        from botocore.exceptions import ClientError
        mock_client.get_generated_policy.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}},
            "GetGeneratedPolicy"
        )

        with pytest.raises(PolicyGenerationError):
            wait_for_policy_json("job-123", client=mock_client, poll_interval=0)


class TestGeneratePolicy:
    """Tests for generate_policy convenience function."""

    def test_full_workflow(self):
        mock_client = MagicMock()
        mock_client.start_policy_generation.return_value = {"jobId": "test-job"}
        policy_doc = {
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]
        }
        mock_client.get_generated_policy.return_value = {
            "jobDetails": {"status": "SUCCEEDED"},
            "generatedPolicyResult": {"policy": json.dumps(policy_doc)}
        }

        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=["arn:aws:cloudtrail:us-east-1:123456789012:trail/test"],
        )

        result = generate_policy(request, client=mock_client, poll_interval=0)
        assert isinstance(result, PolicyDocument)
        assert len(result.statement) == 1

    def test_empty_statement_raises(self):
        mock_client = MagicMock()
        mock_client.start_policy_generation.return_value = {"jobId": "test-job"}
        policy_doc = {"Version": "2012-10-17", "Statement": []}
        mock_client.get_generated_policy.return_value = {
            "jobDetails": {"status": "SUCCEEDED"},
            "generatedPolicyResult": {"policy": json.dumps(policy_doc)}
        }

        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=["arn:aws:cloudtrail:us-east-1:123456789012:trail/test"],
        )

        with pytest.raises(PolicyGenerationError) as exc_info:
            generate_policy(request, client=mock_client, poll_interval=0)
        assert "Statement" in str(exc_info.value)

    def test_custom_timeout(self):
        mock_client = MagicMock()
        mock_client.start_policy_generation.return_value = {"jobId": "test-job"}
        policy_doc = {
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}]
        }
        mock_client.get_generated_policy.return_value = {
            "jobDetails": {"status": "SUCCEEDED"},
            "generatedPolicyResult": {"policy": json.dumps(policy_doc)}
        }

        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=["arn:aws:cloudtrail:us-east-1:123456789012:trail/test"],
        )

        result = generate_policy(
            request,
            client=mock_client,
            poll_interval=0,
            timeout_seconds=3600
        )
        assert isinstance(result, PolicyDocument)

    def test_version_preserved(self):
        mock_client = MagicMock()
        mock_client.start_policy_generation.return_value = {"jobId": "test-job"}
        policy_doc = {
            "Version": "2008-10-17",  # Older version
            "Statement": [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}]
        }
        mock_client.get_generated_policy.return_value = {
            "jobDetails": {"status": "SUCCEEDED"},
            "generatedPolicyResult": {"policy": json.dumps(policy_doc)}
        }

        request = PolicyGenerationRequest(
            analyzer_arn="arn:aws:access-analyzer:us-east-1:123456789012:analyzer/test",
            resource_arn="arn:aws:iam::123456789012:role/TestRole",
            cloudtrail_access_role_arn="arn:aws:iam::123456789012:role/CloudTrailRole",
            cloudtrail_trail_arns=["arn:aws:cloudtrail:us-east-1:123456789012:trail/test"],
        )

        result = generate_policy(request, client=mock_client, poll_interval=0)
        assert result.version == "2008-10-17"
