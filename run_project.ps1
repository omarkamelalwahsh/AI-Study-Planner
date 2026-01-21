# Startup Script

$ErrorActionPreference = "Stop"

Write-Host "Starting Career Copilot RAG..."

# Start Backend
Write-Host "Launching Backend (Port 8000)..."
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd 'E:\Career Copilot RAG'; .\venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

# Start Frontend
Write-Host "Launching Frontend..."
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd 'E:\Career Copilot RAG\frontend'; npm run dev -- --host 127.0.0.1"

# Open Browser
Start-Sleep -Seconds 5
Write-Host "Opening Browser..."
Start-Process "http://localhost:5173" 
# Note: Vite might pick a different port if 5173 is busy, but we'll try the default.
