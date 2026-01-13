#!/bin/bash
# Security Upgrade Script for Support RAG System
# Generated: 2026-01-13
# Purpose: Apply critical security patches identified in dependency audit

set -e  # Exit on error

echo "========================================="
echo "Support RAG - Security Dependency Upgrade"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}WARNING: No virtual environment detected.${NC}"
    echo "It's recommended to run this in a virtual environment."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${YELLOW}Step 1/5: Checking current versions...${NC}"
echo "----------------------------------------"
pip show cryptography torch PyYAML langchain-core 2>/dev/null | grep -E "^(Name|Version):" || echo "Some packages not installed"
echo ""

echo -e "${YELLOW}Step 2/5: Creating backup of current environment...${NC}"
echo "----------------------------------------"
pip freeze > requirements.backup.$(date +%Y%m%d_%H%M%S).txt
echo "Backup created: requirements.backup.*.txt"
echo ""

echo -e "${RED}Step 3/5: Applying CRITICAL security patches...${NC}"
echo "----------------------------------------"
echo "This will upgrade:"
echo "  - cryptography to >=42.0.4 (CVE-2023-50782, CVE-2024-26130)"
echo "  - torch to >=2.6.0 (CVE-2025-32434)"
echo "  - PyYAML to >=6.0.3 (general security)"
echo ""
read -p "Proceed with upgrade? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Upgrade cancelled."
    exit 0
fi

# Upgrade critical packages
pip install --upgrade 'cryptography>=42.0.4' 'torch>=2.6.0' 'PyYAML>=6.0.3'

echo ""
echo -e "${YELLOW}Step 4/5: Verifying langchain-core version...${NC}"
echo "----------------------------------------"
LANGCHAIN_VERSION=$(pip show langchain-core 2>/dev/null | grep "^Version:" | awk '{print $2}')
echo "Current langchain-core version: $LANGCHAIN_VERSION"

if [ -z "$LANGCHAIN_VERSION" ]; then
    echo -e "${RED}ERROR: langchain-core not found${NC}"
    exit 1
fi

# Version comparison (simple check for >=1.2.5)
REQUIRED_VERSION="1.2.5"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$LANGCHAIN_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
    echo -e "${GREEN}✓ langchain-core is safe (>=$REQUIRED_VERSION)${NC}"
else
    echo -e "${RED}✗ langchain-core needs upgrade to >=$REQUIRED_VERSION${NC}"
    read -p "Upgrade langchain-core? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pip install --upgrade 'langchain-core>=1.2.5'
    fi
fi

echo ""
echo -e "${YELLOW}Step 5/5: Verifying upgraded versions...${NC}"
echo "----------------------------------------"
pip show cryptography torch PyYAML langchain-core | grep -E "^(Name|Version):"

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Security upgrade completed!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Run your test suite to ensure compatibility"
echo "2. Test critical functionality (especially ML models with torch)"
echo "3. If tests pass, commit the updated environment"
echo "4. Review DEPENDENCY_AUDIT_REPORT.md for additional recommendations"
echo ""
echo "Rollback instructions (if needed):"
echo "  pip install -r requirements.backup.<timestamp>.txt"
