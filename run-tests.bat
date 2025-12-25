@echo off
REM ATS Backend Test Runner for Windows

if "%1"=="help" (
    echo Available commands:
    echo   run-tests property     - Run property-based tests
    echo   run-tests property-dev - Run property-based tests in dev mode
    echo   run-tests property-ci  - Run property-based tests in CI mode
    echo   run-tests unit         - Run unit tests
    echo   run-tests all          - Run all tests
    echo   run-tests help         - Show this help
    goto :eof
)

if "%1"=="property" (
    set HYPOTHESIS_PROFILE=production_hardening
    python -m pytest tests/property_based/ -m "property_test" -v
    goto :eof
)

if "%1"=="property-dev" (
    set HYPOTHESIS_PROFILE=dev
    python -m pytest tests/property_based/ -m "property_test" -v
    goto :eof
)

if "%1"=="property-ci" (
    set CI=1
    set HYPOTHESIS_PROFILE=ci
    python -m pytest tests/property_based/ -m "property_test" -v --tb=short
    goto :eof
)

if "%1"=="unit" (
    python -m pytest tests/ -m "unit" -v
    goto :eof
)

if "%1"=="all" (
    python -m pytest tests/ -v
    goto :eof
)

REM Default to property tests
set HYPOTHESIS_PROFILE=production_hardening
python -m pytest tests/property_based/ -m "property_test" -v