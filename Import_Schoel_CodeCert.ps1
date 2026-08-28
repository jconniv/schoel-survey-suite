param(
    [string]$PfxPath = "R:\Technology\CodeCerts\SchoelEngineering.pfx",
    [string]$ExpectedThumbprint = "4EFF173D38E827E96A8A2C91A021D12EF5EB2CD8"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $PfxPath)) {
    throw "PFX file was not found: $PfxPath"
}

$password = Read-Host "Enter the SchoelEngineering.pfx password" -AsSecureString
$imported = Import-PfxCertificate -FilePath $PfxPath -CertStoreLocation Cert:\CurrentUser\My -Password $password

$cert = @($imported | Where-Object { $_.Thumbprint -eq $ExpectedThumbprint } | Select-Object -First 1)
if (-not $cert) {
    $cert = Get-ChildItem Cert:\CurrentUser\My\$ExpectedThumbprint -ErrorAction SilentlyContinue
}

if (-not $cert) {
    throw "Imported PFX, but did not find expected thumbprint $ExpectedThumbprint in CurrentUser\My."
}

if (-not $cert.HasPrivateKey) {
    throw "Imported certificate $ExpectedThumbprint, but Windows does not report a private key."
}

Write-Host "Imported Schoel code-signing certificate:"
Write-Host "  Subject: $($cert.Subject)"
Write-Host "  Thumbprint: $($cert.Thumbprint)"
Write-Host "  Has private key: $($cert.HasPrivateKey)"
