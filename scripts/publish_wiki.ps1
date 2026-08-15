# Publish docs/wiki/*.md to the GitHub Wiki.
# Requires Wiki enabled and GH_TOKEN / GITHUB_TOKEN in the environment.
# Never hard-code a PAT in this file.
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$wikiSrc = Join-Path $repoRoot "docs\wiki"
$token = $env:GH_TOKEN
if (-not $token) { $token = $env:GITHUB_TOKEN }
if (-not $token) { throw "Set GH_TOKEN or GITHUB_TOKEN in the environment. Do not put a PAT in the repo." }

$tmp = Join-Path $env:TEMP "qortroller-wiki"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
git clone "https://x-access-token:$token@github.com/ConWan30/QorTroller.wiki.git" $tmp
Copy-Item (Join-Path $wikiSrc "*.md") $tmp -Force
Push-Location $tmp
try {
  git add *.md
  git status --porcelain
  git commit -m "docs(wiki): sync from docs/wiki"
  git push origin HEAD
} finally {
  Pop-Location
}
