@echo off
title SignVerse Git Push
echo ========================================================
echo Pushing local commits to SahilKhutey/SignVerse on GitHub...
echo ========================================================
echo.
"C:\Program Files\Git\cmd\git.exe" push origin main
echo.
if %errorlevel% neq 0 (
    echo.
    echo [Error] Push failed. Make sure your credentials or token are correct.
) else (
    echo [Success] Commits successfully pushed to GitHub!
)
echo.
pause
