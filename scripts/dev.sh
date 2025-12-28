#!/usr/bin/env bash

set -euo pipefail

# Openahrush development environment management script
# Provides convenient commands for Docker Compose operations, migrations, and container access

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$PROJECT_ROOT/infra/compose"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_PROJECT_NAME="openahrush"
API_CONTAINER="${COMPOSE_PROJECT_NAME}-api"
DB_CONTAINER="${COMPOSE_PROJECT_NAME}-postgres"

# Helper functions
print_help() {
    cat << EOF
${BLUE}Openahrush Development Environment${NC}

${GREEN}Usage:${NC}
  $(basename "$0") <command> [options]

${GREEN}Commands:${NC}
  up                  Start all services (postgres, redis, minio, api)
  down                Stop all services
  restart             Restart all services (down + up)
  logs                Stream logs from all services (Ctrl+C to exit)
  logs <service>      Stream logs from specific service (postgres, redis, minio, api)
  ps                  Show running containers
  status              Show detailed status of all services

  shell               Open bash shell in API container
  db-shell            Open psql shell in Postgres container
  redis-cli           Open Redis CLI in Redis container

  migrate             Run pending database migrations
  migrate-downgrade   Rollback database to previous revision

  up-clickhouse       Start services with ClickHouse (Common Crawl)
  down-clickhouse     Stop services including ClickHouse

  clean               Remove stopped containers and volumes
  clean-hard          Remove all containers, volumes, and images (DESTRUCTIVE)

  rebuild             Rebuild API container without cache
  env-setup           Create .env file from .env.example

  help                Show this help message

${GREEN}Examples:${NC}
  $(basename "$0") up                    # Start dev environment
  $(basename "$0") logs api              # Watch API logs
  $(basename "$0") shell                 # Connect to API container
  $(basename "$0") migrate               # Run migrations
  $(basename "$0") up-clickhouse         # Start with ClickHouse
  $(basename "$0") rebuild               # Rebuild API image

${GREEN}Environment:${NC}
  DATABASE_URL        Postgres connection string (set in .env)
  REDIS_URL           Redis connection string (set in .env)
  JWT_SECRET          JWT signing secret (set in .env)

${YELLOW}Notes:${NC}
  - All services are configured with health checks
  - Data persists in Docker volumes (postgres_data, redis_data, minio_data)
  - MinIO console available at http://localhost:9001
  - API server runs at http://localhost:8000
  - Use 'down' and 'clean' to fully reset the environment

EOF
}

# Check if docker compose is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker is not installed or not in PATH${NC}" >&2
        return 1
    fi

    if ! docker compose version &> /dev/null; then
        echo -e "${RED}Error: Docker Compose is not available${NC}" >&2
        return 1
    fi
}

# Create .env file if it doesn't exist
setup_env() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        if [ -f "$PROJECT_ROOT/.env.example" ]; then
            echo -e "${YELLOW}Creating .env from .env.example...${NC}"
            cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
            echo -e "${GREEN}Created .env file. Please review and update secrets as needed.${NC}"
        else
            echo -e "${YELLOW}Warning: .env.example not found, skipping .env setup${NC}"
        fi
    fi
}

# Start services
up() {
    echo -e "${BLUE}Starting Openahrush services...${NC}"
    check_docker || return 1
    setup_env

    cd "$COMPOSE_DIR"
    docker compose -p "$COMPOSE_PROJECT_NAME" up -d

    echo -e "${GREEN}Services starting...${NC}"
    echo ""
    echo -e "${BLUE}Service endpoints:${NC}"
    echo "  API:           http://localhost:8000"
    echo "  MinIO console: http://localhost:9001 (minioadmin/minioadmin)"
    echo "  Postgres:      localhost:5432 (semrush/semrush)"
    echo "  Redis:         localhost:6379"
    echo ""
    echo -e "${YELLOW}Run '$(basename "$0") logs' to watch startup progress${NC}"
    echo -e "${YELLOW}Run '$(basename "$0") migrate' after services are healthy${NC}"
}

# Stop services
down() {
    echo -e "${BLUE}Stopping Openahrush services...${NC}"
    check_docker || return 1

    cd "$COMPOSE_DIR"
    docker compose -p "$COMPOSE_PROJECT_NAME" down

    echo -e "${GREEN}Services stopped${NC}"
}

# Restart services
restart() {
    down
    sleep 2
    up
}

# View logs
logs() {
    check_docker || return 1

    cd "$COMPOSE_DIR"

    if [ $# -eq 0 ]; then
        echo -e "${BLUE}Streaming logs from all services (Ctrl+C to exit)...${NC}"
        docker compose -p "$COMPOSE_PROJECT_NAME" logs -f
    else
        service="$1"
        echo -e "${BLUE}Streaming logs from $service (Ctrl+C to exit)...${NC}"
        docker compose -p "$COMPOSE_PROJECT_NAME" logs -f "$service"
    fi
}

# Show container status
ps() {
    check_docker || return 1

    cd "$COMPOSE_DIR"
    docker compose -p "$COMPOSE_PROJECT_NAME" ps
}

# Show detailed status
status() {
    echo -e "${BLUE}Openahrush Service Status${NC}"
    echo ""

    check_docker || return 1

    cd "$COMPOSE_DIR"
    docker compose -p "$COMPOSE_PROJECT_NAME" ps

    echo ""
    echo -e "${BLUE}Health checks:${NC}"

    # Check each service
    for service in postgres redis minio api; do
        if docker inspect "${COMPOSE_PROJECT_NAME}-${service}" &>/dev/null 2>&1; then
            state=$(docker inspect "${COMPOSE_PROJECT_NAME}-${service}" --format='{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
            if [ "$state" = "healthy" ]; then
                echo -e "  ${GREEN}✓${NC} $service ($state)"
            else
                echo -e "  ${YELLOW}!${NC} $service ($state)"
            fi
        fi
    done
}

# Open shell in API container
shell() {
    echo -e "${BLUE}Opening shell in API container...${NC}"
    check_docker || return 1

    docker exec -it "$API_CONTAINER" /bin/bash
}

# Open psql in database container
db_shell() {
    echo -e "${BLUE}Opening psql session...${NC}"
    check_docker || return 1

    docker exec -it "$DB_CONTAINER" psql -U semrush -d semrush
}

# Open Redis CLI
redis_shell() {
    echo -e "${BLUE}Opening Redis CLI...${NC}"
    check_docker || return 1

    docker exec -it "${COMPOSE_PROJECT_NAME}-redis" redis-cli
}

# Run migrations
migrate() {
    echo -e "${BLUE}Running database migrations...${NC}"
    check_docker || return 1

    docker exec -it "$API_CONTAINER" \
        uv run --package semrush-core alembic -c migrations/alembic.ini upgrade head

    echo -e "${GREEN}Migrations completed${NC}"
}

# Rollback migrations
migrate_downgrade() {
    echo -e "${BLUE}Rolling back database to previous revision...${NC}"
    check_docker || return 1

    docker exec -it "$API_CONTAINER" \
        uv run --package semrush-core alembic -c migrations/alembic.ini downgrade -1

    echo -e "${GREEN}Rollback completed${NC}"
}

# Start with ClickHouse
up_clickhouse() {
    echo -e "${BLUE}Starting Openahrush with ClickHouse...${NC}"
    check_docker || return 1
    setup_env

    cd "$COMPOSE_DIR"
    docker compose -p "$COMPOSE_PROJECT_NAME" \
        -f docker-compose.yml \
        -f docker-compose.clickhouse.yml \
        up -d

    echo -e "${GREEN}Services with ClickHouse starting...${NC}"
    echo ""
    echo -e "${BLUE}Service endpoints:${NC}"
    echo "  API:           http://localhost:8000"
    echo "  MinIO console: http://localhost:9001 (minioadmin/minioadmin)"
    echo "  ClickHouse:    http://localhost:8123 (default/default)"
    echo "  Postgres:      localhost:5432 (semrush/semrush)"
    echo "  Redis:         localhost:6379"
    echo ""
    echo -e "${YELLOW}Run '$(basename "$0") logs' to watch startup progress${NC}"
}

# Stop with ClickHouse
down_clickhouse() {
    echo -e "${BLUE}Stopping Openahrush with ClickHouse...${NC}"
    check_docker || return 1

    cd "$COMPOSE_DIR"
    docker compose -p "$COMPOSE_PROJECT_NAME" \
        -f docker-compose.yml \
        -f docker-compose.clickhouse.yml \
        down

    echo -e "${GREEN}Services stopped${NC}"
}

# Clean up stopped containers
clean() {
    echo -e "${YELLOW}Removing stopped containers...${NC}"
    check_docker || return 1

    docker compose -p "$COMPOSE_PROJECT_NAME" down --remove-orphans

    echo -e "${GREEN}Cleanup completed${NC}"
}

# Destructive cleanup
clean_hard() {
    echo -e "${RED}WARNING: This will remove all containers, volumes, and data!${NC}"
    echo -e "${YELLOW}Press Ctrl+C to cancel, or wait 5 seconds to continue...${NC}"
    sleep 5

    check_docker || return 1

    echo -e "${BLUE}Removing all containers, volumes, and data...${NC}"

    cd "$COMPOSE_DIR"
    docker compose -p "$COMPOSE_PROJECT_NAME" \
        -f docker-compose.yml \
        -f docker-compose.clickhouse.yml \
        down -v --remove-orphans

    docker system prune -f

    echo -e "${GREEN}Hard cleanup completed. All data removed.${NC}"
}

# Rebuild API image
rebuild() {
    echo -e "${BLUE}Rebuilding API container without cache...${NC}"
    check_docker || return 1

    cd "$COMPOSE_DIR"
    docker compose -p "$COMPOSE_PROJECT_NAME" build --no-cache api

    echo -e "${GREEN}Rebuild completed${NC}"
    echo -e "${YELLOW}Run '$(basename "$0") restart' to use the new image${NC}"
}

# Setup environment files
env_setup() {
    setup_env
}

# Main command dispatcher
main() {
    if [ $# -eq 0 ]; then
        print_help
        return 0
    fi

    case "$1" in
        up)
            up
            ;;
        down)
            down
            ;;
        restart)
            restart
            ;;
        logs)
            shift || true
            logs "$@"
            ;;
        ps)
            ps
            ;;
        status)
            status
            ;;
        shell)
            shell
            ;;
        db-shell)
            db_shell
            ;;
        redis-cli)
            redis_shell
            ;;
        migrate)
            migrate
            ;;
        migrate-downgrade)
            migrate_downgrade
            ;;
        up-clickhouse)
            up_clickhouse
            ;;
        down-clickhouse)
            down_clickhouse
            ;;
        clean)
            clean
            ;;
        clean-hard)
            clean_hard
            ;;
        rebuild)
            rebuild
            ;;
        env-setup)
            env_setup
            ;;
        help|-h|--help)
            print_help
            ;;
        *)
            echo -e "${RED}Error: Unknown command '$1'${NC}" >&2
            echo ""
            print_help
            return 1
            ;;
    esac
}

main "$@"
