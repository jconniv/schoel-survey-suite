param(
    [string[]]$Path,
    [string]$Thumbprint = "4EFF173D38E827E96A8A2C91A021D12EF5EB2CD8",
    [string]$TimestampServer = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Find-SignTool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $searchRoots = @(
        "${env:ProgramFiles(x86)}\Windows Kits",
        "$env:ProgramFiles\Microsoft Visual Studio",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio"
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($root in $searchRoots) {
        $matches = @(Get-ChildItem -Path $root -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue)
        $match = $matches |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if (-not $match) {
            $match = $matches |
                Where-Object { $_.FullName -notmatch '\\arm64\\|\\x86\\' } |
                Sort-Object FullName -Descending |
                Select-Object -First 1
        }
        if (-not $match) {
            $match = $matches |
                Sort-Object FullName -Descending |
                Select-Object -First 1
        }
        if ($match) {
            return $match.FullName
        }
    }

    throw "signtool.exe was not found. Install the Windows SDK or add signtool.exe to PATH, then rebuild."
}

function Find-CodeSigningCert {
    param([string]$Thumbprint)

    $stores = @(
        @{ Path = "Cert:\CurrentUser\My"; UseMachineStore = $false },
        @{ Path = "Cert:\LocalMachine\My"; UseMachineStore = $true }
    )

    foreach ($store in $stores) {
        $cert = Get-ChildItem $store.Path -ErrorAction SilentlyContinue |
            Where-Object { $_.Thumbprint -eq $Thumbprint -and $_.HasPrivateKey } |
            Select-Object -First 1
        if ($cert) {
            return [pscustomobject]@{
                Certificate = $cert
                UseMachineStore = $store.UseMachineStore
            }
        }
    }

    throw "Certificate $Thumbprint with a private key was not found in CurrentUser\My or LocalMachine\My."
}

function Get-DefaultTargets {
    $patterns = @(
        "dist\*.exe",
        "release_dist\*.exe",
        "installer_out\*.msi",
        "legal_writer_angle\dist\*.exe",
        "legal_writer_bearing\dist\*.exe",
        "plotter_angle\dist\*.exe"
    )

    foreach ($pattern in $patterns) {
        Get-ChildItem -Path (Join-Path $Root $pattern) -File -ErrorAction SilentlyContinue
    }

    $knownProductOutputs = @(
        "C:\SchoelTools\GradeGuard\SchoelGradeGuard_v8_5_7\dist\SchoelGradeGuard_v7_8.exe",
        "C:\SchoelTools\GradeGuard\SchoelGradeGuard_v9_0_Survey_Package_Mode\dist\SchoelGradeGuard_v7_8.exe",
        "C:\SchoelTools\GradeGuard\SchoelGradeGuard_v8_5_7\installer_out\SchoelGradeGuard*.msi",
        "C:\SchoelTools\GradeGuard\SchoelGradeGuard_v9_0_Survey_Package_Mode\installer_out\SchoelGradeGuard*.msi",
        "C:\SchoelTools\GradeGuard\SchoelGradeGuard*.msi",
        "R:\SchoelTools\SchoelGradeGuard\SchoelGradeGuard*.msi",
        "C:\SchoelTools\Schoel Survey Suite\SchoelSurveySuite_Build_2026.03.27.23_FULL_FIXED_BEARING_UI_COMMON\dist\SchoelSurveySuite.exe",
        "C:\SchoelTools\Schoel Survey Suite\SchoelSurveySuite_Build_2026.03.27.23_FULL_FIXED_BEARING_UI_COMMON\legal_writer_angle\dist\BirminghamLegalDescriptionWriter.exe",
        "C:\SchoelTools\Schoel Survey Suite\SchoelSurveySuite_Build_2026.03.27.23_FULL_FIXED_BEARING_UI_COMMON\legal_writer_bearing\dist\SchoelLegalDescriptionGenerator.exe",
        "C:\SchoelTools\SchoelComparePDFUSFT\SchoelComparePDFUSFT.exe",
        "C:\SchoelTools\SchoelComparePDFUSFT_Updates\SchoelComparePDFUSFT-25.0.0.msi",
        "C:\SchoelTools\SchoelComparePDFUSFT_Updates\SchoelComparePDFUSFT-25.0.1.msi",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\Schoel GradeGuard\SchoelGradeGuard_v9_0_Survey_Package_Mode\dist\SchoelGradeGuard_v7_8.exe",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\Schoel GradeGuard\SchoelGradeGuard_v9_0_Survey_Package_Mode\installer_out\SchoelGradeGuard*.msi",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\Schoel GradeGuard\SchoelGradeGuard*.msi",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\Schoel_Compare_PDF_USFT_v25_WITH_LSP\Schoel_Compare_PDF_USFT_v24_LOGO_SCROLL\dist\SchoelComparePDFUSFT.exe",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\from H\Schoel_Compare_PDF_USFT_v24_LOGO_SCROLL\dist\SchoelComparePDFUSFT.exe",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\SchoelSurveySuite_Build_2026.03.27.23_FULL_FIXED_BEARING_UI_COMMON\dist\SchoelSurveySuite.exe",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\SchoelSurveySuite_Build_2026.03.27.23_FULL_FIXED_BEARING_UI_COMMON\legal_writer_angle\dist\BirminghamLegalDescriptionWriter.exe",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\SchoelSurveySuite_Build_2026.03.27.23_FULL_FIXED_BEARING_UI_COMMON\legal_writer_bearing\dist\SchoelLegalDescriptionGenerator.exe",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\from H\Schoel Survey Suite Legal and Deed Plotter\SchoelSurveySuite.exe",
        "C:\Users\joeco\OneDrive - Schoel Engineering\Desktop\Schoel Programs\.MSI\SchoelSurveySuite_2026.03.27.msi"
    )

    foreach ($output in $knownProductOutputs) {
        if ($output -match '[\*\?]') {
            Get-ChildItem -Path $output -File -ErrorAction SilentlyContinue
        } else {
            Get-Item -LiteralPath $output -ErrorAction SilentlyContinue
        }
    }
}

if (-not $Path -or $Path.Count -eq 0) {
    $targets = @(Get-DefaultTargets)
} else {
    $targets = foreach ($item in $Path) {
        if ([System.IO.Path]::IsPathRooted($item)) {
            Get-Item -LiteralPath $item -ErrorAction Stop
        } else {
            Get-Item -LiteralPath (Join-Path $Root $item) -ErrorAction Stop
        }
    }
}

$targets = @($targets | Where-Object { $_.Extension -match '^\.(exe|msi)$' } | Sort-Object FullName -Unique)
if ($targets.Count -eq 0) {
    Write-Host "No EXE or MSI targets found to sign."
    exit 0
}

$signTool = Find-SignTool
$certInfo = Find-CodeSigningCert -Thumbprint $Thumbprint

Write-Host "Using certificate: $($certInfo.Certificate.Subject)"
Write-Host "Thumbprint: $Thumbprint"
Write-Host "Signer: $signTool"

foreach ($target in $targets) {
    Write-Host "Signing $($target.FullName)"

    $args = @(
        "sign",
        "/fd", "SHA256",
        "/sha1", $Thumbprint,
        "/tr", $TimestampServer,
        "/td", "SHA256",
        "/v"
    )

    if ($certInfo.UseMachineStore) {
        $args += "/sm"
    }

    $args += $target.FullName
    & $signTool @args
    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed for $($target.FullName)"
    }

    & $signTool verify /pa /v $target.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Signature verification failed for $($target.FullName)"
    }
}

Write-Host "Signing complete."
