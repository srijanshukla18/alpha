"""
Pytest configuration and shared fixtures for ALPHA tests.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Ensure local src/ is importable without installing package globally
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def mock_boto3_client():
    """Create a mock boto3 client factory."""
    def _create_client(service_name, **kwargs):
        client = MagicMock()
        client.service_name = service_name
        return client
    return _create_client


@pytest.fixture
def sample_policy_document():
    """Sample IAM policy document for testing."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:ListBucket"],
                "Resource": "*"
            }
        ]
    }


@pytest.fixture
def sample_wildcard_policy():
    """Sample policy with wildcard permissions."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "*",
                "Resource": "*"
            }
        ]
    }


@pytest.fixture
def sample_role_arn():
    """Sample IAM role ARN for testing."""
    return "arn:aws:iam::123456789012:role/TestRole"


@pytest.fixture
def mock_dynamodb_response():
    """Mock DynamoDB response for approval queries."""
    return {
        "Items": [
            {
                "proposal_id": {"S": "test-proposal"},
                "timestamp": {"S": "2025-01-15T10:30:00+00:00"},
                "approved": {"BOOL": True},
                "approver": {"S": "test-user@example.com"},
                "comments": {"S": "Approved for testing"}
            }
        ]
    }


@pytest.fixture
def fixed_datetime():
    """Fixed datetime for deterministic testing."""
    return datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
