# PowerShell script for running tests on Windows

# Determine how to run tests based on arguments
if ($args[0] -eq "docker") {
    Write-Host "Running tests in Docker container..."
    
    # Run tests using Docker Compose
    if ($args[1] -eq "coverage") {
        # Run with coverage
        docker-compose run --rm testcov
    }
    else {
        # Run tests without coverage
        docker-compose run --rm test
    }
}
else {
    # Run tests locally (need MongoDB running locally)
    Write-Host "Running tests locally..."
    
    # Create virtual environment if it doesn't exist
    if (-not (Test-Path "venv")) {
        Write-Host "Creating virtual environment..."
        python -m venv venv
    }
    
    # Activate virtual environment
    . .\venv\Scripts\Activate.ps1
    
    # Install dependencies
    Write-Host "Installing dependencies..."
    pip install -r requirements.txt
    
    if ($args[0] -eq "coverage") {
        # Run tests with coverage
        Write-Host "Running tests with coverage..."
        python -m pytest --cov=. --cov-report=term --cov-report=html:coverage_report -v
    }
    else {
        # Run tests without coverage
        Write-Host "Running tests..."
        python -m pytest -v
    }
}

Write-Host "Tests completed!"