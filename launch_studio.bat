@echo off
title 🤖 SignVerse Robotics Studio Launcher
color 0B
cls
echo ====================================================================
echo   🤖  S I G N V E R S E   R O B O T I C S   S T U D I O  🤖
echo ====================================================================
echo   Universal Human-to-Robot Motion Intelligence Pipeline
echo ====================================================================
echo.
echo Select the services profile you want to run:
echo.
echo   [1] 🎨 Launch Streamlit Dashboard Studio (Reworked Interface)
echo   [2] 🔌 Launch Production API (FastAPI) + React Web Frontend (Three.js)
echo   [3] 🚀 Launch ALL services (Streamlit + FastAPI Backend + React Web UI)
echo   [4] 🚪 Exit Launcher
echo.
set /p opt="Enter select profile option (1-4): "

if "%opt%"=="1" (
    echo.
    echo 🚀 Starting Streamlit Studio Dashboard...
    echo URL: http://localhost:8501
    echo.
    call venv\Scripts\activate.bat
    streamlit run app.py
)
if "%opt%"=="2" (
    echo.
    echo 🚀 Starting React UI + FastAPI Backend...
    echo.
    call start.bat
)
if "%opt%"=="3" (
    echo.
    echo 🚀 Launching all services in parallel windows...
    echo.
    start "SignVerse Streamlit Studio" cmd /k "call venv\Scripts\activate.bat && streamlit run app.py"
    call start.bat
)
if "%opt%"=="4" (
    exit
)
pause
