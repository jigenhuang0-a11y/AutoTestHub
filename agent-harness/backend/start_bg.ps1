$proc = Start-Process -FilePath "python" `
  -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8001" `
  -WorkingDirectory "d:\AI_Project\ai-test-platform\agent-harness\backend" `
  -RedirectStandardOutput "d:\AI_Project\ai-test-platform\agent-harness\backend\server.log" `
  -RedirectStandardError "d:\AI_Project\ai-test-platform\agent-harness\backend\server.err" `
  -WindowStyle Hidden `
  -PassThru
Write-Output "started pid=$($proc.Id)"
Start-Sleep -Seconds 6
netstat -ano | findstr ":8001"
Write-Output "--- server.log tail ---"
Get-Content "d:\AI_Project\ai-test-platform\agent-harness\backend\server.log" -Tail 20
Write-Output "--- server.err tail ---"
Get-Content "d:\AI_Project\ai-test-platform\agent-harness\backend\server.err" -Tail 20
