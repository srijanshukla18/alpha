# ALPHA Architecture Diagrams

This directory contains code-based definitions for ALPHA's system architecture, ensuring documentation stays in sync with implementation.

## Generation Setup

Requires Graphviz and the `diagrams` library.

```bash
# MacOS
brew install graphviz
poetry add diagrams --group dev
```

## Available Diagrams

### 1. Simple Overview
Focuses on the core Analyze-Propose-Apply workflow.
```bash
python3 docs/architecture_simple.py
# Outputs: docs/alpha_architecture_simple.png
```
**Use for:** README overview, high-level stakeholder presentations.

### 2. Detailed Technical Diagram
Deep dive into Step Functions, Bedrock integration, and AgentCore Runtime.
```bash
python3 docs/architecture_detailed.py
# Outputs: docs/alpha_architecture_detailed.png
```
**Use for:** SRE system reviews, security audits, technical deep-dives.

## Customization

Diagrams are defined in Python using the [Diagrams](https://diagrams.mingrammer.com/) library. To modify:
1. Edit `docs/architecture_detailed.py`.
2. Update service nodes or edge labels.
3. Rerun the script to regenerate the PNG.

## Alternative GUI Tools
If manual layout is required, we recommend the official AWS icon sets in:
- **Cloudcraft:** Isometric 3D views for infrastructure.
- **draw.io / diagrams.net:** Most flexible for custom flow layouts.
- **Lucidchart:** Best for collaborative design sessions.