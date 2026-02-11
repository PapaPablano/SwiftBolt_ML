#!/bin/bash
# Production System Startup Script
# Launches the KDJ-Enhanced ML Analysis Platform

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Main startup function
main() {
    print_header "🚀 ML Analysis Platform - KDJ Enhanced Startup"
    echo "=================================================="
    
    # Check if we're in the right directory
    if [[ -d "main_production_system" ]]; then
        # Running from root directory
        SCRIPT_DIR="main_production_system"
        ROOT_DIR="."
    elif [[ -f "main_app.py" && -d "core" ]]; then
        # Running from main_production_system directory
        SCRIPT_DIR="."
        ROOT_DIR=".."
    else
        print_error "Invalid directory!"
        print_error "Please run this script from either:"
        print_error "  - ml_analysis_platform/ (root directory)"
        print_error "  - ml_analysis_platform/main_production_system/"
        exit 1
    fi
    
    # Check for required model file
    MODEL_PATH="$ROOT_DIR/xgboost_tuned_model.pkl"
    if [[ ! -f "$MODEL_PATH" ]]; then
        print_warning "xgboost_tuned_model.pkl not found at $MODEL_PATH"
        print_warning "Dashboard will start but model loading may fail"
    else
        MODEL_SIZE=$(du -h "$MODEL_PATH" | cut -f1)
        print_status "Found XGBoost model: $MODEL_SIZE"
    fi
    
    # Check Python environment
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1)
        print_status "Python detected: $PYTHON_VERSION"
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1)
        print_status "Python detected: $PYTHON_VERSION"
        PYTHON_CMD="python"
    else
        print_error "Python not found! Please install Python 3.8+"
        exit 1
    fi
    
    # Check for virtual environment
    VENV_PATH="$ROOT_DIR/.venv"
    if [[ -d "$VENV_PATH" ]]; then
        print_status "Virtual environment found: $VENV_PATH"
        source "$VENV_PATH/bin/activate"
        print_status "Activated virtual environment"
    else
        print_warning "No virtual environment found ($VENV_PATH)"
        print_warning "Consider creating one: python -m venv .venv"
    fi
    
    # Check required packages
    print_status "Checking required packages..."
    
    REQUIRED_PACKAGES=("streamlit" "pandas" "numpy" "scikit-learn" "xgboost" "plotly")
    MISSING_PACKAGES=()
    
    for package in "${REQUIRED_PACKAGES[@]}"; do
        if $PYTHON_CMD -c "import $package" &> /dev/null; then
            print_status "✓ $package"
        else
            print_warning "✗ $package (missing)"
            MISSING_PACKAGES+=("$package")
        fi
    done
    
    # Install missing packages
    if [[ ${#MISSING_PACKAGES[@]} -gt 0 ]]; then
        print_warning "Installing missing packages..."
        pip install "${MISSING_PACKAGES[@]}"
    fi
    
    # Create directories if they don't exist
    mkdir -p "$SCRIPT_DIR/logs"
    mkdir -p "$SCRIPT_DIR/backups"
    mkdir -p "$ROOT_DIR/monitoring_reports"
    
    # Parse command line arguments
    MODE="dashboard"
    DATA_FILE=""
    if [[ "$SCRIPT_DIR" == "." ]]; then
        CONFIG_FILE="config/production_config.json"
    else
        CONFIG_FILE="$SCRIPT_DIR/config/production_config.json"
    fi
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --mode)
                MODE="$2"
                shift 2
                ;;
            --data)
                DATA_FILE="$2"
                shift 2
                ;;
            --config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Launch based on mode
    case $MODE in
        "dashboard")
            launch_dashboard
            ;;
        "train")
            launch_training "$DATA_FILE"
            ;;
        "predict")
            launch_prediction "$DATA_FILE"
            ;;
        "monitor")
            launch_monitoring
            ;;
        "status")
            show_status
            ;;
        *)
            print_error "Invalid mode: $MODE"
            show_help
            exit 1
            ;;
    esac
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --mode MODE     Operation mode: dashboard, train, predict, monitor, status (default: dashboard)"
    echo "  --data FILE     Data file path (required for train/predict modes)"
    echo "  --config FILE   Configuration file path (default: main_production_system/config/production_config.json)"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Start dashboard"
    echo "  $0 --mode train --data CRWD_data.csv # Train model"
    echo "  $0 --mode predict --data test.csv    # Make predictions"
    echo "  $0 --mode monitor                    # Run monitoring check"
    echo "  $0 --mode status                     # Show system status"
}

# Function to launch dashboard
launch_dashboard() {
    print_header "🌐 Starting Dashboard..."
    
    print_status "Dashboard will be available at: http://localhost:8501"
    print_status "Use Ctrl+C to stop the dashboard"
    
    cd "$SCRIPT_DIR"
    
    # Try Streamlit first, fallback to direct Python
    if command -v streamlit &> /dev/null; then
        streamlit run dashboard/main_dashboard.py --server.port 8501 --server.headless true
    else
        print_warning "Streamlit command not found, trying direct Python execution"
        $PYTHON_CMD main_app.py --mode dashboard --config "$CONFIG_FILE"
    fi
}

# Function to launch training
launch_training() {
    local data_file="$1"
    
    if [[ -z "$data_file" ]]; then
        print_error "Data file required for training mode"
        print_error "Usage: $0 --mode train --data your_data.csv"
        exit 1
    fi
    
    if [[ ! -f "$data_file" ]]; then
        print_error "Data file not found: $data_file"
        exit 1
    fi
    
    print_header "🎯 Starting Model Training..."
    print_status "Training data: $data_file"
    
    cd "$SCRIPT_DIR"
    
    if [[ "$SCRIPT_DIR" == "." ]]; then
        # Running from main_production_system
        $PYTHON_CMD main_app.py --mode train --data "$ROOT_DIR/$data_file" --config "$CONFIG_FILE"
    else
        # Running from root
        $PYTHON_CMD main_app.py --mode train --data "$data_file" --config "$CONFIG_FILE"
    fi
}

# Function to launch prediction
launch_prediction() {
    local data_file="$1"
    
    if [[ -z "$data_file" ]]; then
        print_error "Data file required for prediction mode"
        print_error "Usage: $0 --mode predict --data your_data.csv"
        exit 1
    fi
    
    if [[ ! -f "$data_file" ]]; then
        print_error "Data file not found: $data_file"
        exit 1
    fi
    
    print_header "🔮 Making Predictions..."
    print_status "Input data: $data_file"
    
    OUTPUT_FILE="prediction_results_$(date +%Y%m%d_%H%M%S).json"
    print_status "Output will be saved to: $OUTPUT_FILE"
    
    cd "$SCRIPT_DIR"
    
    if [[ "$SCRIPT_DIR" == "." ]]; then
        # Running from main_production_system
        $PYTHON_CMD main_app.py --mode predict --data "$ROOT_DIR/$data_file" --output "$ROOT_DIR/$OUTPUT_FILE" --config "$CONFIG_FILE"
    else
        # Running from root
        $PYTHON_CMD main_app.py --mode predict --data "$data_file" --output "$OUTPUT_FILE" --config "$CONFIG_FILE"
    fi
}

# Function to launch monitoring
launch_monitoring() {
    print_header "🔍 Running Monitoring Check..."
    
    cd "$SCRIPT_DIR"
    $PYTHON_CMD main_app.py --mode monitor --config "$CONFIG_FILE"
}

# Function to show status
show_status() {
    print_header "📊 System Status Check..."
    
    cd "$SCRIPT_DIR"
    $PYTHON_CMD main_app.py --mode status --config "$CONFIG_FILE"
}

# Trap Ctrl+C for graceful shutdown
trap 'echo -e "\n${YELLOW}[INFO]${NC} Shutting down gracefully..."; exit 0' INT

# Run main function
main "$@"