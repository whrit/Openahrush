#!/usr/bin/env bash

set -euo pipefail

# Openahrush code quality script
# Runs ruff (format + lint) and mypy type checking

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
errors=0
warnings=0

print_header() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((errors++))
}

print_warning() {
    echo -e "${YELLOW}! $1${NC}"
    ((warnings++))
}

# Check ruff is installed
check_ruff() {
    if ! uv run ruff --version &>/dev/null; then
        print_error "ruff is not installed"
        return 1
    fi
}

# Check mypy is installed
check_mypy() {
    if ! uv run mypy --version &>/dev/null; then
        print_error "mypy is not installed"
        return 1
    fi
}

# Run ruff check
run_ruff_check() {
    print_header "Ruff Linting"

    if ! uv run ruff check . --extend-exclude=migrations/versions 2>&1; then
        print_error "Ruff linting found issues"
        return 1
    else
        print_success "All files pass ruff linting"
    fi
}

# Run ruff format check (no fixes)
run_ruff_format() {
    print_header "Ruff Format Check"

    if ! uv run ruff format --check . --extend-exclude=migrations/versions 2>&1; then
        print_error "Code formatting issues found"
        echo ""
        echo -e "${YELLOW}To fix formatting, run:${NC}"
        echo "  uv run ruff format ."
        return 1
    else
        print_success "All files are properly formatted"
    fi
}

# Run mypy type checking
run_mypy() {
    print_header "MyPy Type Checking"

    if ! uv run mypy libs apps 2>&1; then
        print_error "Type checking failed"
        return 1
    else
        print_success "Type checking passed"
    fi
}

# Show summary
print_summary() {
    print_header "Summary"

    if [ $errors -eq 0 ]; then
        echo -e "${GREEN}All checks passed!${NC}"
        return 0
    else
        echo -e "${RED}Found $errors error(s)${NC}"
        if [ $warnings -gt 0 ]; then
            echo -e "${YELLOW}Found $warnings warning(s)${NC}"
        fi
        return 1
    fi
}

# Main execution
main() {
    cd "$PROJECT_ROOT"

    echo -e "${BLUE}Openahrush Code Quality Check${NC}"
    echo "Project: $PROJECT_ROOT"

    # Check tools
    if ! check_ruff; then
        print_error "Cannot continue without ruff"
        return 1
    fi

    if ! check_mypy; then
        print_error "Cannot continue without mypy"
        return 1
    fi

    echo -e "${YELLOW}Running code quality checks...${NC}"

    # Run checks
    if ! run_ruff_check; then
        ((errors++))
    fi

    if ! run_ruff_format; then
        ((errors++))
    fi

    if ! run_mypy; then
        ((errors++))
    fi

    # Print summary
    print_summary
}

# Run main
main "$@"
exit $?
