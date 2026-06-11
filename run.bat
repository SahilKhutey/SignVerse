@echo off
echo 🤖 Starting SignVerse MVP...
echo 📦 Activating Python env...

if not exist venv (
    echo 🛠️ Virtual environment not found. Creating one...
    py -3.12 -m venv venv
)

call venv\Scripts\activate.bat
echo 📥 Checking dependencies...
pip install -r requirements.txt

echo 📂 Creating directories...
if not exist "data\uploads" mkdir "data\uploads"
if not exist "exports" mkdir "exports"
if not exist "datasets" mkdir "datasets"

echo 🚀 Starting FastAPI on port 8000 (separate window)...
start "SignVerse Backend API" cmd /k "venv\Scripts\activate.bat && uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

echo 🎨 Starting React frontend on port 5173 (separate window)...
cd frontend
if not exist "node_modules" (
    echo 📦 Installing frontend dependencies...
    call npm install
)
start "SignVerse Frontend UI" cmd /k "npm run dev"

echo 🎉 SignVerse has been launched.
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
pause
