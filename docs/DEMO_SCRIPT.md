# ALPHA Demo Video Script (~3 Minutes)

## Scene 1: Cold Open (10 seconds)
**Visual**: Terminal with ALPHA logo ASCII art
**Audio**: Upbeat, tech-forward music fade in

**Narrator**:
> "Too many AWS IAM roles with AdminAccess? ALPHA automatically hardens them to least-privilege."

**Visual**: Quick montage:
- AWS console showing role with wildcard permissions
- Red warning icon
- ALPHA logo transition

---

## Scene 2: The Problem (20 seconds)
**Visual**: Split screen - left: IAM role with wildcard policy, right: CloudTrail logs

**Narrator**:
> "Meet the `ci-runner` role. It has full admin access (*) across all AWS services. But in reality, it only needs S3 read and DynamoDB query permissions."

**On-screen text**:
```
Current Policy: * (all actions)
Actual Usage:   s3:GetObject, s3:ListBucket, dynamodb:Query
```

**Narrator**:
> "This is a security risk. ALPHA fixes it automatically."

**Visual**: Fade to terminal

---

## Scene 3: Trigger Analysis (30 seconds)
**Visual**: Terminal showing ALPHA CLI invocation

**Command** (typed on screen):
```bash
python demo_cli.py --role-arn arn:aws:iam::123456789012:role/ci-runner
```

**Visual**: ALPHA starts executing, colorful output

**Narrator**:
> "ALPHA queries IAM Access Analyzer to pull 30 days of CloudTrail activity. It discovers the role only used 5 specific actions."

**On-screen output** (abbreviated):
```
Step 1: Analyzing IAM Role Usage
✓ CloudTrail analysis complete
  • s3:GetObject         150 invocations
  • s3:ListBucket         45 invocations
  • dynamodb:Query       200 invocations
```

**Visual**: Progress bar filling up

---

## Scene 4: Bedrock Reasoning (40 seconds)
**Visual**: Split screen - left: terminal, right: AWS Bedrock console (conceptual)

**Narrator**:
> "Next, ALPHA invokes Claude Sonnet 4.5—Anthropic's most intelligent model—on Amazon Bedrock. Claude analyzes the usage patterns and generates a human-readable explanation."

**On-screen output**:
```
Step 3: Bedrock AI Reasoning
Invoking Claude Sonnet 4.5 on Amazon Bedrock...

AI Analysis:
  The role exhibits access patterns for S3 (read) and DynamoDB (query).
  Based on 30 days of telemetry, the following least-privilege policy
  is recommended.

Risk Assessment:
  • Probability of breakage: 5%
  • Confidence level: High (1245 datapoints analyzed)
```

**Narrator**:
> "Claude provides a risk assessment: only 5% chance of breakage, with high confidence."

**Visual**: Highlight "5%" in green

---

## Scene 5: Policy Diff & Guardrails (30 seconds)
**Visual**: Side-by-side policy comparison

**Left side** (before):
```json
{
  "Effect": "Allow",
  "Action": "*",
  "Resource": "*"
}
```

**Right side** (after):
```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": "arn:aws:s3:::my-app-bucket/*"
},
{
  "Effect": "Allow",
  "Action": "dynamodb:Query",
  "Resource": "arn:aws:dynamodb:us-east-1:123456789012:table/my-table"
}
```

**Narrator**:
> "ALPHA shows the diff: wildcard permissions replaced with scoped ARNs and specific actions. Guardrails enforce organizational rules—no wildcards allowed in production."

**On-screen text**:
```
Policy Diff:
  + Added 5 scoped actions
  - Removed wildcard (*) action
  • Privilege reduction: 95%
```

---

## Scene 6: Human Approval (20 seconds)
**Visual**: Mock Slack notification

**Slack Message**:
```
ALPHA Bot [9:45 AM]
Approval required for IAM policy update `ci-runner`.

Summary: Replace wildcard with least-privilege policy
Risk: 5%
Violations: 0

[Approve] [Reject]
```

**Visual**: Mouse cursor clicks "Approve"

**Narrator**:
> "ALPHA sends a notification to Slack. A human reviewer approves the change in seconds."

**On-screen output**:
```
✓ Approved by: alice@company.com at 2025-10-18 09:45:30
```

---

## Scene 7: Staged Rollout (30 seconds)
**Visual**: Progress bar with 3 stages

**Narrator**:
> "Now comes the magic. ALPHA deploys the policy in stages: sandbox, canary, then production."

**On-screen output** (rapid sequence):
```
Stage 1: Sandbox
Attaching policy to sandbox role... Done!
Monitoring error metrics... ✓ 0 errors detected

Stage 2: Canary (10% traffic)
Attaching policy to canary role... Done!
Monitoring error metrics... ✓ 0.01% error rate (within threshold)

Stage 3: Production
Attaching policy to production role... Done!
Monitoring error metrics... ✓ 0% error rate
```

**Visual**: Green checkmarks appear for each stage

**Narrator**:
> "Each stage monitors CloudWatch metrics. If errors spike, ALPHA automatically rolls back."

---

## Scene 8: Success Metrics (20 seconds)
**Visual**: Dashboard-style metrics display

**On-screen metrics** (animated):
```
Final Results:
  • Privilege Reduction:  95% ✓
  • Actions Before:       All (*)
  • Actions After:        5 scoped actions
  • Resources Before:     All (*)
  • Resources After:      3 scoped ARNs
  • Rollout Time:         8 minutes
  • Error Rate:           0%
```

**Narrator**:
> "Policy hardening complete. The role now operates with 95% fewer privileges, but zero errors. Least privilege achieved."

**Visual**: Celebration animation (confetti or checkmark)

---

## Scene 9: Architecture Highlight (Optional: 20 seconds)
**Visual**: Architecture diagram on screen

**Narrator**:
> "Under the hood, ALPHA uses IAM Access Analyzer for usage telemetry, Amazon Bedrock for AI reasoning, and Step Functions for orchestration. It's fully serverless and scales to thousands of roles."

**On-screen text**:
```
Tech Stack:
  ✓ IAM Access Analyzer (policy generation)
  ✓ Amazon Bedrock (Claude Sonnet 4.5)
  ✓ AgentCore Runtime (agent execution)
  ✓ Step Functions (orchestration)
```

---

## Scene 10: Call to Action (10 seconds)
**Visual**: GitHub repo URL and hackathon logo

**Narrator**:
> "Ship safer permissions overnight, continuously. ALPHA—Autonomous Least-Privilege Hardening Agent. Built for the AWS AI Agent Global Hackathon."

**On-screen text**:
```
🔗 github.com/your-username/alpha
📖 docs.alpha.dev/deploy
🏆 AWS AI Agent Hackathon 2025
```

**Audio**: Music fade out

---

## Recording Tips

### Technical Setup
- **Screen Recording**: Use OBS Studio or Loom (1080p minimum)
- **Terminal**: Use a dark theme with high contrast (e.g., Dracula theme)
- **Font Size**: Increase terminal font to 18pt for readability
- **Cursor**: Enable cursor highlighting for demos

### Timing
- Total runtime target: **2:50 - 3:00**
- Keep each scene tight—no dead air
- Use fade transitions (0.5 seconds max)

### Narration
- **Tone**: Professional but enthusiastic
- **Pacing**: 140-160 words per minute
- **Emphasis**: Highlight key numbers (95%, 5%, 0%)
- Record in a quiet environment with a quality microphone

### Visual Polish
- Use consistent color scheme (green for success, red for warnings, blue for info)
- Add subtle zoom-ins for important text
- Ensure all text is readable at 720p resolution

### Pre-Production Checklist
- [ ] Test demo_cli.py runs without errors
- [ ] Prepare mock Slack notification screenshot
- [ ] Export architecture diagram as high-res PNG
- [ ] Write full narration script (word-for-word)
- [ ] Create title slide and end card

### Post-Production
- Add background music (royalty-free)
- Color grade for consistency
- Add subtle sound effects (whoosh for transitions)
- Export as MP4, H.264, 1920x1080, 60fps

---

## Alternative: Live AWS Demo (If Credentials Available)

If you can record with actual AWS credentials:

1. **Pre-create** a test IAM role with wildcard permissions
2. **Seed CloudTrail** with 30 days of synthetic activity (use a script)
3. **Deploy ALPHA** using CDK (as per deployment guide)
4. **Record** a live Step Functions execution:
   - Show state machine visual in AWS Console
   - Display each Lambda invocation in real-time
   - Zoom in on DynamoDB approval record
   - Show final policy attached in IAM console

**Pros**: More authentic, shows real AWS integrations
**Cons**: Slower (real API calls take 5-10 minutes), risk of failures during recording

**Recommendation**: Use `demo_cli.py` for speed and reliability, mention AWS deployment in narration.

---

## Backup Plan: Slides + Terminal

If video editing is limited:

1. **Slide 1**: Title + Problem statement
2. **Slide 2**: Architecture diagram
3. **Slide 3**: Terminal recording (3 minutes)
4. **Slide 4**: Results + Call to action

Use Google Slides or PowerPoint with clean, minimal design. Export as video with narration overlay.
