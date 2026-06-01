@echo off
cd /d "D:\Codex-work\rigol-voice"

echo.
echo === Push rigol-voice to GitHub ===
echo.

REM Auto-add all changes
git add -A
git status --short
echo.

REM If no changes, skip
git diff --quiet --cached
if %errorlevel% neq 0 (
    set /p MSG="Commit message (or press Enter for auto): "
    if "%MSG%"=="" set MSG=update
    git commit -m "%MSG%"
    echo.
    echo Pushing...
    git push origin master --tags
    echo.
    echo Done! https://github.com/nles1214/rigol-voice
) else (
    echo No changes to push.
)

pause