#!/bin/bash
# End-to-end test script for ALPHA in Mock Mode
# No AWS credentials required - uses deterministic mock data

set -e  # Exit on any error

echo "════════════════════════════════════════════════════════════════"
echo "  ALPHA End-to-End Test (Mock Mode)"
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

# Test 1: Audit command
echo -e "${BLUE}🔍 Test 1: Running audit command${NC}"
poetry run alpha audit --mock-mode
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Audit command succeeded${NC}"
else
    echo -e "${YELLOW}✗ Audit command failed${NC}"
    exit 1
fi
echo ""

# Test 2: Analyze command with all outputs
echo -e "${BLUE}📊 Test 2: Running analyze command${NC}"
poetry run alpha analyze \
  --role-arn arn:aws:iam::123456789012:role/TestRole \
  --mock-mode \
  --output test-proposal.json \
  --output-cloudformation test-cfn-patch.yml \
  --output-terraform test-tf-patch.tf

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Analyze command succeeded${NC}"
else
    echo -e "${YELLOW}✗ Analyze command failed${NC}"
    exit 1
fi
echo ""

# Validate outputs exist
echo -e "${BLUE}📝 Validating output files...${NC}"
test -f test-proposal.json && echo -e "${GREEN}✓ JSON proposal created${NC}"
test -f test-cfn-patch.yml && echo -e "${GREEN}✓ CloudFormation patch created${NC}"
test -f test-tf-patch.tf && echo -e "${GREEN}✓ Terraform patch created${NC}"
echo ""

# Test 3: Apply command (dry-run)
echo -e "${BLUE}🚀 Test 3: Testing apply command (dry-run)${NC}"
poetry run alpha apply \
  --state-machine-arn arn:aws:states:us-east-1:123:stateMachine/Test \
  --proposal test-proposal.json \
  --mock-mode \
  --dry-run > /dev/null
echo -e "${GREEN}✓ Apply dry-run succeeded${NC}"
echo ""

# Test 4: Rollback command (mock mode)
echo -e "${BLUE}⏪ Test 4: Testing rollback command (mock mode)${NC}"
# Use role-arn for history lookup simulation
poetry run alpha rollback \
  --role-arn arn:aws:iam::123:role/Test \
  --state-machine-arn arn:aws:states:us-east-1:123:stateMachine/Test \
  --mock-mode \
  --dry-run > /dev/null
echo -e "${GREEN}✓ Rollback (history lookup) dry-run succeeded${NC}"

# Use proposal file
poetry run alpha rollback \
  --proposal test-proposal.json \
  --state-machine-arn arn:aws:states:us-east-1:123:stateMachine/Test \
  --mock-mode \
  --dry-run > /dev/null
echo -e "${GREEN}✓ Rollback (proposal file) dry-run succeeded${NC}"
echo ""

# Test 5: Diff & Status commands
echo -e "${BLUE}📊 Test 5: Testing diff & status commands${NC}"
poetry run alpha diff --input test-proposal.json --mock-mode > /dev/null
echo -e "${GREEN}✓ Diff command succeeded${NC}"

poetry run alpha status --role-arn arn:aws:iam::123:role/Test --state-machine-arn arn:aws:states:us-east-1:123:stateMachine/Test --mock-mode > /dev/null
echo -e "${GREEN}✓ Status command succeeded${NC}"
echo ""

# Summary
echo "════════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✓ All Mock Mode tests passed!${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""