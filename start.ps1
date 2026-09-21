$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$drivePython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $drivePython)) { throw 'Create .venv and install requirements.txt first.' }
& $drivePython -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
& $drivePython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
