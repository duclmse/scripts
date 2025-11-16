@echo off
setlocal enabledelayedexpansion

:: Configuration: Add your repository paths here
set REPO_PATHS=(
  "C:\path\to\repo1"
  "D:\path\to\repo2"
  :: Add more paths as needed
)

:: Check command
if "%1"=="" (
  echo Usage: %~nx0 ^<command^> [remote]
  echo Commands:
  echo   fetch     - Fetch from both remotes
  echo   pull      - Pull from specified remote
  echo   push      - Push to specified remote
  echo   status    - Show repository status
  echo   remotes   - List configured remotes
  exit /b 1
)

set COMMAND=%1
set REMOTE=%2

for %%r in %REPO_PATHS% do (
  echo.
  echo [Processing %%r]
  
  if not exist "%%r\.git\" (
    echo Not a Git repository! Skipping.
    goto :next_repo
  )
  
  if "%COMMAND%"=="fetch" (
    git -C "%%r" fetch --all
  ) else if "%COMMAND%"=="pull" (
    if "%REMOTE%"=="" (
      echo Error: Remote name required for pull
      exit /b 1
    )
    git -C "%%r" pull %REMOTE%
  ) else if "%COMMAND%"=="push" (
    if "%REMOTE%"=="" (
      echo Error: Remote name required for push
      exit /b 1
    )
    git -C "%%r" push %REMOTE%
  ) else if "%COMMAND%"=="status" (
    git -C "%%r" status -sb
  ) else if "%COMMAND%"=="remotes" (
    git -C "%%r" remote -v
  ) else (
    echo Error: Unknown command '%COMMAND%'
    exit /b 1
  )
  
  :next_repo
)