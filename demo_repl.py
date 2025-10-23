#!/usr/bin/env python3
"""
ALPHA Demo REPL

Guided, step-by-step demo runner. Press Enter to advance; 'q' to quit; 's' to skip.

Usage:
  python3 demo_repl.py [--role-arn ARN] [--state-machine-arn ARN] [--usage-days N]
                       [--guardrails sandbox|prod] [--bedrock-model MODEL_ID]

Environment:
  ROLE_ARN                IAM role to analyze (falls back to --role-arn)
  STATE_MACHINE_ARN       Step Functions ARN for rollout (optional for dry run)
  ALPHA_BEDROCK_MODEL_ID  Bedrock model override (e.g., us.amazon.nova-pro-v1:0)
  AWS_REGION              Default us-east-1 if not set
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


def pause(prompt: str = "Press Enter to continue, 'q' to quit, 's' to skip: ") -> str:
    try:
        return input(prompt).strip().lower()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)


def run(cmd: list[str] | str, env: dict | None = None) -> int:
    if isinstance(cmd, str):
        printable = cmd
        args = cmd
        shell = True
    else:
        printable = " ".join(shlex.quote(c) for c in cmd)
        args = cmd
        shell = False
    print(f"\n$ {printable}")
    proc = subprocess.run(args, env=env, shell=shell)
    return proc.returncode


def print_hr(title: str) -> None:
    bar = "=" * 70
    print(f"\n{bar}\n{title}\n{bar}")


def read_json(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Could not read {path}: {e}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="ALPHA Demo REPL")
    parser.add_argument("--role-arn", help="IAM role ARN to analyze")
    parser.add_argument("--state-machine-arn", help="Step Functions state machine ARN")
    parser.add_argument("--usage-days", type=int, default=1, help="Usage window in days (default: 1)")
    parser.add_argument("--guardrails", default="sandbox", choices=["none", "sandbox", "prod"], help="Guardrail preset (default: sandbox)")
    parser.add_argument("--bedrock-model", help="Override Bedrock model ID (env ALPHA_BEDROCK_MODEL_ID)")
    args = parser.parse_args()

    role_arn = args.role_arn or os.getenv("ROLE_ARN")
    sm_arn = args.state_machine_arn or os.getenv("STATE_MACHINE_ARN")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    if not role_arn:
        print("ERROR: Provide --role-arn or set ROLE_ARN in env.")
        sys.exit(1)

    env = os.environ.copy()
    env.setdefault("AWS_REGION", aws_region)
    if args.bedrock_model:
        env["ALPHA_BEDROCK_MODEL_ID"] = args.bedrock_model

    print_hr("ALPHA – 3-Minute Demo")
    print("Hook: 95% of IAM permissions are never used. Copy‑pasted policies ship ‘s3:*’ into prod. ALPHA fixes this in seconds — not weeks.")
    if pause() == "q":
        return

    print("One‑liner: ALPHA analyzes CloudTrail, proposes least‑privilege with Bedrock, enforces guardrails, and can roll out safely via Step Functions.")
    if pause() == "q":
        return

    # Step 1: Analyze (fast)
    print_hr("Analyze (fast mode, real AWS)")
    analyze_cmd = [
        "poetry", "run", "alpha", "analyze",
        "--role-arn", role_arn,
        "--usage-days", str(args.usage_days),
        "--guardrails", args.guardrails,
        "--output", "proposal.json",
        "--output-cloudformation", "cfn.yml",
        "--output-terraform", "tf.tf",
    ]
    print("Fast mode is default — completes in seconds using CloudTrail Event History.")
    if pause("Press Enter to analyze, 'q' to quit: ") == "q":
        return
    rc = run(analyze_cmd, env=env)
    if rc != 0:
        print(f"Analyze returned exit code {rc}. Continuing anyway.")

    print("\nInspecting outputs…")
    run(["ls", "-lh", "proposal.json", "cfn.yml", "tf.tf"], env=env)

    data = read_json(Path("proposal.json"))
    if data and "proposal" in data:
        risk = data["proposal"].get("risk_signal") or data["proposal"].get("riskSignal")
        if risk:
            print(f"Risk: {risk}")
        policy = data["proposal"].get("proposed_policy") or data["proposal"].get("proposedPolicy")
        if policy:
            try:
                actions = policy["Statement"][0].get("Action", [])
                if isinstance(actions, list):
                    print(f"First statement action count: {len(actions)}")
                else:
                    print("First statement action: 1")
            except Exception:
                pass

    # Step 2: Guardrails (prod)
    print_hr("Guardrails (prod preset demonstration)")
    print("In prod preset, guardrails block risky services and wildcards — showing non‑zero exit code.")
    if pause("Press Enter to run prod guardrails demo, 's' to skip: ") == "s":
        pass
    else:
        rc = run(["poetry", "run", "alpha", "analyze", "--role-arn", role_arn, "--usage-days", str(args.usage_days), "--guardrails", "prod", "--output", "/tmp/ignore.json"], env=env)
        print(f"Exit code: {rc} (expected non‑zero for violations)")

    # Step 3: Step Functions dry run
    print_hr("Staged rollout (Step Functions)")
    if not sm_arn:
        print("STATE_MACHINE_ARN not set. You can still dry‑run with a placeholder ARN or set it and rerun this step.")
    else:
        print(f"Using state machine: {sm_arn}")
    if pause("Press Enter to dry‑run apply, 's' to skip: ") == "s":
        pass
    else:
        apply_dry = [
            "poetry", "run", "alpha", "apply",
            "--state-machine-arn", sm_arn or "arn:aws:states:us-east-1:000000000000:stateMachine:Placeholder",
            "--proposal", "proposal.json",
            "--dry-run",
        ]
        run(apply_dry, env=env)

    # Step 4: Step Functions live execution
    if sm_arn:
        print("Starting a real execution (approvals are off by default for demo).")
        if pause("Press Enter to start execution, 's' to skip: ") == "s":
            pass
        else:
            apply_live = [
                "poetry", "run", "alpha", "apply",
                "--state-machine-arn", sm_arn,
                "--proposal", "proposal.json",
            ]
            run(apply_live, env=env)
    else:
        print("Skipping live execution (no STATE_MACHINE_ARN). See docs/DEMO_SCRIPT.md for setup.")

    # Step 5: AgentCore Runtime invocation (if uv + runtime are available)
    print_hr("AgentCore Runtime (managed endpoints)")
    agentcore_dir = os.getenv("AGENTCORE_DIR", "agentcore_deploy")
    print(f"Using AgentCore project directory: {agentcore_dir}")
    if pause("Press Enter to show AgentCore status, 's' to skip: ") != "s":
        run(["uv", "--directory", agentcore_dir, "run", "agentcore", "status"], env=env)
    # analyze_fast_policy
    if pause("Press Enter to invoke analyze_fast_policy via AgentCore, 's' to skip: ") != "s":
        payload = {
            "action": "analyze_fast_policy",
            "roleArn": role_arn,
            "usageDays": args.usage_days,
            "region": aws_region,
        }
        import json as _json
        run(["uv", "--directory", agentcore_dir, "run", "agentcore", "invoke", _json.dumps(payload)], env=env)
    # enforce_policy_guardrails
    if pause("Press Enter to invoke enforce_policy_guardrails via AgentCore, 's' to skip: ") != "s":
        toy_policy = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}]}
        payload2 = {"action": "enforce_policy_guardrails", "policy": toy_policy, "preset": "prod"}
        import json as _json
        run(["uv", "--directory", agentcore_dir, "run", "agentcore", "invoke", _json.dumps(payload2)], env=env)

    # Close
    print_hr("Close")
    print("In under a minute of runtime, we produced an explainable least‑privilege policy from real usage, enforced guardrails, and kicked off a safe rollout. Practical today; Analyzer path available when you want deeper scoping.")
    print("\nBonus: AgentCore Runtime entrypoints are available at src/alpha_agent/agentcore_entrypoint.py for managed deployment (enforce_policy_guardrails, analyze_fast_policy). See README/QUICKSTART.")


if __name__ == "__main__":
    main()
