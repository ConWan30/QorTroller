# Publish docs/discussions/*.md as GitHub Discussions.
# Requires Discussions enabled and GH_TOKEN / GITHUB_TOKEN in the environment.
# Never hard-code a PAT in this file.
$ErrorActionPreference = "Stop"
$token = $env:GH_TOKEN
if (-not $token) { $token = $env:GITHUB_TOKEN }
if (-not $token) { throw "Set GH_TOKEN or GITHUB_TOKEN in the environment. Do not put a PAT in the repo." }

$headers = @{
  Authorization = "Bearer $token"
  Accept = "application/vnd.github+json"
}

$repoQuery = @{ query = "query { repository(owner: `"ConWan30`", name: `"QorTroller`") { id discussionCategories(first: 20) { nodes { id name } } } }" } | ConvertTo-Json
$repoInfo = Invoke-RestMethod -Method POST -Uri "https://api.github.com/graphql" -Headers $headers -ContentType "application/json" -Body $repoQuery
$repoId = $repoInfo.data.repository.id
$announce = ($repoInfo.data.repository.discussionCategories.nodes | Where-Object { $_.name -eq "Announcements" }).id
$qa = ($repoInfo.data.repository.discussionCategories.nodes | Where-Object { $_.name -eq "Q&A" }).id

$posts = @(
  @{ file = "01-welcome.md"; category = $announce },
  @{ file = "02-two-planes.md"; category = $announce },
  @{ file = "03-zero-secrets.md"; category = $qa }
)

$repoRoot = Split-Path -Parent $PSScriptRoot
foreach ($post in $posts) {
  $path = Join-Path $repoRoot "docs\discussions\$($post.file)"
  $raw = Get-Content -Raw -Path $path
  $lines = $raw -split "`n", 2
  $title = $lines[0].TrimStart("#").Trim()
  $body = if ($lines.Count -gt 1) { $lines[1].Trim() } else { $title }
  $mutation = @{
    query = "mutation(`$repoId:ID!, `$categoryId:ID!, `$title:String!, `$body:String!) { createDiscussion(input: {repositoryId: `$repoId, categoryId: `$categoryId, title: `$title, body: `$body}) { discussion { number url } } }"
    variables = @{ repoId = $repoId; categoryId = $post.category; title = $title; body = $body }
  } | ConvertTo-Json -Depth 6
  $result = Invoke-RestMethod -Method POST -Uri "https://api.github.com/graphql" -Headers $headers -ContentType "application/json" -Body $mutation
  if ($result.errors) { $result.errors | ConvertTo-Json -Depth 6; throw "Discussion create failed for $($post.file)" }
  Write-Host $result.data.createDiscussion.discussion.url
}
