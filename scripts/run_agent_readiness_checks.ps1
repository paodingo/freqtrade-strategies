$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RootDir

function Invoke-NodeCheck {
  param(
    [Parameter(Mandatory = $true)]
    [string[]] $NodeArgs
  )

  & node @NodeArgs
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

Invoke-NodeCheck @("--check", "scripts/guard_harness_diff.js")
Invoke-NodeCheck @("--check", "scripts/guard_no_secret_material.js")
Invoke-NodeCheck @("--check", "scripts/guard_trading_surface.js")

Invoke-NodeCheck @("scripts/guard_harness_diff.js")
Invoke-NodeCheck @("scripts/guard_no_secret_material.js")
Invoke-NodeCheck @("scripts/guard_trading_surface.js")
