param(
    [string]$Base = "main",
    [string]$Title,
    [string]$Body = "Automated change created by Codex CLI.",
    [ValidateSet("merge", "squash", "rebase")]
    [string]$MergeMethod = "squash",
    [switch]$AutoMerge,
    [switch]$Draft
)

$ErrorActionPreference = "Stop"

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

Require-Command git
Require-Command gh

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -eq "HEAD") {
    throw "Detached HEAD is not supported."
}
if ($branch -eq $Base) {
    throw "Current branch '$branch' matches base branch '$Base'. Create or switch to a feature branch first."
}

git push -u origin $branch

if (-not $Title) {
    $Title = "Codex automation: $branch"
}

$existingNumber = ""
try {
    $existingNumber = (gh pr view $branch --json number --jq ".number" 2>$null).Trim()
} catch {
    $existingNumber = ""
}

if ($existingNumber) {
    gh pr edit $existingNumber --title $Title --body $Body | Out-Null
    $prNumber = $existingNumber
} else {
    $createArgs = @(
        "pr", "create",
        "--base", $Base,
        "--head", $branch,
        "--title", $Title,
        "--body", $Body
    )
    if ($Draft) {
        $createArgs += "--draft"
    }
    $prUrl = (& gh @createArgs).Trim()
    $prNumber = ($prUrl -split "/")[-1]
}

if ($AutoMerge) {
    gh pr merge $prNumber --auto --$MergeMethod --delete-branch=false | Out-Null
}

Write-Output "PR ready: #$prNumber"
