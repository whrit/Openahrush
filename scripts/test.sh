#!/usr/bin/env bash

set -euo pipefail

# Openahrush test runner script
# Runs pytest with coverage and detailed reporting

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
COVERAGE_THRESHOLD=70
PYTEST_ARGS=""
FAILED_TESTS=""

print_header() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

# Check pytest is available
check_pytest() {
    if ! uv run pytest --version &>/dev/null; then
        print_error "pytest is not installed"
        return 1
    fi
}

# Parse command line arguments
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --coverage)
                PYTEST_ARGS="$PYTEST_ARGS --cov=apps --cov=libs --cov-report=term-missing"
                ;;
            --html)
                PYTEST_ARGS="$PYTEST_ARGS --html=test_results.html --self-contained-html"
                ;;
            --verbose)
                PYTEST_ARGS="$PYTEST_ARGS -v"
                ;;
            --quiet)
                PYTEST_ARGS="$PYTEST_ARGS -q"
                ;;
            --watch)
                # Note: requires pytest-watch, install with: uv pip install pytest-watch
                check_pytest_watch
                exec uv run ptw -- $PYTEST_ARGS
                ;;
            --unit)
                PYTEST_ARGS="$PYTEST_ARGS -m unit"
                ;;
            --integration)
                PYTEST_ARGS="$PYTEST_ARGS -m integration"
                ;;
            --e2e)
                PYTEST_ARGS="$PYTEST_ARGS -m e2e"
                ;;
            --no-cov)
                # Remove coverage args if they were added
                PYTEST_ARGS="${PYTEST_ARGS//--cov=*}"
                ;;
            -x|--exitfirst)
                PYTEST_ARGS="$PYTEST_ARGS -x"
                ;;
            -k)
                shift
                PYTEST_ARGS="$PYTEST_ARGS -k $1"
                ;;
            --help|-h)
                print_help
                exit 0
                ;;
            *)
                # Pass through to pytest
                PYTEST_ARGS="$PYTEST_ARGS $1"
                ;;
        esac
        shift
    done
}

# Check for pytest-watch
check_pytest_watch() {
    if ! uv run ptw --version &>/dev/null 2>&1; then
        print_error "pytest-watch not found. Install with: uv pip install pytest-watch"
        exit 1
    fi
}

# Run tests with coverage
run_tests() {
    print_header "Running Tests"

    cd "$PROJECT_ROOT"

    # Default pytest args include coverage
    if [ -z "$PYTEST_ARGS" ]; then
        PYTEST_ARGS="--cov=apps --cov=libs --cov-report=term-missing --cov-report=html"
    fi

    print_info "Running pytest with args: $PYTEST_ARGS"
    echo ""

    if uv run pytest apps libs $PYTEST_ARGS; then
        print_success "All tests passed"
        return 0
    else
        print_error "Tests failed"
        return 1
    fi
}

# Print help message
print_help() {
    cat << EOF
${BLUE}Openahrush Test Runner${NC}

${GREEN}Usage:${NC}
  $(basename "$0") [options]

${GREEN}Options:${NC}
  --coverage              Include coverage report (default)
  --html                  Generate HTML test report
  --verbose, -v           Verbose output
  --quiet, -q             Quiet output
  --watch                 Watch mode (requires pytest-watch)
  --unit                  Run only unit tests
  --integration           Run only integration tests
  --e2e                   Run only end-to-end tests
  --no-cov                Disable coverage reporting
  -x, --exitfirst         Stop on first failure
  -k PATTERN              Run tests matching pattern
  --help, -h              Show this help message

${GREEN}Examples:${NC}
  $(basename "$0")                    # Run all tests with coverage
  $(basename "$0") --verbose          # Run with verbose output
  $(basename "$0") -k test_login      # Run only tests matching 'test_login'
  $(basename "$0") --watch            # Run tests in watch mode
  $(basename "$0") --unit --coverage  # Run unit tests with coverage
  $(basename "$0") -x                 # Stop on first failure

${GREEN}Environment:${NC}
  Tests are discovered in: apps/, libs/
  Test markers: unit, integration, e2e
  Coverage threshold: ${COVERAGE_THRESHOLD}%

${GREEN}Coverage Report:${NC}
  Terminal: Printed to stdout
  HTML:     htmlcov/index.html

${YELLOW}Notes:${NC}
  - Coverage report generated in htmlcov/ directory
  - All pytest options are supported
  - Tests should use pytest.ini configuration from pyproject.toml

EOF
}

# Main execution
main() {
    echo -e "${BLUE}Openahrush Test Suite${NC}"
    echo "Project: $PROJECT_ROOT"
    echo ""

    # Check pytest
    if ! check_pytest; then
        print_error "Cannot run tests without pytest"
        return 1
    fi

    # Parse arguments
    parse_args "$@"

    # Run tests
    if run_tests; then
        print_header "Test Run Complete"
        echo -e "${GREEN}All checks passed!${NC}"

        # Show coverage info if generated
        if [ -f "$PROJECT_ROOT/htmlcov/index.html" ]; then
            echo ""
            echo -e "${BLUE}Coverage report generated: htmlcov/index.html${NC}"
        fi

        return 0
    else
        print_header "Test Run Failed"
        echo -e "${RED}Fix the failing tests before proceeding${NC}"
        return 1
    fi
}

# Run main
main "$@"
exit $?
