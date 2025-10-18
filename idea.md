Amazing—thanks for the full brief. Here’s a **win‑oriented idea + implementation design** you can hand to your team and drive as the “idea guy.” It’s scoped to ship in ~3 days, uses the *right* AWS stack the judges care about, and tees you up for several category prizes.

---

## 🏆 Concept (one‑liner)

**ALPHA** — *Autonomous Least‑Privilege Hardening Agent*

> An agent that continuously **analyzes actual IAM usage**, proposes **least‑privilege policies**, and (with human approval) **rolls out safer permissions** across accounts. Built on **Amazon Bedrock AgentCore** + **Bedrock reasoning model**, with optional **Nova Act** for browser actions in SaaS/console UIs.

**Why this wins**

* **High, measurable impact (20%)**: Fewer over‑privileged roles, reduced attack surface, clear metrics (privilege reduction %, findings closed, MTTR).
* **Creative & timely (10%)**: Leverages **AgentCore (GA 4 days ago)** in a meaningful security use case + optional **Nova Act** browser actions, a fresh capability. ([Amazon Web Services, Inc.][1])
* **Technical execution (50%)**: Checks every “What to Build” box (AgentCore primitive, Bedrock LLM reasoning, tool integrations, autonomous workflow, external APIs). Uses **IAM Access Analyzer policy generation from CloudTrail** as the ground truth for least‑privilege. ([AWS Documentation][2])
* **Functionality (10%)**: End‑to‑end: detect → reason → propose → approve → apply → verify → report.
* **Demo clarity (10%)**: 3‑min run shows live policy diff, manual approval, controlled rollout, and success metrics.

---

## 🔭 What ALPHA actually does

1. **Collect usage** – Pulls *who actually did what* from CloudTrail via **IAM Access Analyzer** policy generation APIs. ([AWS Documentation][2])
2. **Reason & propose** – A **Bedrock** reasoning model (e.g., Claude Sonnet) turns usage into **least‑privilege policy** + resource scoping and conditions, explains tradeoffs, and drafts a PR‑ready policy JSON. (Claude Sonnet is fully supported on Bedrock.) ([AWS Documentation][3])
3. **Risk gates** – Adds organization‑specific guardrails (deny wildcards to prod, enforce tags) and checks for break risk (e.g., missing list/describe).
4. **Approval & rollout** – Human‑in‑the‑loop via Slack/UI approves staged changes; the agent then **attaches the policy** (sandbox → canary → target role) and monitors for break signals.
5. **(Optional) Nova Act demo move** – Use **Amazon Nova Act SDK** to show the agent **navigating the AWS console** (or Okta/GitHub) in a **secure, isolated browser** to apply a change or create a ticket—great demo moment. For safer production, the default path is API‑driven, but the demo can use the browser to wow judges. ([AGI Lab][4])
6. **Report** – Writes diffs, approvals, and outcomes to a dashboard and emits weekly “risk burned down” stats.

---

## 🧱 Reference architecture (aligns with “What to Build”)

```
[User (Web UI / Slack)]
        |
   Amazon CloudFront + S3 (static UI)
        |
  API Gateway (REST) ──────────────┐
        |                          |
   AgentCore Runtime  ◄────────────┼── (Observability/metrics)
   (Bedrock AgentCore)             |         CloudWatch
        |                          |
   AgentCore Tools:                |
   • IAM Analyzer Tool (boto3)     |    AgentCore Memory
   • GitHub PR Tool (REST)         |    (design decisions, approvals)
   • Slack Notifier                |
   • (Optional) AgentCore Browser / Nova Act
        |
  Step Functions Orchestrator  (batch & rollback)
        |
    Lambda “skills”:
    • start_policy_generation()
    • fetch_generated_policy()
    • risk_guardrails_and_diff()
    • canary_attach_and_verify()
    • open_github_pr()
        |
      IAM / CloudTrail / IAM Access Analyzer  ←→  S3 (artifacts)
        |
   DynamoDB (role baselines, rollouts)
```

* **AgentCore** gives you managed agent runtime, memory, identity, tooling, and a secure browser primitive; it just went GA and is built for exactly this agentic pattern. ([Amazon Web Services, Inc.][1])
* **AgentCore Browser** = safe, containerized browser with session isolation & auditing (for the optional “console action” scene). ([AWS Documentation][5])
* **Bedrock LLM** for reasoning (Claude 3.5/3.7 Sonnet on Bedrock). ([Amazon Web Services, Inc.][6])
* **IAM Access Analyzer** produces the draft least‑privilege policy from usage. ([AWS Documentation][2])
* **Step Functions** coordinates long‑running policy generation & staged rollouts (canary → blast radius). (AWS prescriptive pattern shows this integration.) ([AWS Documentation][7])
* **(Optional)** **Strands Agents SDK** as the code‑first agent framework *inside* AgentCore runtime (qualifies you for “Best Strands SDK”). ([Strands Agents][8])
* **(Optional)** **Nova Act SDK** to win the “Nova Act Integration” prize with a crisp browser‑action moment. ([GitHub][9])

---

## 🧪 Demo storyboard (3 minutes)

1. **Cold open (10s)** – “Too many AdminAccess roles? ALPHA auto‑hardens them.”
2. **Trigger (30s)** – Select `role/ci-runner` → click **“Analyze usage”**.
3. **Reason (40s)** – Show the **explanation panel** from the Bedrock model: “These 11 actions were used in last 30 days; adding 3 *List* hooks to avoid breakage.” (Backed by IAM Analyzer job ID.) ([AWS Documentation][10])
4. **Diff & guardrails (30s)** – Side‑by‑side JSON: before vs proposed least‑privilege. Highlight wildcard → resource‑scoped + conditions.
5. **Approval (20s)** – Click **Approve** in the UI or Slack.
6. **Rollout (30s)** – **Canary attach** → smoke test passes → progressive rollout.
7. **(Prize moment, 20s)** – **Nova Act** opens the AWS console in a **secure AgentCore Browser** session and performs a simple confirmatory step (e.g., verifies role attachment / creates a JIRA ticket), proving actioning capability. ([AGI Lab][4])
8. **Results (20s)** – Metrics panel: privileges cut 78%, 0 errors observed in canary, time saved.
9. **CTA (10s)** – “Ship safer permissions overnight, continuously.”

---

## ⚙️ Tech choices & how they map to rules

* **Large Language Model on Bedrock**: Anthropic Claude Sonnet for reasoning/explanations. ([Amazon Web Services, Inc.][6])
* **Agent platform**: **Amazon Bedrock AgentCore** (runtime + memory + tools + observability). **Use at least one AgentCore primitive** (Memory or Browser). ([AWS Documentation][11])
* **External integrations**: IAM Access Analyzer API, GitHub API, Slack API; optional Nova Act for browser actuation. ([AWS Documentation][2])
* **Autonomy**: Scheduled re‑analysis, guardrail checks, canary rollout, and self‑verification; human approval optional.
* **Security model**: AgentCore Identity (least‑privilege role assumptions), CloudTrail audit, read‑only fetch → guarded write paths. ([AWS Documentation][12])

---

## 🛠️ Implementation blueprint (3 days, small team)

### Day 1 — Foundations & happy path

* **Infra**: CDK/Terraform to provision AgentCore Runtime, Memory, API Gateway, Step Functions, Lambdas, DynamoDB, S3, IAM roles.
* **Tools**: Implement **IAM Analyzer Tool** wrapper (start / get policy job) + **GitHub PR Tool**. (Use `accessanalyzer:start-policy-generation` and `get-generated-policy`.) ([AWS Documentation][10])
* **LLM prompts**: System prompt that converts Analyzer output → least‑priv JSON with conditions & *list/describe* safety hooks.
* **UI**: Minimal S3/CloudFront single‑page app (role picker → analyze → show diff → approve).
* **Smoke test**: One role in a sandbox account.

### Day 2 — Rollouts, guardrails, & demo polish

* **Guardrails**: Enforce org rules (no `*` on prod; tag conditions).
* **Canary rollout**: Lambda attaches policy to `role/ci-runner-canary`; Step Functions monitors CloudWatch events/logs for errors; auto‑rollback if break detected.
* **Observability**: Emit spans/metrics for judge demo (jobs completed, privilege reduction %).
* **(Optional)** Integrate **Strands Agents** inside runtime (tool slates + planners). ([Strands Agents][8])
* **Slack**: Approve in Slack message action (signed callback to API Gateway).

### Day 3 — Prize hooks & video

* **(Optional)** **Nova Act** scene: script the agent to open console/Jira in the **AgentCore Browser** and complete a step; keep it deterministic. ([AGI Lab][4])
* **(Optional)** **Q Developer** cameo: show how Q auto‑generates unit tests for Lambdas or refactors a policy‑diff module (fits “Best Amazon Q Application” if you integrate meaningfully with the dev workflow). ([Amazon Web Services, Inc.][13])
* **Hardening**: Final pass on IAM policies (least‑priv for the agent itself).
* **Video**: Record 3‑min demo (script above).

---

## 🗂️ Repo & submission package

```
/alpha/
  /infra/            # CDK/Terraform
  /agent/
    runtime/         # AgentCore app bootstrap
    tools/
      iam_analyzer.py
      github_pr.py
      slack_notify.py
      nova_act_demo.py   # optional
    prompts/
      system_policy_refiner.md
  /lambdas/
    start_policy_generation/
    get_generated_policy/
    guardrails_and_diff/
    canary_attach_and_verify/
  /ui/               # S3 static site
  /docs/
    architecture-diagram.png
    README.md        # runbook + deploy steps
    demo-script.md
```

**What to submit**

* **Public repo URL** (readme with one‑click deploy + env vars).
* **Architecture diagram** (PNG + ASCII in README).
* **Text description** (Problem → Solution → Tech → Impact).
* **~3‑minute demo video** (script above).
* **Deployed URL** (CloudFront).

---

## 🔐 Policy logic (how the agent “thinks”)

* **Inputs**: Access Analyzer output for a role (actions & services actually used in a time window). ([AWS Documentation][2])
* **Heuristics**:

  * Always add **read‑only list/describe** calls for used services to minimize breakage. (AWS docs note action‑ vs service‑level output nuances; we bridge gaps.) ([AWS Documentation][14])
  * Replace `Resource: "*" ` with scoped ARNs if seen in CloudTrail; apply `Condition` blocks for tags, prefixes, or `aws:PrincipalOrgID`.
  * Flag suspicious grants (e.g., `iam:*`, `sts:AssumeRole` to external accounts).
* **Outputs**: Proposed policy JSON + natural‑language rationale + risk score + test plan.

---

## 📏 Success metrics (judge‑friendly)

* **Privilege reduction**: % drop in actions & wildcards (before vs after).
* **Safety**: 0 errors during canary window; automatic rollback proof.
* **Speed**: Time from “Analyze” to “Approved PR” (seconds).
* **Coverage**: Number of roles analyzed in batch.
* **Auditability**: Linked Analyzer job IDs and CloudTrail refs.

---

## 🧰 Detailed service mapping to categories

* **Best Bedrock AgentCore Implementation**: Runtime, Memory, Tools, and **Browser** primitive for a secured demo. ([AWS Documentation][5])
* **Best Bedrock Application**: Core reasoning & policy synthesis on **Bedrock** models. ([AWS Documentation][3])
* **Best Nova Act Integration** *(optional)*: Browser‑action scene in demo. ([AGI Lab][4])
* **Best Strands SDK Implementation** *(optional)*: Use Strands as your framework inside AgentCore. ([Strands Agents][8])
* **Amazon Q Application** *(optional)*: Show **Q Developer** autonomously generating tests/refactors for your Lambda step, with benchmarks cited by AWS. ([Amazon Web Services, Inc.][15])

---

## 🧪 Test data & safe demo setup

* Create a **sandbox account** with a deliberately broad `AdministratorAccess`‑like role used by a sample CI job.
* Generate benign CloudTrail activity (S3 list/get, ECS deploy, CloudWatch logs).
* Run policy generation for the last 7–30 days → **prove least‑privilege** delta via diff. ([AWS Documentation][2])

---

## ⚠️ Risks & mitigations

* **Policy gaps (e.g., missing `ListBucket`)** → add default read‑list heuristics and break‑glass rollback. ([Alexander Hose][16])
* **Browser demos flake** → keep **Nova Act** to a single deterministic action; primary path remains API‑driven. ([GitHub][9])
* **Agent privileges** → scope roles via **AgentCore Identity** and service‑scoped IAM. ([AWS Documentation][12])

---

## 💸 Rough cost (fits the $100 credit)

* Light Bedrock inference (few policy proposals), Lambda/Step Functions/DynamoDB pennies, S3/CloudFront minimal. No heavy training. (Use smaller Sonnet contexts.)

---

## 📝 Judge crib notes (drop in your submission)

* **AgentCore GA & primitives used** (Memory + Browser): state that the build relies on the newest GA capabilities purpose‑built for agents. ([Amazon Web Services, Inc.][1])
* **Real AWS capability** for policy generation (not synthetic): IAM Access Analyzer from CloudTrail. ([AWS Documentation][2])
* **Actionable autonomy**: canary rollout + rollback; optional **Nova Act** browser action to show real-world actuation. ([AGI Lab][4])

---

## 💡 Two backup ideas (if your team wants options)

1. **SpendGuard** — Cost anomaly triage & auto‑mitigation agent (EventBridge → Bedrock explanation → Lambda actions). Great metrics ($ saved), very visual graphs. ([AWS Documentation][17])
2. **S3 Shield** — Data‑exposure agent that detects public buckets/PII and auto‑applies Access Block settings + bucket policies; produces compliance reports. (Pairs nicely with AgentCore + Bedrock reasoning.)

---

If you want, I can also draft the **README.md outline, prompts, and the exact Step Functions state machine** your team can paste in. For now, you’ve got the idea and an implementation design that maps tightly to the rules and to what the judges will value.

[1]: https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available/?utm_source=chatgpt.com "Amazon Bedrock AgentCore is now generally available"
[2]: https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-policy-generation.html?utm_source=chatgpt.com "IAM Access Analyzer policy generation - AWS Identity and Access Management"
[3]: https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html?utm_source=chatgpt.com "Supported foundation models in Amazon Bedrock - Amazon Bedrock"
[4]: https://labs.amazon.science/blog/nova-act?utm_source=chatgpt.com "Introducing Amazon Nova Act"
[5]: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html?utm_source=chatgpt.com "Interact with web applications using Amazon Bedrock AgentCore Browser"
[6]: https://aws.amazon.com/blogs/aws/anthropics-claude-3-5-sonnet-model-now-available-in-amazon-bedrock-the-most-intelligent-claude-model-yet/?utm_source=chatgpt.com "Anthropic’s Claude 3.5 Sonnet model now available in Amazon Bedrock ..."
[7]: https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/dynamically-generate-an-iam-policy-with-iam-access-analyzer-by-using-step-functions.html?utm_source=chatgpt.com "Dynamically generate an IAM policy with IAM Access Analyzer by using ..."
[8]: https://strandsagents.com/latest/documentation/docs/?utm_source=chatgpt.com "Welcome - Strands Agents"
[9]: https://github.com/aws/nova-act?utm_source=chatgpt.com "GitHub - aws/nova-act: Amazon Nova Act is a research preview of a new ..."
[10]: https://docs.aws.amazon.com/cli/latest/reference/accessanalyzer/start-policy-generation.html?utm_source=chatgpt.com "start-policy-generation — AWS CLI 2.31.8 Command Reference"
[11]: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html?utm_source=chatgpt.com "Add memory to your Amazon Bedrock AgentCore agent"
[12]: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idp-microsoft.html?utm_source=chatgpt.com "Microsoft - Amazon Bedrock AgentCore"
[13]: https://aws.amazon.com/q/developer/features/?utm_source=chatgpt.com "AI for Software Development – Amazon Q Developer Features – AWS"
[14]: https://docs.aws.amazon.com/IAM/latest/UserGuide/getting-started_reduce-permissions-edit-policy.html?utm_source=chatgpt.com "Generating a policy based on access activity - AWS Identity and Access ..."
[15]: https://aws.amazon.com/about-aws/whats-new/2025/04/amazon-q-developer-releases-state-art-agent-feature-development/?utm_source=chatgpt.com "Amazon Q Developer releases state of the art agent for feature ..."
[16]: https://alexanderhose.com/how-to-generate-custom-policies-using-aws-iam-access-analyzer/?utm_source=chatgpt.com "How to generate custom policies using AWS IAM Access Analyzer"
[17]: https://docs.aws.amazon.com/cost-management/latest/userguide/cad-eventbridge.html?utm_source=chatgpt.com "Using EventBridge with Cost Anomaly Detection - AWS Cost Management"

