@echo off
setlocal enabledelayedexpansion

REM Determine if running with Docker or locally
if "%1"=="docker" (
    echo Running tests in Docker container...
    
    if "%2"=="coverage" (
        REM Run with coverage
        docker-compose run --rm testcov
    ) else (
        REM Run tests without coverage
        docker-compose run --rm test
    )
) else (
    REM Run tests locally (need MongoDB running locally)
    echo Running tests locally...
    
    REM Create virtual environment if it doesn't exist
    if not exist "venv" (
        echo Creating virtual environment...
        python -m venv venv
    )
    
    REM Activate virtual environment
    call venv\Scripts\activate.bat
    
    REM Install dependencies
    echo Installing dependencies...
    pip install -r requirements.txt
    
    if "%1"=="coverage" (
        REM Run tests with coverage
        echo Running tests with coverage...
        python -m pytest --cov=. --cov-report=term --cov-report=html:coverage_report -v
    ) else (
        REM Run tests without coverage
        echo Running tests...
        python -m pytest -v
    )
)

echo Tests completed!
endlocal