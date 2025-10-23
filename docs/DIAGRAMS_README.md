# Architecture Diagrams for ALPHA

This directory contains Python scripts to generate AWS architecture diagrams with official AWS service icons.

## Prerequisites

```bash
# Install diagrams library
pip install diagrams

# Install Graphviz (macOS)
brew install graphviz

# Or if using Poetry (recommended)
poetry add diagrams --group dev
```

## Generate Diagrams

### Simple Overview (for pitch/demo)
```bash
cd docs
python3 architecture_simple.py
# Outputs: alpha_architecture_simple.png
```

**Use for:** Hackathon pitch slides, README hero image, 3-minute demo backdrop

### Detailed Technical (for submission)
```bash
cd docs
python3 architecture_detailed.py
# Outputs: alpha_architecture_detailed.png
```

**Use for:** Devpost submission "Architecture diagram" requirement, technical deep-dive, judge review

## What Gets Generated

- **PNG files** with official AWS service icons
- **Transparent background** (easy to overlay on slides)
- **Professional quality** (same icons AWS uses in docs)
- **Version controlled** (commit the .py files, regenerate anytime)

## Customization Tips

### Change direction
```python
with Diagram("ALPHA", direction="TB"):  # TB = top-to-bottom, LR = left-to-right
```

### Change colors for emphasis
```python
user >> Edge(label="critical path", color="red") >> service
```

### Add more services
```python
from diagrams.aws.network import APIGateway
gateway = APIGateway("API Gateway")
```

Full icon library: https://diagrams.mingrammer.com/docs/nodes/aws

## Alternative Tools (if you prefer GUI)

### 1. Cloudcraft (easiest)
- **URL:** https://www.cloudcraft.co/
- **Pros:** Drag-and-drop, 3D isometric view, AWS-specific
- **Cons:** Free tier limited to public diagrams
- **Best for:** Quick mockups, visually stunning diagrams

### 2. draw.io / diagrams.net (most flexible)
- **URL:** https://app.diagrams.net/
- **Pros:** Completely free, AWS icon library built-in, exports PNG/SVG
- **Cons:** Manual layout, not code-based
- **Best for:** Custom layouts, iterative design

**AWS icon library:** File → Open Library → Search "AWS" → Load AWS19 icons

### 3. Lucidchart (professional)
- **URL:** https://www.lucidchart.com/
- **Pros:** Polished templates, collaboration features
- **Cons:** Free tier limited
- **Best for:** Team collaboration

## Recommended for Hackathon Submission

**Use `architecture_detailed.py`** for the Devpost "Architecture diagram" requirement because:
1. Shows all components judges want to see (Bedrock, AgentCore, Step Functions)
2. Labels data flow clearly
3. Official AWS branding = professional credibility
4. Fits "Technical Execution (50%)" judging criteria

**Tip:** Export both PNG and add the .py file to your repo. Judges love seeing "infrastructure as code" extending to diagrams.
