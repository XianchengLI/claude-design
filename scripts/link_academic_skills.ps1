<#
.SYNOPSIS
  Link the central academic skill set into one project: NTFS junctions for the skills (no admin
  rights needed) plus an in-repo copy of the academic rules (imports cannot leave the repo).

.DESCRIPTION
  Central set:  ~/Documents/claude-design/skills/academic/<skill>/   (one folder per skill)
  Central rules:~/Documents/claude-design/rules/academic-rules.md

  Per project:  .claude/skills/<skill>     -> junction to the central skill folder
                .claude/academic-rules.md  -> COPY of the central rules file
                CLAUDE.local.md            -> "@./.claude/academic-rules.md" import line
                .git/info/exclude          -> all of the above (never touches the shared .gitignore)
                <scripts>/linked-repos.txt -> registry of linked repos, for -All

  Restart the Claude Code session afterwards: skills and imports are read at session start.

.USAGE  (run from the repo root, or pass -Repo)
  link_academic_skills.ps1                 # link everything (idempotent; also refreshes the rules copy)
  link_academic_skills.ps1 link -All       # refresh every repo in the registry (use after editing the rules)
  link_academic_skills.ps1 unlink          # remove junctions, rules copy, exclude block and import line
  link_academic_skills.ps1 doctor [-All]   # dangling junctions, unlinked skills, stale rules copy, import status
  link_academic_skills.ps1 list            # central skills

  Verified 2026-09-09:
   - git add follows a junction (hence the exclude block); git clean -fdx, Git Bash rm -rf and
     PowerShell Remove-Item -Recurse remove only the junction, never the central files.
   - CLAUDE.md/CLAUDE.local.md "@" imports resolve ONLY real relative paths inside the repo:
     "@~/..." and "@C:/..." are silently ignored, and a junction is not traversed. That is why the
     rules are copied in rather than imported from the central location. `doctor` hash-checks the copy.
#>
param(
  [ValidateSet("link", "unlink", "doctor", "list")]
  [string]$Action = "link",
  [string]$Repo = (Get-Location).Path,
  [string]$Central = (Join-Path $HOME "Documents\claude-design\skills\academic"),
  [string]$Rules = (Join-Path $HOME "Documents\claude-design\rules\academic-rules.md"),
  [switch]$All
)

$ErrorActionPreference = "Stop"
$ImportLine = "@./.claude/academic-rules.md"
$LegacyImports = @("@~/Documents/claude-design/rules/academic-rules.md")
$LocalHeader = "# Personal, machine-local Claude settings for this repo (not committed; see .git/info/exclude)."
$BlockStart = "# >>> academic-skills (managed by link_academic_skills.ps1)"
$BlockEnd = "# <<< academic-skills"
$RulesRel = ".claude/academic-rules.md"
$Registry = Join-Path $PSScriptRoot "linked-repos.txt"

function Write-Utf8([string]$path, [string[]]$lines) {
  # PS 5.1 "-Encoding UTF8" writes a BOM; in .git/info/exclude that turns line 1 into a pattern
  # instead of a comment, and it can break the first line of CLAUDE.local.md.
  [IO.File]::WriteAllLines($path, [string[]]$lines, (New-Object Text.UTF8Encoding($false)))
}

function Get-CentralSkills {
  if (-not (Test-Path $Central)) { throw "Central dir not found: $Central" }
  Get-ChildItem -Path $Central -Directory | Where-Object { -not $_.Name.StartsWith("_") -and (Test-Path (Join-Path $_.FullName "SKILL.md")) }
}

function Get-ExcludePath([string]$repoPath) {
  $p = (& git -C $repoPath rev-parse --git-path info/exclude 2>$null)
  if (-not $p) { throw "Not a git repo: $repoPath" }
  if (-not [IO.Path]::IsPathRooted($p)) { $p = Join-Path $repoPath $p }
  return $p
}

function Write-ExcludeBlock([string]$repoPath, [string[]]$entries) {
  $path = Get-ExcludePath $repoPath
  $dir = Split-Path $path -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  $existing = @()
  if (Test-Path $path) { $existing = @(Get-Content $path -Encoding UTF8) }
  $kept = @(); $skip = $false
  foreach ($l in $existing) {
    if ($l -eq $BlockStart) { $skip = $true; continue }
    if ($l -eq $BlockEnd) { $skip = $false; continue }
    if (-not $skip) { $kept += $l }
  }
  if ($entries.Count -gt 0) {
    $kept = $kept + @($BlockStart) + $entries + @($BlockEnd)
  }
  Write-Utf8 $path $kept
}

function Is-JunctionInto([IO.FileSystemInfo]$item) {
  if ($item.LinkType -ne "Junction") { return $false }
  $t = ($item.Target | Select-Object -First 1)
  return ($t -and $t.ToLower().StartsWith($Central.ToLower()))
}

function Get-Hash([string]$path) {
  if (-not (Test-Path $path)) { return $null }
  return (Get-FileHash -Path $path -Algorithm SHA256).Hash
}

function Get-Registry {
  if (-not (Test-Path $Registry)) { return @() }
  $out = @()
  foreach ($l in (Get-Content $Registry -Encoding UTF8)) {
    $t = $l.Trim()
    if ($t -and -not $t.StartsWith("#") -and (Test-Path (Join-Path $t ".git"))) { $out += $t }
  }
  return $out
}

function Set-Registry([string[]]$paths) {
  $sorted = @($paths | Sort-Object -Unique)
  Write-Utf8 $Registry $sorted
}

function Add-Registry([string]$repoPath) {
  $cur = @()
  if (Test-Path $Registry) { $cur = @(Get-Content $Registry -Encoding UTF8 | Where-Object { $_.Trim() }) }
  if ($cur -notcontains $repoPath) { Set-Registry ($cur + @($repoPath)) }
}

function Remove-Registry([string]$repoPath) {
  if (-not (Test-Path $Registry)) { return }
  $cur = @(Get-Content $Registry -Encoding UTF8 | Where-Object { $_.Trim() -and $_ -ne $repoPath })
  Set-Registry $cur
}

function Set-ImportLine([string]$localMd) {
  # drop any legacy import line, guarantee exactly one current one
  if (-not (Test-Path $localMd)) {
    Write-Utf8 $localMd @($LocalHeader, $ImportLine)
    return
  }
  $lines = @(Get-Content $localMd -Encoding UTF8)
  $clean = @($lines | Where-Object { $LegacyImports -notcontains $_ })
  if ($clean -notcontains $ImportLine) { $clean += $ImportLine }
  Write-Utf8 $localMd $clean
}

function Do-Link([string]$repoPath) {
  $skillsDir = Join-Path $repoPath ".claude\skills"
  $claudeDir = Join-Path $repoPath ".claude"
  $localMd = Join-Path $repoPath "CLAUDE.local.md"
  $rulesDst = Join-Path $repoPath ".claude\academic-rules.md"

  if (-not (Test-Path $Rules)) { throw "Central rules file not found: $Rules" }
  if (-not (Test-Path $skillsDir)) { New-Item -ItemType Directory -Force $skillsDir | Out-Null }

  $linked = @(); $skipped = @()
  foreach ($s in Get-CentralSkills) {
    $dst = Join-Path $skillsDir $s.Name
    if (Test-Path $dst) {
      $item = Get-Item $dst -Force
      if (Is-JunctionInto $item) { $linked += $s.Name; continue }
      $skipped += $s.Name
      Write-Warning "skip $($s.Name): $dst exists and is not a junction into the central dir"
      continue
    }
    New-Item -ItemType Junction -Path $dst -Target $s.FullName | Out-Null
    $linked += $s.Name
  }

  Copy-Item -Path $Rules -Destination $rulesDst -Force
  Set-ImportLine $localMd

  $entries = @("CLAUDE.local.md", $RulesRel) + ($linked | ForEach-Object { ".claude/skills/$_/" })
  Write-ExcludeBlock $repoPath $entries
  Add-Registry $repoPath

  Write-Output ("[{0}] linked {1} skill(s); rules copied to {2}" -f (Split-Path $repoPath -Leaf), $linked.Count, $RulesRel)
  if ($skipped.Count) { Write-Output ("  skipped (real folders): " + ($skipped -join ", ")) }
}

function Do-Unlink([string]$repoPath) {
  $skillsDir = Join-Path $repoPath ".claude\skills"
  $localMd = Join-Path $repoPath "CLAUDE.local.md"
  $rulesDst = Join-Path $repoPath ".claude\academic-rules.md"

  $removed = 0
  if (Test-Path $skillsDir) {
    foreach ($item in Get-ChildItem $skillsDir -Force) {
      if (Is-JunctionInto $item) { [IO.Directory]::Delete($item.FullName); $removed++ }
    }
  }
  if (Test-Path $rulesDst) { Remove-Item $rulesDst -Force }
  Write-ExcludeBlock $repoPath @()
  if (Test-Path $localMd) {
    $drop = @($ImportLine) + $LegacyImports
    $rest = @(Get-Content $localMd -Encoding UTF8 | Where-Object { $drop -notcontains $_ })
    $meaningful = @($rest | Where-Object { $_.Trim() -and $_ -ne $LocalHeader })
    if ($meaningful.Count -eq 0) { Remove-Item $localMd } else { Write-Utf8 $localMd $rest }
  }
  Remove-Registry $repoPath
  Write-Output ("[{0}] removed {1} junction(s); rules copy, exclude block and import line cleared" -f (Split-Path $repoPath -Leaf), $removed)
}

function Do-Doctor([string]$repoPath) {
  $skillsDir = Join-Path $repoPath ".claude\skills"
  $localMd = Join-Path $repoPath "CLAUDE.local.md"
  $rulesDst = Join-Path $repoPath ".claude\academic-rules.md"
  $tag = Split-Path $repoPath -Leaf

  $centralNames = @()   # NOT $central: PowerShell variables are case-insensitive and $Central is the param
  foreach ($s in Get-CentralSkills) { $centralNames += $s.Name }
  $present = @()
  if (Test-Path $skillsDir) {
    foreach ($item in Get-ChildItem $skillsDir -Force) {
      if ($item.LinkType -eq "Junction") {
        $t = ($item.Target | Select-Object -First 1)
        if (-not (Test-Path $t)) { Write-Output "[$tag] DANGLING  $($item.Name) -> $t" } else { $present += $item.Name }
      }
    }
  }
  foreach ($n in $centralNames) { if ($present -notcontains $n) { Write-Output "[$tag] UNLINKED  $n" } }
  foreach ($n in $present) { if ($centralNames -notcontains $n) { Write-Output "[$tag] STALE     $n (linked, no longer in central)" } }

  $rulesState = "MISSING"
  $srcHash = Get-Hash $Rules
  $dstHash = Get-Hash $rulesDst
  if ($dstHash) { if ($dstHash -eq $srcHash) { $rulesState = "ok" } else { $rulesState = "STALE (re-run link)" } }

  $localLines = @()
  if (Test-Path $localMd) { $localLines = @(Get-Content $localMd -Encoding UTF8) }
  $hasImport = ($localLines -contains $ImportLine)
  $legacy = @($localLines | Where-Object { $LegacyImports -contains $_ })
  if ($legacy.Count) { Write-Output "[$tag] LEGACY    dead import line in CLAUDE.local.md (re-run link): $($legacy[0])" }

  $excl = Get-ExcludePath $repoPath
  $hasBlock = (Test-Path $excl) -and ((Get-Content $excl -Encoding UTF8) -contains $BlockStart)
  Write-Output ("[{0}] linked {1}/{2}; rules copy: {3}; import line: {4}; exclude block: {5}" -f $tag, $present.Count, $centralNames.Count, $rulesState, $hasImport, $hasBlock)
}

# ---- main ----
if ($Action -eq "list") {
  foreach ($s in Get-CentralSkills) { Write-Output $s.Name }
  return
}

$targets = @()
if ($All) {
  $targets = Get-Registry
  if ($targets.Count -eq 0) { throw "Registry empty or missing: $Registry" }
} else {
  if (-not (Test-Path (Join-Path $Repo ".git"))) { throw "No .git at $Repo (pass -Repo <path> or run from the repo root)" }
  $targets = @((Resolve-Path $Repo).Path)
}

foreach ($t in $targets) {
  switch ($Action) {
    "link"   { Do-Link $t }
    "unlink" { Do-Unlink $t }
    "doctor" { Do-Doctor $t }
  }
}

if ($Action -eq "link") {
  Write-Output "Restart the Claude Code session in these repos to load the skills and rules."
  Write-Output "Registry: $Registry"
}
