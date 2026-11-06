# Simba A2E: one-time OAuth enrollment and activation on the owner's Windows PC.
# This script never prints, stores in Git, or uploads the OAuth JSON itself.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string] $ClientJson,
    [string] $ExpectedAccount = "eskvlg@gmail.com",
    [string] $Repo = "legur/Simba"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Command([string]$Name, [string]$Instruction) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is not installed. $Instruction"
    }
}
function Run-SafeNative([string]$Description, [scriptblock]$Action) {
    Write-Host $Description
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed. No further activation steps were run."
    }
}

Require-Command -Name "py" -Instruction "Install Python 3.12+ from python.org."
Require-Command -Name "gh" -Instruction "Install GitHub CLI from cli.github.com, then run gh auth login."

if (-not (Test-Path -LiteralPath $ClientJson -PathType Leaf)) {
    throw "Google Desktop OAuth JSON not found. Download it to this PC first."
}
if ([IO.Path]::GetExtension($ClientJson) -ne ".json") {
    throw "Provide a local Google OAuth Desktop client .json file."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Setup = Join-Path $PSScriptRoot "setup_drive_oauth.py"
if (-not (Test-Path -LiteralPath $Setup -PathType Leaf)) {
    throw "OAuth setup helper missing in repository."
}

Run-SafeNative "Checking GitHub login..." { gh auth status }
Run-SafeNative "Installing OAuth libraries..." {
    py -3 -m pip install "google-auth-oauthlib>=1.2,<2" "google-api-python-client>=2.140,<3" "google-auth-httplib2>=0.2,<1"
}
Write-Host ""
Write-Host "Google will open a browser permission screen."
Write-Host "Use account $ExpectedAccount. Scope: full Google Drive."
Write-Host "The archiver code writes only to the designated Simba private folder."
Write-Host "No credentials will be shown or committed."
Write-Host ""

# setup_drive_oauth.py verifies the authenticated Google account and the folder
# before saving encrypted GitHub Actions secrets and setting the enable variable.
Run-SafeNative "Authorizing Google Drive and enabling A2E backups..." {
    py -3 $Setup --client-json $ClientJson --expected-account $ExpectedAccount --repo $Repo --enable
}

Run-SafeNative "Triggering first read-only A2E archive scan..." {
    gh workflow run simba-a2e-drive-archive.yml --repo $Repo
}
Write-Host ""
Write-Host "Initial scan requested. A2E paid generation is not invoked."
Write-Host "Open the repository Actions tab and check the 'Simba A2E — automatic Google Drive backup' workflow."
Write-Host "Google Drive destination: https://drive.google.com/drive/folders/1oMtSCcUOMVU6f2yiS72cevr0NQF58EAj"
Write-Host "Archive is ACTIVE only after an actual successful Drive upload/read-back or verified no-new-tasks scan."
