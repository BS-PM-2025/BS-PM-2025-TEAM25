#!/bin/bash
set -e

# Set default database URI if not provided
if [ -z "$MONGO_URI" ]; then
    export MONGO_URI="mongodb://mongo:27017/cityfix"
fi

# Determine what to run based on the command
case "$1" in
    app)
        echo "Starting CityFix application..."
        exec python run.py
        ;;
    test)
        echo "Running tests..."
        # Shift the first argument so $@ contains all remaining arguments
        shift
        exec python -m pytest -xvs "$@"
        ;;
    testcov)
        echo "Running tests with coverage..."
        # Shift the first argument so $@ contains all remaining arguments
        shift
        exec python -m pytest --cov=. --cov-report=term --cov-report=html:coverage_report "$@"
        ;;
    shell)
        echo "Starting Python shell..."
        exec python
        ;;
    *)
        # Execute the command directly
        exec "$@"
        ;;
esac