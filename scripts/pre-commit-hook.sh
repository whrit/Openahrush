#!/usr/bin/env bash

# Pre-commit hook for Openahrush
# This script runs code quality checks before allowing commits
#
# Installation:
#   cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Exit status
EXIT_STATUS=0

print_header() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    EXIT_STATUS=1
}

print_warning() {
    echo -e "${YELLOW}! $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Get list of staged files
get_staged_files() {
    git diff --cached --name-only --diff-filter=ACM | grep -E '\.(py|yaml|yml)$' || true
}

# Check if any Python files are staged
has_python_files() {
    git diff --cached --name-only --diff-filter=ACM | grep -E '\.py$' > /dev/null 2>&1
}

# Check if any YAML files are staged
has_yaml_files() {
    git diff --cached --name-only --diff-filter=ACM | grep -E '\.(yaml|yml)$' > /dev/null 2>&1
}

# Run linting checks
check_linting() {
    print_header "Ruff Linting"

    if ! uv run ruff check . --extend-exclude=migrations/versions 2>&1 | head -20; then
        print_error "Ruff linting found issues"
        echo -e "${YELLOW}To fix, run: uv run ruff check . --fix${NC}"
        return 1
    else
        print_success "Linting passed"
    fi
}

# Run format check
check_format() {
    print_header "Ruff Format Check"

    if ! uv run ruff format --check . --extend-exclude=migrations/versions 2>&1 | head -20; then
        print_error "Code formatting issues found"
        echo -e "${YELLOW}To fix, run: uv run ruff format .${NC}"
        return 1
    else
        print_success "Formatting correct"
    fi
}

# Run type checking
check_types() {
    print_header "MyPy Type Checking"

    if ! uv run mypy libs apps 2>&1 | head -20; then
        print_error "Type checking failed"
        echo -e "${YELLOW}Review the issues above and fix them${NC}"
        return 1
    else
        print_success "Type checking passed"
    fi
}

# Run quick tests
check_tests() {
    print_header "Running Tests"

    if ! uv run pytest --tb=short -q 2>&1 | tail -10; then
        print_error "Tests failed"
        echo -e "${YELLOW}Fix failing tests before committing${NC}"
        return 1
    else
        print_success "Tests passed"
    fi
}

# Main
main() {
    echo -e "${BLUE}Openahrush Pre-Commit Hook${NC}"
    echo "Checking code quality before commit..."

    cd "$PROJECT_ROOT"

    # Get list of staged files
    staged_files=$(get_staged_files)

    if [ -z "$staged_files" ]; then
        print_warning "No relevant files staged for commit"
        return 0
    fi

    # Run quality checks
    if has_python_files; then
        check_linting || true  # Continue even if lint fails
        check_format || true   # Continue even if format fails
        check_types || true    # Continue even if type check fails
    fi

    # Show results
    echo ""
    if [ $EXIT_STATUS -eq 0 ]; then
        print_success "All checks passed. Commit allowed."
        return 0
    else
        print_error "Code quality checks failed"
        echo ""
        echo -e "${YELLOW}Options:${NC}"
        echo "1. Fix the issues and stage the fixes"
        echo "2. Run: git commit --no-verify (bypass checks - not recommended)"
        echo "3. Run: ./scripts/lint.sh (for more details)"
        return 1
    fi
}

# Run main
main "$@"
exit $?
