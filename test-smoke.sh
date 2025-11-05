#!/bin/bash
# Simple smoke test - just verify ALPHA CLI works

set -e

echo "=========================================="
echo "ALPHA - Smoke Test (No AWS Required)"
echo "=========================================="
echo ""

echo "1. Testing CLI is installed..."
if poetry run alpha --version; then
    echo "✓ CLI works"
else
    echo "❌ CLI not working"
    exit 1
fi

echo ""
echo "2. Testing help output..."
if poetry run alpha --help > /dev/null; then
    echo "✓ Help works"
else
    echo "❌ Help not working"
    exit 1
fi

echo ""
echo "3. Testing analyze command help..."
if poetry run alpha analyze --help > /dev/null; then
    echo "✓ Analyze command works"
else
    echo "❌ Analyze command not working"
    exit 1
fi

echo ""
echo "4. Testing propose command help..."
if poetry run alpha propose --help > /dev/null; then
    echo "✓ Propose command works"
else
    echo "❌ Propose command not working"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ All Smoke Tests Passed"
echo "=========================================="
echo ""
echo "ALPHA is installed correctly!"
echo ""
echo "Next steps:"
echo "  1. Configure AWS credentials: aws configure"
echo "  2. Run against your account: ./test-alpha.sh"
echo "  3. Or create test Lambda: ./test-with-lambda.sh"
