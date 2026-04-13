from alpha_agent.validation import validate_role_arn, validate_repo_slug
import pytest


def test_validate_role_arn_accepts_valid():
    validate_role_arn("arn:aws:iam::123456789012:role/MyRole")
    validate_role_arn("arn:aws:iam::123456789012:role/path/With-Valid_Chars")


@pytest.mark.parametrize("arn", ["", "arn:aws:iam::123:role/Bad", "arn:aws:iam::123456789012:user/NotRole"])
def test_validate_role_arn_rejects(arn):
    with pytest.raises(ValueError):
        validate_role_arn(arn)


def test_validate_repo_slug_accepts_valid():
    validate_repo_slug("owner/repo-name_1")


@pytest.mark.parametrize("repo", ["owner", "../owner/repo", "owner/repo extra", "owner/repo/extra"])
def test_validate_repo_slug_rejects(repo):
    with pytest.raises(ValueError):
        validate_repo_slug(repo)
