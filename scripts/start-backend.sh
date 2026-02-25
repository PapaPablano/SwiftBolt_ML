#!/bin/bash

# SwiftBolt Backend Docker Management Script
# Usage: ./start-backend.sh [start|stop|restart|logs|status]

set -e

CONTAINER_NAME="swiftbolt-ml-backend"
COMPOSE_FILE="docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if docker is running
check_docker() {
    if ! docker ps > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker Desktop."
        exit 1
    fi
}

# Start the backend
start_backend() {
    print_header "Starting SwiftBolt Backend"

    check_docker

    if docker-compose ps | grep -q "swiftbolt-ml-backend.*Up"; then
        print_info "Backend is already running"
        print_info "Access at: http://localhost:8000"
        print_info "View logs: docker-compose logs -f backend"
        return 0
    fi

    print_info "Building Docker image..."
    docker-compose build

    print_info "Starting container..."
    docker-compose up -d

    # Wait for health check
    print_info "Waiting for backend to be healthy..."
    sleep 3

    if docker-compose ps | grep -q "swiftbolt-ml-backend.*Up.*healthy"; then
        print_success "Backend is running and healthy!"
        print_info "Access at: http://localhost:8000"
        print_info "View logs: docker-compose logs -f backend"
        print_info "Stop backend: ./start-backend.sh stop"
    else
        print_error "Backend failed to start. Check logs:"
        docker-compose logs backend
        exit 1
    fi
}

# Stop the backend
stop_backend() {
    print_header "Stopping SwiftBolt Backend"

    if ! docker-compose ps | grep -q "swiftbolt-ml-backend"; then
        print_info "Backend is not running"
        return 0
    fi

    print_info "Stopping container..."
    docker-compose down

    print_success "Backend stopped"
}

# Restart the backend
restart_backend() {
    print_header "Restarting SwiftBolt Backend"

    stop_backend
    sleep 2
    start_backend
}

# Show logs
show_logs() {
    check_docker

    print_header "SwiftBolt Backend Logs"
    print_info "Press Ctrl+C to exit"

    docker-compose logs -f backend
}

# Show status
show_status() {
    print_header "SwiftBolt Backend Status"

    check_docker

    if docker-compose ps | grep -q "swiftbolt-ml-backend.*Up"; then
        print_success "Backend is running"
        echo ""
        print_info "Details:"
        docker-compose ps backend
        echo ""
        print_info "Health check:"
        curl -s http://localhost:8000/health | python3 -m json.tool || echo "Health check endpoint not responding"
        echo ""
        print_info "Real-time charts API:"
        curl -s http://localhost:8000/api/v1/health/realtime-charts | python3 -m json.tool || echo "Charts API not responding"
    else
        print_error "Backend is not running"
        print_info "Start with: ./start-backend.sh start"
    fi
}

# Show help
show_help() {
    echo "SwiftBolt Backend Docker Management Script"
    echo ""
    echo "Usage: ./start-backend.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start       Start the backend container"
    echo "  stop        Stop the backend container"
    echo "  restart     Restart the backend container"
    echo "  logs        Show backend logs (live)"
    echo "  status      Show backend status and health"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./start-backend.sh start     # Start the backend"
    echo "  ./start-backend.sh status    # Check if backend is running"
    echo "  ./start-backend.sh logs      # View logs in real-time"
    echo ""
    echo "Access the backend at: http://localhost:8000"
    echo "Real-time charts API: http://localhost:8000/api/v1/health/realtime-charts"
}

# Main
main() {
    local command="${1:-start}"

    case "$command" in
        start)
            start_backend
            ;;
        stop)
            stop_backend
            ;;
        restart)
            restart_backend
            ;;
        logs)
            show_logs
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main
main "$@"
