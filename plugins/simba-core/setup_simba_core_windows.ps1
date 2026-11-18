#Requires -Version 5.1
<#
.SYNOPSIS
  Install and diagnose Simba CORE local MCP on Windows without API calls.
.DESCRIPTION
  Checks Python/Git, creates a separate checkout only if absent, configures an
  owner-only new private folder, persists *non-secret* user environment variables
  and runs a no-charge JSON-RPC MCP preflight. Does NOT install the ChatGPT UI
  plugin, create an API key, authorize billing, publish or run model requests.
.EXAMPLE
  .\setup_simba_core_windows.ps1
.EXAMPLE
  .\setup_simba_core_windows.ps1 -RepoRoot "D:\Projects\Simba" -PrivateDir "D:\SimbaPrivate"
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = (Join-Path $env:LOCALAPPDATA 'SimbaCore\Repo'),
    [string]$PrivateDir = (Join-Path $env:LOCALAPPDATA 'SimbaCore\Private')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-ExternalExit {
    param([int]$ExitCode, [string]$Task)
    if ($ExitCode -ne 0) { throw "$Task failed (exit $ExitCode)." }
}

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'This is the Windows-only setup. No desktop installation performed.'
}
if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is missing.' }

$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python 3 is not available. Install Python and retry.' }
& $python.Source -c 'import sys; assert sys.version_info >= (3, 9)' 
Assert-ExternalExit $LASTEXITCODE 'Python version check'

$RepoRoot = [IO.Path]::GetFullPath($RepoRoot)
$PrivateDir = [IO.Path]::GetFullPath($PrivateDir)
$defaultRepoRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'SimbaCore\Repo'))
$sparseDirs = @(
    'integrations/core',
    'plugins/simba-core',
    'SIMBA KNOWLEDGE BASE',
    'Симба (Писатель)',
    'Critic'
)
if ($RepoRoot -eq $PrivateDir -or $PrivateDir.StartsWith($RepoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'PrivateDir must be outside the repository.'
}
# The public repo contains Windows-invalid ':' file names inside Archivarius.
# NEVER run a full checkout on Windows: clone objects, then materialize ONLY CORE.
$git = Get-Command git.exe -ErrorAction SilentlyContinue
$createdRepo = $false
if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) {
    if (-not $git) { throw 'Git is not available. Install Git or supply -RepoRoot for an existing checkout.' }
    $parent = Split-Path -Parent $RepoRoot
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Write-Host 'Cloning Simba objects without checkout (Windows-safe, no paid API calls)...'
    & $git.Source clone --no-checkout --depth 1 --single-branch --branch main https://github.com/legur/Simba.git $RepoRoot
    Assert-ExternalExit $LASTEXITCODE 'Git clone --no-checkout'
    $createdRepo = $true
}
$server = Join-Path $RepoRoot 'plugins\simba-core\server\simba_core_mcp.py'
$runner = Join-Path $RepoRoot 'integrations\core\editorial_live_runner.py'
$missingCore = (-not (Test-Path -LiteralPath $server -PathType Leaf)) -or
               (-not (Test-Path -LiteralPath $runner -PathType Leaf))
$isDedicatedRepo = [string]::Equals($RepoRoot.TrimEnd('\'), $defaultRepoRoot.TrimEnd('\'),
                                    [StringComparison]::OrdinalIgnoreCase)

# Recover the *known dedicated location* left by an interrupted full clone.
# Never alter an existing custom repo or a healthy checkout.
if ($createdRepo -or ($missingCore -and $isDedicatedRepo)) {
    if (-not $git) { throw 'Git is required to recover the partial Simba checkout.' }
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.git'))) {
        throw 'Dedicated Simba directory exists but is not a Git repo. Kept unchanged.'
    }
    $remote = & $git.Source -C $RepoRoot remote get-url origin
    Assert-ExternalExit $LASTEXITCODE 'Verify local Git origin'
    if ($remote -notmatch '^(https://github\.com/legur/Simba(\.git)?|git@github\.com:legur/Simba(\.git)?)

$privateCreated = $false
if (-not (Test-Path -LiteralPath $PrivateDir)) {
    New-Item -ItemType Directory -Path $PrivateDir -Force | Out-Null
    $privateCreated = $true
}
if (-not (Test-Path -LiteralPath $PrivateDir -PathType Container)) {
    throw 'PrivateDir path is not a directory.'
}
$currentId = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($privateCreated) {
    # Only a NEW folder is adjusted: never rewrite ACLs of an existing folder.
    & icacls.exe $PrivateDir /inheritance:r | Out-Null
    Assert-ExternalExit $LASTEXITCODE 'Remove inherited permissions from NEW private folder'
    & icacls.exe $PrivateDir /grant:r ('*{0}:(OI)(CI)F' -f $currentId) | Out-Null
    Assert-ExternalExit $LASTEXITCODE 'Grant private folder owner access'
}

$acl = Get-Acl -LiteralPath $PrivateDir
if (-not $acl.AreAccessRulesProtected) {
    throw 'Existing private folder inherits permissions. Manually restrict ACL first; no environment changes made.'
}
$allowed = @($currentId, 'S-1-5-18', 'S-1-5-32-544')
foreach ($rule in $acl.Access) {
    if ($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow) {
        $sid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        if ($allowed -notcontains $sid) {
            throw "PrivateDir has an unexpected allowed principal. Check ACLs before retry."
        }
    }
}
$vars = @{
    SIMBA_CORE_REPO_ROOT = $RepoRoot
    SIMBA_CORE_PRIVATE_DIR = $PrivateDir
    SIMBA_CORE_WINDOWS_PRIVATE_ACL_VERIFIED = '1'
}
foreach ($pair in $vars.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($pair.Key, $pair.Value, 'User')
    [Environment]::SetEnvironmentVariable($pair.Key, $pair.Value, 'Process')
}
# IMPORTANT: never set SIMBA_CORE_ALLOW_BILLABLE or OPENAI_API_KEY here.
Write-Host 'Local paths and private ACL verified. Running no-charge MCP preflight:'
$request = '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"simba_core_preflight","arguments":{}}}'
$reply = $request | & $python.Source $server
Assert-ExternalExit $LASTEXITCODE 'Read-only MCP handshake'
$line = @($reply | Where-Object { $_.Trim() })[-1]
$parsed = $line | ConvertFrom-Json
if (-not $parsed.result -or $parsed.result.isError -or $parsed.id -ne 1) {
    throw 'MCP server did not return a valid preflight response.'
}
Write-Output $line
Write-Host ''
Write-Host 'LOCAL SETUP COMPLETE (not installed in ChatGPT UI). No API usage.'
Write-Host 'Open the private plugin in ChatGPT Desktop and install/connect it.'
Write-Host 'A new ChatGPT Desktop session may be needed to see persisted variables.'
) {
        throw 'Existing Git origin is not legur/Simba. Kept unchanged.'
    }
    Write-Host 'Selecting Simba CORE only: avoiding Windows-invalid Archivarius filenames...'
    & $git.Source -C $RepoRoot sparse-checkout init --cone
    Assert-ExternalExit $LASTEXITCODE 'Git sparse-checkout init'
    & $git.Source -C $RepoRoot sparse-checkout set --cone -- $sparseDirs
    Assert-ExternalExit $LASTEXITCODE 'Git sparse-checkout set'
}
if (-not (Test-Path -LiteralPath $server -PathType Leaf) -or
    -not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw 'Simba CORE files missing after sparse checkout; no local environment settings changed.'
}

$privateCreated = $false
if (-not (Test-Path -LiteralPath $PrivateDir)) {
    New-Item -ItemType Directory -Path $PrivateDir -Force | Out-Null
    $privateCreated = $true
}
if (-not (Test-Path -LiteralPath $PrivateDir -PathType Container)) {
    throw 'PrivateDir path is not a directory.'
}
$currentId = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($privateCreated) {
    # Only a NEW folder is adjusted: never rewrite ACLs of an existing folder.
    & icacls.exe $PrivateDir /inheritance:r | Out-Null
    Assert-ExternalExit $LASTEXITCODE 'Remove inherited permissions from NEW private folder'
    & icacls.exe $PrivateDir /grant:r ('*{0}:(OI)(CI)F' -f $currentId) | Out-Null
    Assert-ExternalExit $LASTEXITCODE 'Grant private folder owner access'
}

$acl = Get-Acl -LiteralPath $PrivateDir
if (-not $acl.AreAccessRulesProtected) {
    throw 'Existing private folder inherits permissions. Manually restrict ACL first; no environment changes made.'
}
$allowed = @($currentId, 'S-1-5-18', 'S-1-5-32-544')
foreach ($rule in $acl.Access) {
    if ($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow) {
        $sid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        if ($allowed -notcontains $sid) {
            throw "PrivateDir has an unexpected allowed principal. Check ACLs before retry."
        }
    }
}
$vars = @{
    SIMBA_CORE_REPO_ROOT = $RepoRoot
    SIMBA_CORE_PRIVATE_DIR = $PrivateDir
    SIMBA_CORE_WINDOWS_PRIVATE_ACL_VERIFIED = '1'
}
foreach ($pair in $vars.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($pair.Key, $pair.Value, 'User')
    [Environment]::SetEnvironmentVariable($pair.Key, $pair.Value, 'Process')
}
# IMPORTANT: never set SIMBA_CORE_ALLOW_BILLABLE or OPENAI_API_KEY here.
Write-Host 'Local paths and private ACL verified. Running no-charge MCP preflight:'
$request = '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"simba_core_preflight","arguments":{}}}'
$reply = $request | & $python.Source $server
Assert-ExternalExit $LASTEXITCODE 'Read-only MCP handshake'
$line = @($reply | Where-Object { $_.Trim() })[-1]
$parsed = $line | ConvertFrom-Json
if (-not $parsed.result -or $parsed.result.isError -or $parsed.id -ne 1) {
    throw 'MCP server did not return a valid preflight response.'
}
Write-Output $line
Write-Host ''
Write-Host 'LOCAL SETUP COMPLETE (not installed in ChatGPT UI). No API usage.'
Write-Host 'Open the private plugin in ChatGPT Desktop and install/connect it.'
Write-Host 'A new ChatGPT Desktop session may be needed to see persisted variables.'
