#!/bin/bash

# MV Face Recognition - Fly.io Deployment Script
# This script automates the deployment process while respecting CLAUDE.md constraints

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  MV Face Recognition - Fly.io Deploy  ${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Configuration
BACKEND_APP="mv-face-recognition-backend"
FRONTEND_APP="mv-face-recognition-frontend"
REGION="sjc"

# Parse command line arguments
DEPLOY_BACKEND=true
DEPLOY_FRONTEND=true
CREATE_VOLUMES=false
SKIP_BUILD=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend-only)
            DEPLOY_BACKEND=true
            DEPLOY_FRONTEND=false
            shift
            ;;
        --frontend-only)
            DEPLOY_BACKEND=false
            DEPLOY_FRONTEND=true
            shift
            ;;
        --create-volumes)
            CREATE_VOLUMES=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --backend-only      Deploy only the backend service"
            echo "  --frontend-only     Deploy only the frontend service"
            echo "  --create-volumes    Create Fly.io volumes for persistent storage"
            echo "  --skip-build        Skip Docker build (use existing images)"
            echo "  --dry-run           Show what would be done without executing"
            echo "  --help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                          # Deploy both backend and frontend"
            echo "  $0 --backend-only           # Deploy only backend"
            echo "  $0 --create-volumes         # Create volumes and deploy everything"
            echo "  $0 --dry-run                # Show deployment plan"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Dry run mode
if [ "$DRY_RUN" = true ]; then
    print_info "DRY RUN MODE - No changes will be made"
    echo ""
fi

print_header

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."
    
    # Check if flyctl is installed
    if ! command -v fly &> /dev/null; then
        print_error "flyctl is not installed. Please install it first:"
        print_info "  curl -L https://fly.io/install.sh | sh"
        exit 1
    fi
    
    # Check if user is authenticated
    if ! fly auth whoami &> /dev/null; then
        print_error "Not authenticated with Fly.io. Please run:"
        print_info "  fly auth login"
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Check critical files exist (respecting CLAUDE.md constraints)
    print_info "Checking critical files..."
    
    if [ ! -f "metadata/contestant_info.csv" ]; then
        print_error "CRITICAL: metadata/contestant_info.csv not found!"
        print_error "This file is essential for the system (see CLAUDE.md)"
        exit 1
    fi
    
    if [ ! -f "config.json" ]; then
        print_error "config.json not found!"
        exit 1
    fi
    
    # Check if contestant embeddings exist
    if [ ! -d "source/photo/contestants" ]; then
        print_error "source/photo/contestants directory not found!"
        print_error "Contestant embeddings are required for face recognition"
        exit 1
    fi
    
    contestant_count=$(find source/photo/contestants -mindepth 1 -maxdepth 1 -type d | wc -l)
    if [ "$contestant_count" -lt 90 ]; then
        print_warning "Only $contestant_count contestant directories found (expected 95+)"
    else
        print_info "Found $contestant_count contestant directories"
    fi
    
    print_success "Prerequisites check passed"
}

# Create Fly.io volumes
create_volumes() {
    if [ "$CREATE_VOLUMES" = true ]; then
        print_step "Creating Fly.io volumes..."
        
        # Calculate required volume sizes based on existing data
        videos_size=$(du -sm source/videos processed_videos 2>/dev/null | awk '{sum += $1} END {print int(sum/1024) + 10}')
        embeddings_size=10  # Embeddings are small
        metadata_size=5     # Metadata is small
        chromadb_size=10    # ChromaDB storage
        
        print_info "Calculated volume sizes:"
        print_info "  Videos: ${videos_size}GB"
        print_info "  Embeddings: ${embeddings_size}GB" 
        print_info "  Metadata: ${metadata_size}GB"
        print_info "  ChromaDB: ${chromadb_size}GB"
        
        if [ "$DRY_RUN" = false ]; then
            # Create volumes if they don't exist
            volumes=(
                "mv_videos_vol:${videos_size}"
                "mv_embeddings_vol:${embeddings_size}"
                "mv_metadata_vol:${metadata_size}"
                "mv_chromadb_vol:${chromadb_size}"
            )
            
            for volume_spec in "${volumes[@]}"; do
                volume_name=$(echo $volume_spec | cut -d: -f1)
                volume_size=$(echo $volume_spec | cut -d: -f2)
                
                if ! fly volumes list | grep -q "$volume_name"; then
                    print_info "Creating volume: $volume_name (${volume_size}GB)"
                    fly volumes create "$volume_name" --region "$REGION" --size "$volume_size" --yes
                else
                    print_info "Volume $volume_name already exists"
                fi
            done
        else
            print_info "Would create volumes: mv_videos_vol, mv_embeddings_vol, mv_metadata_vol, mv_chromadb_vol"
        fi
        
        print_success "Volume creation completed"
    fi
}

# Deploy backend
deploy_backend() {
    if [ "$DEPLOY_BACKEND" = true ]; then
        print_step "Deploying backend application..."
        
        if [ "$DRY_RUN" = false ]; then
            # Check if app exists, create if not
            if ! fly apps list | grep -q "$BACKEND_APP"; then
                print_info "Creating backend app: $BACKEND_APP"
                fly apps create "$BACKEND_APP" --org personal
            fi
            
            # Deploy the backend with GPU support
            print_info "Deploying backend with GPU acceleration (NVIDIA A10)"
            print_info "Using configuration: fly.backend.toml"
            fly deploy --config fly.backend.toml
            
            # Set up secrets if needed
            print_info "Setting up backend secrets..."
            fly secrets set --app "$BACKEND_APP" \
                SECRET_KEY="$(openssl rand -hex 32)" \
                ENVIRONMENT="production"
                
        else
            print_info "Would deploy backend app: $BACKEND_APP"
            print_info "Would set environment secrets"
        fi
        
        print_success "Backend deployment completed"
    fi
}

# Deploy frontend
deploy_frontend() {
    if [ "$DEPLOY_FRONTEND" = true ]; then
        print_step "Deploying frontend application..."
        
        if [ "$DRY_RUN" = false ]; then
            # Check if app exists, create if not
            if ! fly apps list | grep -q "$FRONTEND_APP"; then
                print_info "Creating frontend app: $FRONTEND_APP"
                fly apps create "$FRONTEND_APP" --org personal
            fi
            
            # Deploy the frontend
            print_info "Deploying frontend with configuration fly.frontend.toml"
            fly deploy --config fly.frontend.toml
            
            # Set up frontend secrets
            print_info "Setting up frontend environment..."
            fly secrets set --app "$FRONTEND_APP" \
                VITE_API_BASE_URL="https://${BACKEND_APP}.fly.dev"
                
        else
            print_info "Would deploy frontend app: $FRONTEND_APP"
            print_info "Would set API URL: https://${BACKEND_APP}.fly.dev"
        fi
        
        print_success "Frontend deployment completed"
    fi
}

# Post-deployment data migration
migrate_data() {
    if [ "$DRY_RUN" = false ] && [ "$DEPLOY_BACKEND" = true ]; then
        print_step "Migrating critical data to production..."
        
        print_info "Connecting to backend for data migration..."
        
        # Create a migration script
        cat > migrate_data.sh << 'EOF'
#!/bin/bash
# Data migration script for Fly.io deployment

echo "Starting data migration..."

# Copy critical metadata (respecting CLAUDE.md constraints)
if [ -f "/app/metadata/contestant_info.csv" ]; then
    cp /app/metadata/contestant_info.csv /data/metadata/
    echo "✓ Copied contestant_info.csv"
else
    echo "✗ ERROR: contestant_info.csv not found!"
    exit 1
fi

# Copy embeddings if they exist in the container
if [ -d "/app/source/photo/contestants" ]; then
    cp -r /app/source/photo/contestants/* /data/embeddings/contestants/ 2>/dev/null || echo "Embeddings will be uploaded separately"
fi

# Initialize ChromaDB
if [ -f "/app/fix_embeddings.py" ]; then
    cd /app && python fix_embeddings.py --validate
    echo "✓ ChromaDB validation completed"
fi

echo "Data migration completed"
EOF
        
        # Execute migration on the backend machine
        fly ssh console --app "$BACKEND_APP" < migrate_data.sh
        
        # Clean up
        rm migrate_data.sh
        
        print_success "Data migration completed"
    else
        print_info "Skipping data migration (dry run or backend not deployed)"
    fi
}

# Validate deployment
validate_deployment() {
    print_step "Validating deployment..."
    
    if [ "$DRY_RUN" = false ]; then
        if [ "$DEPLOY_BACKEND" = true ]; then
            print_info "Checking backend health..."
            backend_url="https://${BACKEND_APP}.fly.dev"
            
            # Wait for deployment to be ready
            sleep 30
            
            if curl -f "${backend_url}/health" > /dev/null 2>&1; then
                print_success "Backend is healthy: $backend_url"
            else
                print_warning "Backend health check failed, but it may still be starting up"
                print_info "Check logs with: fly logs --app $BACKEND_APP"
            fi
        fi
        
        if [ "$DEPLOY_FRONTEND" = true ]; then
            print_info "Checking frontend..."
            frontend_url="https://${FRONTEND_APP}.fly.dev"
            
            if curl -f "$frontend_url" > /dev/null 2>&1; then
                print_success "Frontend is accessible: $frontend_url"
            else
                print_warning "Frontend not accessible yet, but it may still be starting up"
                print_info "Check logs with: fly logs --app $FRONTEND_APP"
            fi
        fi
    else
        print_info "Would validate:"
        if [ "$DEPLOY_BACKEND" = true ]; then
            print_info "  Backend: https://${BACKEND_APP}.fly.dev/health"
        fi
        if [ "$DEPLOY_FRONTEND" = true ]; then
            print_info "  Frontend: https://${FRONTEND_APP}.fly.dev"
        fi
    fi
}

# Print final information
print_final_info() {
    print_success "Deployment process completed!"
    echo ""
    print_info "Application URLs:"
    
    if [ "$DEPLOY_BACKEND" = true ]; then
        echo -e "  Backend API: ${GREEN}https://${BACKEND_APP}.fly.dev${NC}"
        echo -e "  Health Check: ${GREEN}https://${BACKEND_APP}.fly.dev/health${NC}"
    fi
    
    if [ "$DEPLOY_FRONTEND" = true ]; then
        echo -e "  Frontend: ${GREEN}https://${FRONTEND_APP}.fly.dev${NC}"
    fi
    
    echo ""
    print_info "Management commands:"
    echo -e "  View logs: ${BLUE}fly logs --app ${BACKEND_APP}${NC}"
    echo -e "  SSH access: ${BLUE}fly ssh console --app ${BACKEND_APP}${NC}"
    echo -e "  Scale app: ${BLUE}fly scale count 2 --app ${BACKEND_APP}${NC}"
    echo -e "  Monitor status: ${BLUE}fly status --app ${BACKEND_APP}${NC}"
    
    if [ "$CREATE_VOLUMES" = true ]; then
        echo ""
        print_warning "IMPORTANT: Critical data migration required!"
        print_info "Upload your video files and embeddings to the production volumes:"
        print_info "  1. Use 'fly ssh console --app $BACKEND_APP' to access the machine"
        print_info "  2. Copy data to /data/videos/, /data/embeddings/, etc."
        print_info "  3. Run embedding refresh: python /app/fix_embeddings.py --all --force"
    fi
}

# Main execution
main() {
    check_prerequisites
    create_volumes
    deploy_backend
    deploy_frontend
    migrate_data
    validate_deployment
    print_final_info
}

# Run main function
main 