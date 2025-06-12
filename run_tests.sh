#!/bin/bash
set -e

# Make the script executable
chmod +x ./run_tests.sh

# Make the docker entrypoint script executable
chmod +x ./docker-entrypoint.sh

# Determine how to run tests based on arguments
if [ "$1" == "docker" ]; then
    echo "Running tests in Docker container..."
    
    # Run tests using Docker Compose
    if [ "$2" == "coverage" ]; then
        # Run with coverage
        docker-compose run --rm testcov
    else
        # Run tests without coverage
        docker-compose run --rm test
    fi
else
    # Run tests locally (need MongoDB running locally)
    echo "Running tests locally..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python -m venv venv
    fi
    
    # Activate virtual environment (different on Windows)
    if [ -f "venv/bin/activate" ]; then
        # Linux/MacOS
        source venv/bin/activate
    else
        # Windows
        source venv/Scripts/activate
    fi
    
    # Install dependencies
    echo "Installing dependencies..."
    pip install -r requirements.txt
    
    if [ "$1" == "coverage" ]; then
        # Run tests with coverage
        echo "Running tests with coverage..."
        python -m pytest --cov=. --cov-report=term --cov-report=html:coverage_report -v
    else
        # Run tests without coverage
        echo "Running tests..."
        python -m pytest -v
    fi
fi

echo "Tests completed!"