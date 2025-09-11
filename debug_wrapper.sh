#!/bin/bash
# Debug wrapper script for running face recognition with ChromaDB backend
# This script adds debug flags and captures output for analysis

echo "Starting face recognition with ChromaDB backend in debug mode..."

# Create a timestamp for log files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="debug_log_${TIMESTAMP}.txt"

# Define colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Running with command:${NC}"
echo -e "python -m src.main --recognizer-backend chromadb --debug --optimize-cache --no-optimize-performance"
echo -e "${YELLOW}Logging output to: ${LOG_FILE}${NC}\n"

# Run the command with debug flags enabled
# --debug: Enable debug output
# --optimize-cache: Preload and optimize cache
# --no-optimize-performance: Disable performance optimizations that might hide issues
python -m src.main \
  --recognizer-backend chromadb \
  --debug \
  --optimize-cache \
  --no-optimize-performance \
  2>&1 | tee "$LOG_FILE"

# Check exit status of the Python command (not the tee command)
EXIT_STATUS=${PIPESTATUS[0]}

if [ $EXIT_STATUS -eq 0 ]; then
  echo -e "\n${GREEN}Face recognition completed successfully${NC}"
else
  echo -e "\n${RED}Face recognition failed with exit code: $EXIT_STATUS${NC}"
  echo -e "${YELLOW}Check $LOG_FILE for detailed error information${NC}"
  
  # Extract errors from the log file for quick review
  echo -e "\n${YELLOW}Error summary:${NC}"
  grep -i "error\|exception\|failed" "$LOG_FILE" | tail -n 20
fi

echo -e "\n${BLUE}Debug log saved to: ${LOG_FILE}${NC}"