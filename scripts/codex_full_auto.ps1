param(
    [Parameter(Mandatory = $true)]
    [string]$Prompt,
    [string]$Base = "main",
    [string]$Branch,
    [string]$CommitMessage,
    [string]$PrTitle,
    [string]$PrBody = "Automated change created by Codex CLI.",
    [ValidateSet("merge", "squash", "rebase")]
    [string]$MergeMethod = "squash"
)

$ErrorActionPreference = "Stop"

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

Require-Command git
Require-Command gh
Require-Command codex

if (-not $Branch) {
    $slug = (($Prompt.ToLowerInvariant() -replace "[^a-z0-9]+", "-").Trim("-"))
    if (-not $slug) {
        $slug = "update"
    }
    if ($slug.Length -gt 40) {
        $slug = $slug.Substring(0, 40).Trim("-")
    }
    $Branch = "codex/$slug"
}

if (-not $CommitMessage) {
    $CommitMessage = "Codex automation: $Prompt"
}

if (-not $PrTitle) {
    $PrTitle = $CommitMessage
}

$currentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($currentBranch -ne $Branch) {
    git checkout -B $Branch
}

codex exec $Prompt

$status = (git status --porcelain).Trim()
if (-not $status) {
    Write-Output "No changes produced; skipping commit and PR creation."
    exit 0
}

git add -A
git commit -m $CommitMessage

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "pr_auto.ps1") `
    -Base $Base `
    -Title $PrTitle `
    -Body $PrBody `
    -MergeMethod $MergeMethod `
    -AutoMerge
