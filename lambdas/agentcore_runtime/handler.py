"""
Lambda handler for AgentCore Runtime integration.

This handler serves as the entry point for ALPHA when deployed
to Amazon Bedrock AgentCore Runtime.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from alpha_agent.agentcore import AgentCoreTools, get_agentcore_tool_definitions

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AgentCore Runtime entry point for ALPHA agent.

    This handler receives invocations from AgentCore Runtime and
    dispatches tool calls to the appropriate ALPHA modules.

    Expected event payload from AgentCore:
    {
        "action": "invoke_tool",
        "tool_name": "generate_least_privilege_policy",
        "tool_input": {
            "analyzer_arn": "...",
            "resource_arn": "...",
            ...
        }
    }

    OR for tool discovery:
    {
        "action": "list_tools"
    }

    Returns:
    {
        "statusCode": 200,
        "tool_result": {...}
    }
    """
    try:
        action = event.get("action", "invoke_tool")

        # Handle tool discovery
        if action == "list_tools":
            tools = get_agentcore_tool_definitions()
            return {
                "statusCode": 200,
                "tools": tools,
            }

        # Handle tool invocation
        if action == "invoke_tool":
            tool_name = event["tool_name"]
            tool_input = event.get("tool_input", {})

            # Initialize tools with configuration from environment
            tools = AgentCoreTools(
                approval_table=os.getenv("APPROVAL_TABLE_NAME"),
                slack_webhook=os.getenv("SLACK_WEBHOOK_URL"),
                github_token=os.getenv("GITHUB_TOKEN"),
            )

            # Route to appropriate tool
            tool_method = getattr(tools, tool_name, None)
            if not tool_method:
                return {
                    "statusCode": 404,
                    "error": f"Tool '{tool_name}' not found",
                }

            # Invoke tool
            result = tool_method(**tool_input)

            return {
                "statusCode": 200,
                "tool_result": result,
            }

        return {
            "statusCode": 400,
            "error": f"Unsupported action: {action}",
        }

    except KeyError as err:
        LOGGER.error("Missing required field: %s", err)
        return {
            "statusCode": 400,
            "error": f"Missing required field: {err}",
        }
    except Exception as err:  # pylint: disable=broad-exception-caught
        LOGGER.exception("Unexpected error in AgentCore runtime")
        return {
            "statusCode": 500,
            "error": f"Unexpected error: {err}",
        }


def entrypoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    AgentCore-compatible entrypoint using the bedrock-agentcore SDK pattern.

    This function can be decorated with @app.entrypoint when using
    the bedrock-agentcore SDK's BedrockAgentCoreApp.
    """
    return handler(payload, None)
