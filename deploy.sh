#!/bin/bash
# ============================================================================
# Quick Deployment Script for video-cut
# ============================================================================
# This script automates the deployment process with Docker Compose
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed."
        exit 1
    fi

    # Check if .env file exists
    if [ ! -f .env ]; then
        log_warning ".env file not found. Copying from template..."
        cp .env.production .env
        log_warning "Please edit .env file and update the configuration!"
        log_info "Then run this script again."
        exit 1
    fi

    log_success "Prerequisites check passed"
}

generate_jwt_secret() {
    if grep -q "your-super-secret-jwt-key" .env; then
        log_info "Generating JWT secret key..."
        JWT_SECRET=$(openssl rand -hex 32)
        sed -i "s/your-super-secret-jwt-key-change-this-in-production-32chars/$JWT_SECRET/" .env
        log_success "JWT secret key generated"
    fi
}

build_and_start() {
    log_info "Building Docker images (this may take a few minutes)..."
    docker-compose build --no-cache

    log_info "Starting services..."
    docker-compose up -d

    log_info "Waiting for services to be ready..."
    sleep 15
}

check_services() {
    log_info "Checking service status..."

    if docker-compose ps | grep -q "Up"; then
        log_success "Services are running!"
    else
        log_error "Some services failed to start. Check logs:"
        docker-compose logs
        exit 1
    fi
}

show_status() {
    echo ""
    log_success "Deployment complete! Here's what's running:"
    echo ""
    docker-compose ps
    echo ""
    log_info "Access the application at: http://localhost:8462"
    log_info "Default login: admin / admin123"
    log_warning "IMPORTANT: Change the default admin password immediately!"
    echo ""
    log_info "Useful commands:"
    echo "  View logs:       docker-compose logs -f"
    echo "  Stop services:   docker-compose down"
    echo "  Restart:         docker-compose restart"
    echo ""
}

# Main execution
main() {
    echo "=========================================="
    echo "  video-cut Docker Deployment Script"
    echo "=========================================="
    echo ""

    check_prerequisites
    generate_jwt_secret
    build_and_start
    check_services
    show_status
}

# Run main function
main
