Write-Host "=== Starting CybersecurityResearchAgent Phase 19.5 Stack ==="

Write-Host "Starting PostgreSQL container..."
docker start cyber-db | Out-Null

Write-Host "Starting Redis container..."
docker start cyber-redis | Out-Null

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "Now start these in separate terminals:"
Write-Host ""
Write-Host "1) Ollama:"
Write-Host "   ollama serve"
Write-Host ""
Write-Host "2) Celery worker:"
Write-Host "   .\venv\Scripts\celery.exe -A celery_app.celery_app worker --loglevel=info --pool=solo"
Write-Host ""
Write-Host "3) FastAPI:"
Write-Host "   .\venv\Scripts\uvicorn.exe app.main:app --reload"
Write-Host ""
Write-Host "4) Streamlit:"
Write-Host "   .\venv\Scripts\streamlit.exe run ui/streamlit_app.py"
Write-Host ""
Write-Host "5) Manual ingestion (optional):"
Write-Host "   .\venv\Scripts\python.exe run_ingestion.py"
