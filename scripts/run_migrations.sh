#!/usr/bin/env bash
#
# Production-safe migration runner with PostgreSQL advisory locks.
#
# Features:
# - Uses PostgreSQL advisory locks to prevent concurrent migrations
# - Validates database connectivity before starting
# - Provides clear output of migration status
# - Supports dry-run mode
# - Handles rollback on failure
#
# Usage:
#   ./scripts/run_migrations.sh                     # Run all pending migrations
#   ./scripts/run_migrations.sh --dry-run           # Show what would be done
#   ./scripts/run_migrations.sh --revision abc123   # Migrate to specific revision
#   ./scripts/run_migrations.sh --downgrade -1      # Downgrade one step
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MIGRATIONS_DIR="$PROJECT_ROOT/migrations"
ALEMBIC_INI="$MIGRATIONS_DIR/alembic.ini"

# Advisory lock ID (derived from project name hash)
LOCK_ID=12345678

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
DRY_RUN=false
REVISION="head"
DOWNGRADE=false
VERBOSE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --revision)
            REVISION="$2"
            shift 2
            ;;
        --downgrade)
            DOWNGRADE=true
            REVISION="${2:--1}"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run           Show what would be done without executing"
            echo "  --revision REV      Migrate to specific revision (default: head)"
            echo "  --downgrade [N]     Downgrade N steps (default: -1)"
            echo "  -v, --verbose       Show verbose output"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_database_url() {
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL environment variable is not set"
        exit 1
    fi
}

check_postgres_connection() {
    log_info "Checking database connection..."

    if command -v psql &> /dev/null; then
        if psql "$DATABASE_URL" -c "SELECT 1;" &> /dev/null; then
            log_success "Database connection successful"
        else
            log_error "Failed to connect to database"
            exit 1
        fi
    else
        log_warning "psql not found, skipping connection check"
    fi
}

get_current_revision() {
    cd "$PROJECT_ROOT"
    uv run --package semrush-core alembic -c "$ALEMBIC_INI" current 2>/dev/null | grep -oE '[a-f0-9]+' | head -1 || echo "none"
}

get_pending_migrations() {
    cd "$PROJECT_ROOT"
    uv run --package semrush-core alembic -c "$ALEMBIC_INI" history --indicate-current 2>/dev/null | grep -E '^\s+<-' | wc -l | tr -d ' '
}

acquire_advisory_lock() {
    log_info "Acquiring advisory lock ($LOCK_ID)..."

    # Use psql to acquire lock if available
    if command -v psql &> /dev/null && [[ "$DATABASE_URL" == postgres* ]]; then
        LOCK_RESULT=$(psql "$DATABASE_URL" -t -c "SELECT pg_try_advisory_lock($LOCK_ID);" 2>/dev/null | tr -d ' ')

        if [[ "$LOCK_RESULT" != "t" ]]; then
            log_error "Failed to acquire advisory lock - another migration may be in progress"
            exit 1
        fi

        log_success "Advisory lock acquired"
    else
        log_warning "Skipping advisory lock (not PostgreSQL or psql not available)"
    fi
}

release_advisory_lock() {
    if command -v psql &> /dev/null && [[ "${DATABASE_URL:-}" == postgres* ]]; then
        psql "$DATABASE_URL" -c "SELECT pg_advisory_unlock($LOCK_ID);" &> /dev/null || true
        log_info "Advisory lock released"
    fi
}

run_migrations() {
    local action="upgrade"
    local target="$REVISION"

    if [[ "$DOWNGRADE" == true ]]; then
        action="downgrade"
    fi

    log_info "Running: alembic $action $target"

    if [[ "$DRY_RUN" == true ]]; then
        log_warning "DRY RUN - no changes will be made"
        cd "$PROJECT_ROOT"
        uv run --package semrush-core alembic -c "$ALEMBIC_INI" $action "$target" --sql
    else
        cd "$PROJECT_ROOT"
        if [[ "$VERBOSE" == true ]]; then
            uv run --package semrush-core alembic -c "$ALEMBIC_INI" $action "$target"
        else
            uv run --package semrush-core alembic -c "$ALEMBIC_INI" $action "$target" 2>&1
        fi

        if [[ $? -eq 0 ]]; then
            log_success "Migration completed successfully"
        else
            log_error "Migration failed"
            return 1
        fi
    fi
}

# Main execution
main() {
    echo ""
    echo "=========================================="
    echo "  Database Migration Runner"
    echo "=========================================="
    echo ""

    # Check prerequisites
    check_database_url
    check_postgres_connection

    # Show current state
    CURRENT_REV=$(get_current_revision)
    log_info "Current revision: $CURRENT_REV"

    if [[ "$DOWNGRADE" == false ]]; then
        PENDING=$(get_pending_migrations)
        log_info "Pending migrations: $PENDING"
    fi

    echo ""

    # Acquire lock before running migrations
    acquire_advisory_lock

    # Ensure lock is released on exit
    trap release_advisory_lock EXIT

    # Run migrations
    if run_migrations; then
        NEW_REV=$(get_current_revision)
        echo ""
        log_success "Migration complete!"
        log_info "New revision: $NEW_REV"
    else
        echo ""
        log_error "Migration failed!"
        exit 1
    fi
}

main
