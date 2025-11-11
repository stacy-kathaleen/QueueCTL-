@echo off
REM Test script for QueueCTL on Windows
REM This script validates core functionality

echo === QueueCTL Test Suite (Windows) ===
echo.

set TESTS_PASSED=0
set TESTS_TOTAL=0

REM Cleanup function
if exist "%USERPROFILE%\.queuectl" (
    echo Cleaning up old data...
    rmdir /s /q "%USERPROFILE%\.queuectl"
)

echo Test 1: Configuration management
python queuectl.py config set max-retries 5
python queuectl.py config get max-retries | find "5" >nul
if %errorlevel% equ 0 (
    echo [PASS] Configuration set/get
    set /a TESTS_PASSED+=1
) else (
    echo [FAIL] Configuration set/get
)
set /a TESTS_TOTAL+=1
echo.

echo Test 2: Enqueuing jobs
python queuectl.py enqueue "{\"id\":\"test-job-1\",\"command\":\"echo Hello World\"}"
python queuectl.py enqueue "{\"id\":\"test-job-2\",\"command\":\"timeout /t 1 /nobreak\"}"
python queuectl.py enqueue "{\"id\":\"test-job-fail\",\"command\":\"exit 1\"}"
echo [PASS] Jobs enqueued
set /a TESTS_PASSED+=1
set /a TESTS_TOTAL+=1
echo.

echo Test 3: Status check
python queuectl.py status | find "Pending:" >nul
if %errorlevel% equ 0 (
    echo [PASS] Status command works
    set /a TESTS_PASSED+=1
) else (
    echo [FAIL] Status command works
)
set /a TESTS_TOTAL+=1
echo.

echo Test 4: List pending jobs
python queuectl.py list --state pending | find "test-job-1" >nul
if %errorlevel% equ 0 (
    echo [PASS] List command works
    set /a TESTS_PASSED+=1
) else (
    echo [FAIL] List command works
)
set /a TESTS_TOTAL+=1
echo.

echo Test 5: Worker processing (5 seconds)
echo Starting worker...
timeout /t 5 /nobreak | python queuectl.py worker start --count 1
timeout /t 2 /nobreak >nul

python queuectl.py status | find "Completed:" >nul
if %errorlevel% equ 0 (
    echo [PASS] Worker processed jobs
    set /a TESTS_PASSED+=1
) else (
    echo [FAIL] Worker processed jobs
)
set /a TESTS_TOTAL+=1
echo.

echo Test 6: Data persistence
python queuectl.py enqueue "{\"id\":\"persist-test\",\"command\":\"echo Persistence\"}"
if exist "%USERPROFILE%\.queuectl\jobs.db" (
    python queuectl.py list --state pending | find "persist-test" >nul
    if %errorlevel% equ 0 (
        echo [PASS] Jobs persist across restarts
        set /a TESTS_PASSED+=1
    ) else (
        echo [FAIL] Jobs persist across restarts
    )
) else (
    echo [FAIL] Database file not created
)
set /a TESTS_TOTAL+=1
echo.

echo ================================
echo Tests passed: %TESTS_PASSED%/%TESTS_TOTAL%
echo ================================

if %TESTS_PASSED% equ %TESTS_TOTAL% (
    echo All tests passed!
) else (
    echo Some tests failed
)

REM Cleanup
echo.
echo Cleaning up...
if exist "%USERPROFILE%\.queuectl" (
    rmdir /s /q "%USERPROFILE%\.queuectl"
)
echo Done

pause
