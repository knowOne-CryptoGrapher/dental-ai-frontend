#Requires -Version 5.1
<#
.SYNOPSIS
    Single-command build and deploy for the dental-ai backend.
.DESCRIPTION
    1. Enables Secret Manager API (idempotent).
    2. Creates/updates GCP secrets for all sensitive env vars from backend/.env.
    3. Grants the Cloud Run service account secretAccessor on each secret.
    4. Builds the Docker image via Cloud Build (context = backend/).
    5. Deploys via `gcloud run services replace backend/service.yaml`.
    6. Prints the latest ready revision name and service URL.

USAGE:  .\deploy_backend.ps1
#>

$ErrorActionPreference = "Stop"

$PROJECT   = "dental-ai-backend"
$REGION    = "us-west1"
$SERVICE   = "dental-ai-backend"
$IMAGE     = "gcr.io/$PROJECT/$SERVICE"
$REPO_ROOT = $PSScriptRoot
$BACKEND   = Join-Path $REPO_ROOT "backend"
$SVC_YAML  = Join-Path $BACKEND "service.yaml"

$SECRET_VARS = @(
    "MONGODB_URI",
    "JWT_SECRET_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
    "RETELL_API_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_BASIC",
    "STRIPE_PRICE_PROFESSIONAL",
    "STRIPE_PRICE_ENTERPRISE",
    "STRIPE_PRICE_ELITE",
    "CA_WEST_DB_URI",
    "CA_EAST_DB_URI",
    "INTERNAL_API_KEY",
    "SALES_NOTIFY_EMAIL",
    "SES_ACCESS_KEY_ID",
    "SES_SECRET_ACCESS_KEY",
    "SES_REGION",
    "SES_FROM_EMAIL",
    "SES_FROM_NAME",
    "SES_SNS_TOPIC_ARN",
    "SES_CONFIGURATION_SET",
    "RETELL_WEBHOOK_SECRET"
)

function Write-Step([string]$msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}

# ── 1. Enable Secret Manager API ─────────────────────────────────────────────
Write-Step "Enabling Secret Manager API"
gcloud services enable secretmanager.googleapis.com --project $PROJECT
if ($LASTEXITCODE -ne 0) { throw "Failed to enable Secret Manager API" }

# ── 2. Provision secrets from backend/.env ────────────────────────────────────
Write-Step "Provisioning secrets"
$ENV_FILE = Join-Path $BACKEND ".env"
if (-not (Test-Path $ENV_FILE)) { throw ".env not found at $ENV_FILE" }

$envVars = @{}
foreach ($line in Get-Content $ENV_FILE) {
    if ($line -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$') {
        $envVars[$Matches[1]] = $Matches[2].Trim()
    }
}

# Day-one: if regional DB URIs are not in .env, use MONGODB_URI as the fallback value.
# When Atlas clusters are split, set explicit values in .env (or Secret Manager directly).
if (-not $envVars.ContainsKey("CA_WEST_DB_URI") -or [string]::IsNullOrWhiteSpace($envVars["CA_WEST_DB_URI"])) {
    $envVars["CA_WEST_DB_URI"] = $envVars["MONGODB_URI"]
}
if (-not $envVars.ContainsKey("CA_EAST_DB_URI") -or [string]::IsNullOrWhiteSpace($envVars["CA_EAST_DB_URI"])) {
    $envVars["CA_EAST_DB_URI"] = $envVars["MONGODB_URI"]
}

$projectNumber = gcloud projects describe $PROJECT --format="value(projectNumber)"
if ($LASTEXITCODE -ne 0) { throw "Could not retrieve project number" }
$SA = "$projectNumber-compute@developer.gserviceaccount.com"

foreach ($varName in $SECRET_VARS) {
    if (-not $envVars.ContainsKey($varName) -or [string]::IsNullOrWhiteSpace($envVars[$varName])) {
        Write-Warning "  SKIP $varName — missing or empty in .env"
        continue
    }
    $secretValue = $envVars[$varName]
    $tmpFile = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($tmpFile, $secretValue, [System.Text.UTF8Encoding]::new($false))

        gcloud secrets describe $varName --project $PROJECT | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  CREATE  $varName"
            gcloud secrets create $varName --project $PROJECT --data-file=$tmpFile
            if ($LASTEXITCODE -ne 0) { throw "Failed to create secret $varName" }
        } else {
            Write-Host "  UPDATE  $varName"
            gcloud secrets versions add $varName --project $PROJECT --data-file=$tmpFile
            if ($LASTEXITCODE -ne 0) { throw "Failed to update secret $varName" }
        }
    } finally {
        Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
    }

    gcloud secrets add-iam-policy-binding $varName `
        --project $PROJECT `
        --member "serviceAccount:$SA" `
        --role "roles/secretmanager.secretAccessor" `
        --quiet | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to grant IAM binding for $varName" }
}

# ── 3. Build via Cloud Build ──────────────────────────────────────────────────
Write-Step "Building image via Cloud Build"
Push-Location $BACKEND
try {
    gcloud builds submit --tag $IMAGE --project $PROJECT
    if ($LASTEXITCODE -ne 0) { throw "Cloud Build failed" }
} finally {
    Pop-Location
}

# ── 4. Deploy ─────────────────────────────────────────────────────────────────
Write-Step "Deploying to Cloud Run"

# Resolve :latest to its current digest so Cloud Run always creates a new
# revision, even when the service.yaml configuration string is unchanged.
$digest = gcloud container images describe "${IMAGE}:latest" `
    --project $PROJECT --format "value(image_summary.digest)"
if ($LASTEXITCODE -ne 0 -or -not $digest) { throw "Could not resolve image digest" }
$IMAGE_WITH_DIGEST = "${IMAGE}@${digest}"
Write-Host "  Image digest: $IMAGE_WITH_DIGEST"

# Patch service.yaml in-memory with the pinned digest, replace, then leave
# the file on disk still referencing :latest for the next commit.
$svcContent = [System.IO.File]::ReadAllText($SVC_YAML)
$svcPatched  = $svcContent -replace [regex]::Escape("image: ${IMAGE}"), "image: ${IMAGE_WITH_DIGEST}"
$patchedFile = [System.IO.Path]::GetTempFileName() + ".yaml"
[System.IO.File]::WriteAllText($patchedFile, $svcPatched, [System.Text.UTF8Encoding]::new($false))

gcloud run services replace $patchedFile --platform managed --region $REGION --project $PROJECT
$deployResult = $LASTEXITCODE
Remove-Item $patchedFile -Force -ErrorAction SilentlyContinue
if ($deployResult -ne 0) { throw "Deployment failed" }

# ── 5. Summary ────────────────────────────────────────────────────────────────
Write-Step "Done"
$revision = gcloud run services describe $SERVICE --region $REGION --project $PROJECT `
    --format "value(status.latestReadyRevisionName)"
$url = gcloud run services describe $SERVICE --region $REGION --project $PROJECT `
    --format "value(status.url)"
Write-Host "  Revision : $revision" -ForegroundColor Green
Write-Host "  URL      : $url"      -ForegroundColor Green
