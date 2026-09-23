<# :
@echo off
setlocal
cd /d "%~dp0"
set "SCRIPT_FILE=%~f0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression (Get-Content -Path $env:SCRIPT_FILE -Raw)"
set "EXITCODE=%ERRORLEVEL%"

echo.
if %EXITCODE% equ 0 (
    echo ========================================================
    echo   Installation completed successfully!
    echo ========================================================
) else (
    echo ========================================================
    echo   [ERROR] Installation failed with exit code %EXITCODE%.
    echo ========================================================
)
echo.
pause
exit /b %EXITCODE%
: #>

# -----------------------------------------------------------------------------
# SteamDepotDownloaderModBuddy (SDDMB) - Tool Dependencies Installer
# Downloads and sets up the latest releases for:
#   1. SteamAutoCracks/DepotDownloaderMod -> DDM\
#   2. atom0s/Steamless                 -> Steamless\
#   3. UnionCrax-Team/uc-online2        -> UC2\
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

$baseDir = Split-Path -Parent $env:SCRIPT_FILE
Set-Location $baseDir

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   SteamDepotDownloaderModBuddy (SDDMB) - Installer" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Target Directory: $baseDir" -ForegroundColor Gray
Write-Host ""

$tempDir = Join-Path $baseDir "_temp_installer"
if (Test-Path $tempDir) {
    Remove-Item -Path $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

function Get-LatestAssetInfo([string]$repo, [string]$pattern, [string]$directFallbackUrl = "") {
    $headers = @{ 'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }
    
    # 1. Try GitHub REST API
    try {
        $apiUrl = "https://api.github.com/repos/$repo/releases/latest"
        $r = Invoke-RestMethod -Uri $apiUrl -Headers $headers -TimeoutSec 15 -ErrorAction Stop
        foreach ($asset in $r.assets) {
            if ($asset.name -like $pattern) {
                return @{
                    Tag = $r.tag_name
                    Name = $asset.name
                    Url = $asset.browser_download_url
                }
            }
        }
    } catch {}

    # 2. Try web scraping the /releases/latest redirect (helps when API rate limits unauthenticated requests)
    try {
        $webUrl = "https://github.com/$repo/releases/latest"
        $web = Invoke-WebRequest -Uri $webUrl -Headers $headers -MaximumRedirection 5 -TimeoutSec 15 -ErrorAction Stop
        foreach ($link in $web.Links) {
            if ($link.href -like "*/releases/download/*" -and $link.href -like "*$pattern*") {
                $fullUrl = if ($link.href -like "http*") { $link.href } else { "https://github.com" + $link.href }
                $fname = [System.IO.Path]::GetFileName($fullUrl)
                return @{
                    Tag = "latest"
                    Name = $fname
                    Url = $fullUrl
                }
            }
        }
    } catch {}

    # 3. Direct URL fallback if provided
    if ($directFallbackUrl) {
        return @{
            Tag = "latest"
            Name = [System.IO.Path]::GetFileName($directFallbackUrl)
            Url = $directFallbackUrl
        }
    }

    return $null
}

function Download-File([string]$url, [string]$outFile) {
    # Prefer curl.exe for progress and robust redirect handling
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -fL --progress-bar -o $outFile $url
        if ($LASTEXITCODE -eq 0 -and (Test-Path $outFile)) {
            return $true
        }
    }
    
    # Fallback to Invoke-WebRequest
    try {
        $headers = @{ 'User-Agent' = 'Mozilla/5.0' }
        Invoke-WebRequest -Uri $url -OutFile $outFile -Headers $headers -TimeoutSec 180
        return (Test-Path $outFile)
    } catch {
        Write-Host "Failed to download $url : $_" -ForegroundColor Red
        return $false
    }
}

function Extract-ArchiveFile([string]$archivePath, [string]$destination) {
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    
    if ($archivePath.EndsWith(".zip", [System.StringComparison]::OrdinalIgnoreCase)) {
        try {
            Expand-Archive -LiteralPath $archivePath -DestinationPath $destination -Force -ErrorAction Stop
            return $true
        } catch {
            if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
                & tar.exe -xf $archivePath -C $destination
                return ($LASTEXITCODE -eq 0)
            }
            return $false
        }
    } else {
        # .rar or other formats supported by Windows bsdtar (tar.exe)
        if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
            & tar.exe -xf $archivePath -C $destination
            return ($LASTEXITCODE -eq 0)
        } else {
            Write-Host "tar.exe not found to extract $archivePath" -ForegroundColor Red
            return $false
        }
    }
}

try {
    # =========================================================================
    # [1/3] DepotDownloaderMod (SteamAutoCracks/DepotDownloaderMod)
    # =========================================================================
    Write-Host "[1/3] Finding latest DepotDownloaderMod release..." -ForegroundColor Yellow
    $ddmInfo = Get-LatestAssetInfo -repo "SteamAutoCracks/DepotDownloaderMod" -pattern "*.rar" -directFallbackUrl "https://github.com/SteamAutoCracks/DepotDownloaderMod/releases/latest/download/Release.rar"
    if (-not $ddmInfo) {
        throw "Could not determine DepotDownloaderMod release download URL."
    }
    Write-Host "      Found: $($ddmInfo.Name) ($($ddmInfo.Tag))" -ForegroundColor Gray
    Write-Host "      Downloading DepotDownloaderMod..." -ForegroundColor Gray
    $ddmArchive = Join-Path $tempDir "ddm.rar"
    if (-not (Download-File -url $ddmInfo.Url -outFile $ddmArchive)) {
        throw "Failed to download DepotDownloaderMod from $($ddmInfo.Url)"
    }

    Write-Host "      Extracting DepotDownloaderMod..." -ForegroundColor Gray
    $ddmExtract = Join-Path $tempDir "ddm_extracted"
    if (-not (Extract-ArchiveFile -archivePath $ddmArchive -destination $ddmExtract)) {
        throw "Failed to extract DepotDownloaderMod archive."
    }

    $ddmExe = Get-ChildItem -Path $ddmExtract -Filter "DepotDownloaderMod.exe" -Recurse | Select-Object -First 1
    if (-not $ddmExe) {
        throw "DepotDownloaderMod.exe was not found inside the extracted archive."
    }

    $ddmTarget = Join-Path $baseDir "DDM"
    New-Item -ItemType Directory -Force -Path $ddmTarget | Out-Null
    Copy-Item -Path (Join-Path $ddmExe.DirectoryName "*") -Destination $ddmTarget -Recurse -Force
    Write-Host "  [OK] DepotDownloaderMod installed to DDM\" -ForegroundColor Green

    # =========================================================================
    # [2/3] Steamless (atom0s/Steamless)
    # =========================================================================
    Write-Host "[2/3] Finding latest Steamless release..." -ForegroundColor Yellow
    $steamlessInfo = Get-LatestAssetInfo -repo "atom0s/Steamless" -pattern "*.zip"
    if (-not $steamlessInfo) {
        throw "Could not determine Steamless release download URL."
    }
    Write-Host "      Found: $($steamlessInfo.Name) ($($steamlessInfo.Tag))" -ForegroundColor Gray
    Write-Host "      Downloading Steamless..." -ForegroundColor Gray
    $steamlessArchive = Join-Path $tempDir "steamless.zip"
    if (-not (Download-File -url $steamlessInfo.Url -outFile $steamlessArchive)) {
        throw "Failed to download Steamless from $($steamlessInfo.Url)"
    }

    Write-Host "      Extracting Steamless..." -ForegroundColor Gray
    $steamlessTarget = Join-Path $baseDir "Steamless"
    New-Item -ItemType Directory -Force -Path $steamlessTarget | Out-Null
    if (-not (Extract-ArchiveFile -archivePath $steamlessArchive -destination $steamlessTarget)) {
        throw "Failed to extract Steamless archive."
    }
    Write-Host "  [OK] Steamless installed to Steamless\" -ForegroundColor Green

    # =========================================================================
    # [3/3] uc-online2 (UnionCrax-Team/uc-online2)
    # =========================================================================
    Write-Host "[3/3] Finding latest uc-online2 release..." -ForegroundColor Yellow
    $ucInfo = Get-LatestAssetInfo -repo "UnionCrax-Team/uc-online2" -pattern "*release*.zip"
    if (-not $ucInfo) {
        throw "Could not determine uc-online2 release download URL."
    }
    Write-Host "      Found: $($ucInfo.Name) ($($ucInfo.Tag))" -ForegroundColor Gray
    Write-Host "      Downloading uc-online2..." -ForegroundColor Gray
    $ucArchive = Join-Path $tempDir "uc.zip"
    if (-not (Download-File -url $ucInfo.Url -outFile $ucArchive)) {
        throw "Failed to download uc-online2 from $($ucInfo.Url)"
    }

    Write-Host "      Extracting uc-online2..." -ForegroundColor Gray
    $ucExtract = Join-Path $tempDir "uc_extracted"
    if (-not (Extract-ArchiveFile -archivePath $ucArchive -destination $ucExtract)) {
        throw "Failed to extract uc-online2 archive."
    }

    $dll64 = Get-ChildItem -Path $ucExtract -Filter "steam_api64.dll" -Recurse | Where-Object { $_.FullName -like "*x64*" } | Select-Object -First 1
    if (-not $dll64) {
        $dll64 = Get-ChildItem -Path $ucExtract -Filter "steam_api64.dll" -Recurse | Select-Object -First 1
    }
    if (-not $dll64) {
        throw "steam_api64.dll was not found inside the extracted uc-online2 archive."
    }

    $ucTarget = Join-Path $baseDir "UC2"
    New-Item -ItemType Directory -Force -Path $ucTarget | Out-Null
    Copy-Item -Path $dll64.FullName -Destination (Join-Path $ucTarget "steam_api64.dll") -Force

    # Ensure union-crax.ini exists
    $iniUnionCrax = Join-Path $ucTarget "union-crax.ini"
    if (-not (Test-Path $iniUnionCrax)) {
        Set-Content -Path $iniUnionCrax -Value ("[Settings]" + [Environment]::NewLine + "GetStubbedLol=true") -Encoding utf8
    }
    Write-Host "  [OK] uc-online2 installed to UC2\" -ForegroundColor Green

} catch {
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
} finally {
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
