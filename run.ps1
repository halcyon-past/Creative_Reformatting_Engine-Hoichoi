<#
.SYNOPSIS
    Task runner for the Creative Reformatting Engine on Windows.

.DESCRIPTION
    Mirrors the Makefile for environments without GNU make (the default on
    Windows). Every target here does the same thing as the Make target of the
    same name.

.EXAMPLE
    .\run.ps1 setup
    .\run.ps1 demo
    .\run.ps1 process test_sample/input_image.png
    .\run.ps1 api
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Task = "help",

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$Py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

function Assert-Venv {
    if (-not (Test-Path $Py)) {
        throw "No virtualenv found at .venv. Run '.\run.ps1 setup' first."
    }
}

function Invoke-Step {
    param([string]$Label, [scriptblock]$Body)
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Body
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "$Label failed (exit $LASTEXITCODE)"
    }
}

switch ($Task.ToLower()) {

    # ---------------------------------------------------------------- setup --
    "venv" {
        Invoke-Step "Creating virtualenv" { uv venv .venv --python 3.12 }
    }

    "install" {
        if (-not (Test-Path $Py)) { Invoke-Step "Creating virtualenv" { uv venv .venv --python 3.12 } }
        Invoke-Step "Installing backend + dev tooling" { uv pip install --python $Py -e "backend[dev]" }
    }

    "models" {
        Assert-Venv
        Invoke-Step "Fetching vision models" { & $Py -m cre.vision.models }
    }

    "frontend-install" {
        Invoke-Step "Installing frontend dependencies" {
            Push-Location frontend; npm install --no-audit --no-fund; Pop-Location
        }
    }

    "setup" {
        & $PSCommandPath install
        & $PSCommandPath models
        & $PSCommandPath frontend-install
        if (-not (Test-Path ".env")) {
            Copy-Item ".env.example" ".env"
            Write-Host "==> Wrote .env from .env.example" -ForegroundColor Cyan
        }
        Write-Host "`nSetup complete. Try: .\run.ps1 demo" -ForegroundColor Green
    }

    # ------------------------------------------------------------------ run --
    "api" {
        Assert-Venv
        Write-Host "API + in-process worker on http://127.0.0.1:8000  (docs at /docs)" -ForegroundColor Green
        & $Py -m uvicorn cre.main:app --reload --host 0.0.0.0 --port 8000
    }

    "web" {
        Write-Host "UI on http://localhost:5173  (proxies /api and /media to :8000)" -ForegroundColor Green
        Push-Location frontend; npm run dev; Pop-Location
    }

    "stack" {
        # Both servers at once, each in its own window, since a single
        # PowerShell session cannot foreground two long-running processes.
        Assert-Venv
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$PSCommandPath' api"
        Start-Sleep -Seconds 3
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$PSCommandPath' web"
        Write-Host "API  -> http://127.0.0.1:8000" -ForegroundColor Green
        Write-Host "UI   -> http://localhost:5173" -ForegroundColor Green
    }

    # ------------------------------------------------------------------ cli --
    "spec" {
        Assert-Venv
        & $Py -m cre.cli spec
    }

    "process" {
        Assert-Venv
        if (-not $Args -or $Args.Count -eq 0) {
            throw "Usage: .\run.ps1 process <path-to-master>"
        }
        & $Py -m cre.cli process $Args[0]
    }

    "regenerate" {
        Assert-Venv
        if (-not $Args -or $Args.Count -lt 2) {
            throw "Usage: .\run.ps1 regenerate <asset_id> <profile_id>"
        }
        & $Py -m cre.cli regenerate $Args[0] $Args[1]
    }

    "list" {
        Assert-Venv
        & $Py -m cre.cli list
    }

    "demo" {
        Assert-Venv
        Invoke-Step "Reformatting the sample still" {
            & $Py -m cre.cli process test_sample/input_image.png --title "Sample Still"
        }
        Invoke-Step "Reformatting the sample video" {
            & $Py -m cre.cli process test_sample/input_video.mp4 --title "Sample Video"
        }
    }

    # ----------------------------------------------------------------- test --
    "test" {
        Assert-Venv
        & $Py -m pytest backend/tests/unit -q
    }

    "test-all" {
        Assert-Venv
        & $Py -m pytest backend/tests -q
    }

    "coverage" {
        Assert-Venv
        & $Py -m pytest backend/tests/unit --cov=cre --cov-report=term-missing
    }

    "lint" {
        Assert-Venv
        & $Py -m ruff check backend/src backend/tests
    }

    "format" {
        Assert-Venv
        & $Py -m ruff check --fix backend/src backend/tests
        & $Py -m ruff format backend/src backend/tests
    }

    "typecheck-web" {
        Push-Location frontend; npx tsc -b; Pop-Location
    }

    # ---------------------------------------------------------------- docker --
    "up"   { docker compose up --build }
    "down" { docker compose down -v }

    # ---------------------------------------------------------------- clean --
    "clean" {
        foreach ($p in @("data\library", "data\cache", "data\cre.db")) {
            if (Test-Path $p) { Remove-Item -Recurse -Force $p }
        }
        Write-Host "Removed generated data (masters and models kept)." -ForegroundColor Green
    }

    default {
        Write-Host @"
Creative Reformatting Engine - task runner

  Setup
    .\run.ps1 setup               venv + deps + models + npm install
    .\run.ps1 models              fetch the vision models only

  Run
    .\run.ps1 api                 API + worker on :8000
    .\run.ps1 web                 UI on :5173
    .\run.ps1 stack               both, in separate windows

  Pipeline
    .\run.ps1 demo                both sample assets, end to end
    .\run.ps1 process <file>      reformat one master
    .\run.ps1 regenerate <asset> <profile>
    .\run.ps1 list                list ingested assets
    .\run.ps1 spec                print the platform spec sheet

  Quality
    .\run.ps1 test                unit tests
    .\run.ps1 test-all            everything, including slow media tests
    .\run.ps1 lint / format / typecheck-web

  Other
    .\run.ps1 up / down           docker compose
    .\run.ps1 clean               remove generated variants
"@ -ForegroundColor Gray
    }
}
