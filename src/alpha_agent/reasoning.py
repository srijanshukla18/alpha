from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, ConfigDict, ValidationError

from .models import PolicyDocument, PolicyProposal, RiskSignal, GuardrailViolation

LOGGER = logging.getLogger(__name__)


class BedrockReasoningError(RuntimeError):
    """Raised when Bedrock reasoning fails."""


class _ProposalPayload(BaseModel):
    """Strict schema for LLM output to mitigate prompt-injection/invalid JSON."""

    model_config = ConfigDict(extra="forbid")

    policy: PolicyDocument
    rationale: str = ""
    risk_signal: RiskSignal = Field(default_factory=RiskSignal)
    guardrail_violations: list[GuardrailViolation] = Field(default_factory=list)
    remediation_notes: list[str] = Field(default_factory=list)


class BedrockReasoner:
    """
    Wraps an Amazon Bedrock text model (Claude Sonnet 4.5) to reason about policy diffs.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        client: Optional[boto3.client] = None,
        temperature: float = 0.2,
    ) -> None:
        # Allow override via env var
        self.model_id = model_id or os.getenv("ALPHA_BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
        self._client = client  # lazy init to avoid dependency during tests/offline
        self.temperature = temperature

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = boto3.client("bedrock-runtime")
            except Exception as err:
                raise BedrockReasoningError(f"Bedrock client unavailable: {err}") from err
        return self._client

    def _build_prompt(self, context: Dict[str, Any], generated_policy: PolicyDocument) -> str:
        prompt_sections = [
            "You are ALPHA, an IAM least-privilege expert embedded in a security engineering team.",
            "You receive:",
            "- The generated policy document based on actual usage.",
            "- Context about the role, service ownership, and organizational constraints.",
            "Respond with JSON containing:",
            "policy // policy JSON that is safe to apply.",
            "rationale // short paragraph summarizing the key changes.",
            "risk_signal // object with probability_of_break (0-1) and rationale.",
            "remediation_notes // list of action items for humans.",
            "guardrail_violations // list of {code, message, path} for any violations found.",
            "Only output JSON. Do not wrap in markdown.",
        ]

        payload = {
            "context": context,
            "generated_policy": generated_policy.model_dump(),
        }
        prompt_sections.append(json.dumps(payload))
        return "\n".join(prompt_sections)

    def propose_policy(
        self,
        context: Dict[str, Any],
        generated_policy: PolicyDocument,
    ) -> PolicyProposal:
        prompt = self._build_prompt(context, generated_policy)
        model_id = self.model_id
        # Choose payload schema based on model provider
        is_anthropic = model_id.startswith("anthropic.") or model_id.startswith("us.anthropic.")
        is_nova = model_id.startswith("amazon.nova") or model_id.startswith("us.amazon.nova") or model_id.startswith("eu.amazon.nova") or model_id.startswith("apac.amazon.nova")
        try:
            if is_anthropic:
                body = json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 2000,
                        "temperature": self.temperature,
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt}]}
                        ],
                    }
                )
            elif is_nova:
                # Nova text understanding – prefer messages + inferenceConfig schema
                body = json.dumps(
                    {
                        "messages": [
                            {"role": "user", "content": [{"text": prompt}]}
                        ],
                        "inferenceConfig": {
                            "maxTokens": 2000,
                            "temperature": self.temperature,
                        },
                    }
                )
            else:
                # Fallback to Titan-like schema
                body = json.dumps(
                    {
                        "inputText": prompt,
                        "textGenerationConfig": {
                            "maxTokenCount": 2000,
                            "temperature": self.temperature,
                            "topP": 0.9,
                        },
                    }
                )

            response = self.client.invoke_model(modelId=model_id, body=body, accept="application/json", contentType="application/json")
        except ClientError as err:
            raise BedrockReasoningError(f"Bedrock invocation failed: {err}") from err

        try:
            body = json.loads(response["body"].read())
            # Try Anthropic content first
            completion: Optional[str] = None
            if isinstance(body, dict):
                try:
                    completion = body["content"][0]["text"]
                except Exception:
                    # Try Nova-style keys
                    completion = (
                        body.get("completion")
                        or body.get("output", {}).get("text")
                        or body.get("results", [{}])[0].get("outputText")
                    )
            if (not completion or not isinstance(completion, str)) and isinstance(body, dict):
                try:
                    # Converse-style output
                    completion = body.get("output", {}).get("message", {}).get("content", [{}])[0].get("text")
                except Exception:
                    completion = completion
            if not completion or not isinstance(completion, str):
                raise KeyError("No text completion found in response")
            parsed_json = json.loads(completion)
            payload = _ProposalPayload.model_validate(parsed_json)
        except (KeyError, json.JSONDecodeError, ValidationError) as err:
            raise BedrockReasoningError(
                f"Unexpected response structure from model: {err}"
            ) from err

        return PolicyProposal(
            proposed_policy=payload.policy,
            rationale=payload.rationale,
            guardrail_violations=payload.guardrail_violations,
            risk_signal=payload.risk_signal,
            remediation_notes=payload.remediation_notes,
        )
