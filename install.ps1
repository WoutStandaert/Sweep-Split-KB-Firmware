<#
.SYNOPSIS
  Installs KMK + the Ferris Sweep firmware onto a KB2040 running CircuitPython.

.EXAMPLE
  .\install.ps1 -Drive E -Side L
  .\install.ps1 -Drive E -Side R -OverwriteKeymap

.NOTES
  The half must already run CircuitPython (it shows up as a CIRCUITPY drive).
  Run once per half. Renaming the drive may need an elevated PowerShell;
  if it fails, rename the drive in Explorer instead (right-click > Rename).
#>
param(
    [Parameter(Mandatory)] [string] $Drive,
    [Parameter(Mandatory)] [ValidateSet('L', 'R')] [string] $Side,
    [switch] $OverwriteKeymap
)

$ErrorActionPreference = 'Stop'
$letter = $Drive.TrimEnd(':', '\')
$root = "${letter}:\"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path (Join-Path $root 'boot_out.txt'))) {
    throw "$root doesn't look like a CircuitPython drive (no boot_out.txt)."
}
Write-Host "CircuitPython: $(Get-Content (Join-Path $root 'boot_out.txt') -TotalCount 1)"

# 1. KMK library (pinned to the main branch snapshot at install time)
$tmp = Join-Path $env:TEMP "sweep-kmk-$(Get-Random)"
New-Item -ItemType Directory $tmp | Out-Null
try {
    Write-Host 'Downloading KMK...'
    $zip = Join-Path $tmp 'kmk.zip'
    Invoke-WebRequest 'https://github.com/KMKfw/kmk_firmware/archive/refs/heads/main.zip' -OutFile $zip -UseBasicParsing
    Expand-Archive $zip -DestinationPath $tmp
    $kmkSrc = Get-ChildItem $tmp -Directory | Where-Object Name -like 'kmk_firmware-*' | Select-Object -First 1
    $kmkDst = Join-Path $root 'kmk'
    if (Test-Path $kmkDst) { Remove-Item $kmkDst -Recurse -Force }
    Write-Host 'Copying kmk/ to the keyboard...'
    Copy-Item (Join-Path $kmkSrc.FullName 'kmk') $kmkDst -Recurse
}
finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

# 2. Firmware + keymap
Copy-Item (Join-Path $here 'firmware\code.py') (Join-Path $root 'code.py') -Force
$keymapDst = Join-Path $root 'keymap.json'
if ($OverwriteKeymap -or -not (Test-Path $keymapDst)) {
    Copy-Item (Join-Path $here 'firmware\keymap.json') $keymapDst -Force
    Write-Host 'Installed default keymap.json'
} else {
    Write-Host 'Kept existing keymap.json (use -OverwriteKeymap to replace it)'
}

# 3. Drive label decides which half this is
$label = "SWEEP$Side"
try {
    Set-Volume -DriveLetter $letter -NewFileSystemLabel $label
    Write-Host "Drive renamed to $label"
} catch {
    Write-Warning "Couldn't rename the drive ($($_.Exception.Message)). Rename it to $label in Explorer."
}

Write-Host "Done. The $Side half reloads by itself; its LED flashes green when the keymap loads."
