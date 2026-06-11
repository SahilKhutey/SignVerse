@echo off
echo ============================================
echo   🤖 SignVerse Robotics - Day 3 Windows
echo   Final Demo Build
echo ============================================
echo.

:: Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

:: Check Node
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Node.js not found. Please install Node 18+
    pause
    exit /b 1
)

:: Create directories
if not exist "data\uploads" mkdir "data\uploads"
if not exist "exports" mkdir "exports"
if not exist "datasets" mkdir "datasets"

:: Python virtual environment
if not exist "venv" (
    echo 📦 Creating Python virtual environment (Python 3.12)...
    py -3.12 -m venv venv
    if %errorlevel% neq 0 (
        echo 📦 Fallback to default python venv...
        python -m venv venv
    )
)

echo 📦 Activating venv and updating dependencies...
call .\venv\Scripts\activate
python -m pip install --quiet --upgrade pip
pip install -r requirements.txt

:: Node dependencies
if not exist "frontend\node_modules" (
    echo 📦 Installing Node dependencies...
    cd frontend && npm install && cd ..
)

echo.
echo 🔍 Running verification...
python scripts/verify.py
if %errorlevel% neq 0 (
    echo ❌ Verification failed. Fix issues before starting.
    pause
    exit /b 1
)

echo.
echo ✅ Setup complete!
echo.
echo 🚀 Starting services...
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C in either terminal window to stop.
echo.

:: Start backend and frontend in separate parallel processes
start "SignVerse Backend" cmd /k "call .\venv\Scripts\activate && uvicorn backend.main:app --host 0.0.0.0 --port 8000"
start "SignVerse Frontend" cmd /k "cd frontend && npm run dev"

echo Services have been launched in separate console windows.
pause
