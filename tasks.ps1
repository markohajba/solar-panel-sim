<#
.SYNOPSIS
    Task runner for the Solar Panel Thermal Simulator (Windows / PowerShell).
.DESCRIPTION
    Thin wrapper around uv. Usage:  .\tasks.ps1 <task>
    Tasks: setup | run | test | lint | format | typecheck | check
#>
param([Parameter(Position = 0)][string]$Task = "help")

$src = @("src", "app", "tests")

switch ($Task) {
    "setup"     { uv sync }
    "run"       { uv run streamlit run app/streamlit_app.py }
    "test"      { uv run pytest -q }
    "lint"      { uv run ruff check @src; if ($?) { uv run ruff format --check @src } }
    "format"    { uv run ruff format @src; if ($?) { uv run ruff check --fix @src } }
    "typecheck" { uv run mypy src }
    "check"     { uv run ruff check @src; if ($?) { uv run mypy src }; if ($?) { uv run pytest -q } }
    default     { Write-Host "Tasks: setup | run | test | lint | format | typecheck | check" }
}
