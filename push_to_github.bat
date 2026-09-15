@echo off
setlocal
cd /d "%~dp0"

set REPO_URL=https://github.com/nutyfreshz/ocr_mvp1.git

git --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Git is not installed or not in PATH.
  pause
  exit /b 1
)

if not exist ".git" (
  git init
  if errorlevel 1 goto :error
  git branch -M main
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
  git remote add origin %REPO_URL%
) else (
  git remote set-url origin %REPO_URL%
)

git add -A

git diff --cached --quiet
if not errorlevel 1 (
  echo No changes to commit.
  goto :push
)

set /p COMMIT_MSG=Commit message [update OCR MVP]: 
if "%COMMIT_MSG%"=="" set COMMIT_MSG=update OCR MVP

git commit -m "%COMMIT_MSG%"
if errorlevel 1 goto :error

:push
git branch -M main
git push -u origin main
if errorlevel 1 goto :error

echo.
echo Push completed successfully.
pause
exit /b 0

:error
echo.
echo ERROR: Git command failed. Check GitHub login/credentials and try again.
pause
exit /b 1
