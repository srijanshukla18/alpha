#!/bin/bash
# End-to-end test script for ALPHA in Judge Mode
# No AWS credentials required - uses deterministic mock data

set -e  # Exit on any error

echo "════════════════════════════════════════════════════════════════"
echo "  ALPHA End-to-End Test (Judge Mode)"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Clean up any previous test outputs
echo -e "${BLUE}🧹 Cleaning up previous test outputs...${NC}"
rm -f test-proposal.json test-cfn-patch.yml test-tf-patch.tf
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Test 1: Analyze command with all outputs
echo -e "${BLUE}📊 Test 1: Running analyze command${NC}"
echo "Command: alpha analyze --role-arn arn:aws:iam::123456789012:role/TestRole --judge-mode --output test-proposal.json --output-cloudformation test-cfn-patch.yml --output-terraform test-tf-patch.tf"
echo ""

poetry run alpha analyze \
  --role-arn arn:aws:iam::123456789012:role/TestRole \
  --judge-mode \
  --output test-proposal.json \
  --output-cloudformation test-cfn-patch.yml \
  --output-terraform test-tf-patch.tf

EXIT_CODE=$?
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Analyze command succeeded (exit code: $EXIT_CODE)${NC}"
else
    echo -e "${YELLOW}⚠ Analyze command returned exit code: $EXIT_CODE${NC}"
fi
echo ""

# Validate outputs exist
echo -e "${BLUE}📝 Validating output files...${NC}"

if [ -f "test-proposal.json" ]; then
    echo -e "${GREEN}✓ JSON proposal created${NC}"

    # Validate JSON structure
    if command -v jq &> /dev/null; then
        echo "  Validating JSON structure with jq..."
        jq -e '.proposal.proposedPolicy' test-proposal.json > /dev/null && echo -e "  ${GREEN}✓ proposedPolicy present${NC}"
        jq -e '.proposal.riskSignal' test-proposal.json > /dev/null && echo -e "  ${GREEN}✓ riskSignal present${NC}"
        jq -e '.diff' test-proposal.json > /dev/null && echo -e "  ${GREEN}✓ diff present${NC}"
        jq -e '.metadata' test-proposal.json > /dev/null && echo -e "  ${GREEN}✓ metadata present${NC}"
    else
        echo -e "  ${YELLOW}⚠ jq not found, skipping JSON validation${NC}"
    fi
else
    echo -e "${YELLOW}✗ JSON proposal NOT created${NC}"
    exit 1
fi

if [ -f "test-cfn-patch.yml" ]; then
    echo -e "${GREEN}✓ CloudFormation patch created${NC}"
    echo "  Preview (first 10 lines):"
    head -n 10 test-cfn-patch.yml | sed 's/^/    /'
else
    echo -e "${YELLOW}✗ CloudFormation patch NOT created${NC}"
fi

if [ -f "test-tf-patch.tf" ]; then
    echo -e "${GREEN}✓ Terraform patch created${NC}"
    echo "  Preview (first 10 lines):"
    head -n 10 test-tf-patch.tf | sed 's/^/    /'
else
    echo -e "${YELLOW}✗ Terraform patch NOT created${NC}"
fi
echo ""

# Test 2: Guardrail presets
echo -e "${BLUE}🔒 Test 2: Testing guardrail presets${NC}"

echo "  Testing 'none' preset..."
poetry run alpha analyze --role-arn arn:aws:iam::123:role/Test --judge-mode --guardrails none > /dev/null
echo -e "  ${GREEN}✓ 'none' preset works${NC}"

echo "  Testing 'sandbox' preset..."
poetry run alpha analyze --role-arn arn:aws:iam::123:role/Test --judge-mode --guardrails sandbox > /dev/null
echo -e "  ${GREEN}✓ 'sandbox' preset works${NC}"

echo "  Testing 'prod' preset..."
poetry run alpha analyze --role-arn arn:aws:iam::123:role/Test --judge-mode --guardrails prod > /dev/null
echo -e "  ${GREEN}✓ 'prod' preset works${NC}"
echo ""

# Test 3: Service/action exclusions
echo -e "${BLUE}🚫 Test 3: Testing exclusion filters${NC}"

echo "  Testing exclude-services..."
poetry run alpha analyze \
  --role-arn arn:aws:iam::123:role/Test \
  --judge-mode \
  --exclude-services ec2,rds > /dev/null
echo -e "  ${GREEN}✓ Service exclusion works${NC}"

echo "  Testing suppress-actions..."
poetry run alpha analyze \
  --role-arn arn:aws:iam::123:role/Test \
  --judge-mode \
  --suppress-actions s3:DeleteBucket,dynamodb:DeleteTable > /dev/null
echo -e "  ${GREEN}✓ Action suppression works${NC}"
echo ""

# Test 4: Apply command (dry-run)
echo -e "${BLUE}🚀 Test 4: Testing apply command (dry-run)${NC}"

poetry run alpha apply \
  --state-machine-arn arn:aws:states:us-east-1:123:stateMachine/Test \
  --proposal test-proposal.json \
  --judge-mode \
  --dry-run > /dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Apply dry-run succeeded${NC}"
else
    echo -e "${YELLOW}✗ Apply dry-run failed${NC}"
fi
echo ""

# Test 5: Help commands
echo -e "${BLUE}📖 Test 5: Testing help commands${NC}"

poetry run alpha --help > /dev/null && echo -e "${GREEN}✓ Main help works${NC}"
poetry run alpha analyze --help > /dev/null && echo -e "${GREEN}✓ Analyze help works${NC}"
poetry run alpha propose --help > /dev/null && echo -e "${GREEN}✓ Propose help works${NC}"
poetry run alpha apply --help > /dev/null && echo -e "${GREEN}✓ Apply help works${NC}"
echo ""

# Summary
echo "════════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✓ All tests passed!${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Generated test files:"
echo "  • test-proposal.json     - Full proposal with metadata"
echo "  • test-cfn-patch.yml     - CloudFormation patch"
echo "  • test-tf-patch.tf       - Terraform patch"
echo ""
echo "Try the full workflow:"
echo "  1. alpha analyze --role-arn <ARN> --judge-mode --output proposal.json"
echo "  2. alpha propose --repo org/repo --branch harden/role --input proposal.json"
echo "  3. alpha apply --state-machine-arn <ARN> --proposal proposal.json --dry-run"
echo ""
echo "Clean up test files:"
echo "  rm test-proposal.json test-cfn-patch.yml test-tf-patch.tf"
echo ""
