param(
    [Parameter(Mandatory = $true)]
    [string]$HostName,

    [string]$User = "ubuntu",
    [string]$KeyPath = "..\..\github-actions-wifi-backend",
    [string]$RemoteRoot = "/opt/rf-service",
    [string]$ImageName = "rf-service-ai-api",
    [string]$ContainerName = "rf-service-ai-api",
    [int]$Port = 9000,
    [string]$EnvFile = ".env",
    [string]$Gpus = "all"
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command ssh
Require-Command scp
Require-Command tar

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$archive = Join-Path ([System.IO.Path]::GetTempPath()) ("rf-service-docker-deploy-{0}.tar.gz" -f ([guid]::NewGuid().ToString("N")))
$remoteArchive = "/tmp/rf-service-docker-deploy.tar.gz"
$sshTarget = "$User@$HostName"
$keyCandidate = if ([System.IO.Path]::IsPathRooted($KeyPath)) {
    $KeyPath
} else {
    Join-Path $PSScriptRoot $KeyPath
}
$resolvedKey = Resolve-Path $keyCandidate
$envPath = Join-Path $repoRoot $EnvFile

Write-Host "[rf-service] packaging Docker build context: $repoRoot"
Push-Location $repoRoot
try {
    tar `
        --exclude ".git" `
        --exclude ".venv" `
        --exclude "apps/ai_api/.venv" `
        --exclude ".ruff_cache" `
        --exclude "__pycache__" `
        --exclude "apps/data/output" `
        -czf $archive .
} finally {
    Pop-Location
}

Write-Host "[rf-service] uploading archive to $sshTarget"
scp -i $resolvedKey $archive "${sshTarget}:${remoteArchive}"

if (Test-Path $envPath) {
    Write-Host "[rf-service] uploading env file $EnvFile"
    scp -i $resolvedKey $envPath "${sshTarget}:/tmp/rf-service.env"
} else {
    Write-Host "[rf-service] env file not found, remote existing env will be kept: $envPath"
}

$gpuRunArg = ""
if ($Gpus -and $Gpus.Trim().ToLowerInvariant() -notin @("none", "false", "0", "off")) {
    $gpuRunArg = "--gpus $Gpus"
}

$remoteScript = @"
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required on the instance. Install Docker first." >&2
  exit 1
fi

sudo mkdir -p "$RemoteRoot"
sudo tar -xzf "$remoteArchive" -C "$RemoteRoot"
sudo chown -R "${User}:${User}" "$RemoteRoot"

if [ -f /tmp/rf-service.env ]; then
  sudo mv /tmp/rf-service.env "$RemoteRoot/.env"
  sudo chown "${User}:${User}" "$RemoteRoot/.env"
elif [ ! -f "$RemoteRoot/.env" ]; then
  cp "$RemoteRoot/.env.example" "$RemoteRoot/.env"
fi

mkdir -p "$RemoteRoot/apps/ai_api/data/output"

cd "$RemoteRoot"
docker build -f apps/ai_api/Dockerfile -t "${ImageName}:latest" .

docker rm -f "$ContainerName" >/dev/null 2>&1 || true
docker run -d \
  --name "$ContainerName" \
  --restart unless-stopped \
  $gpuRunArg \
  --env-file "$RemoteRoot/.env" \
  -e HOST=0.0.0.0 \
  -e PORT=$Port \
  -p "${Port}:${Port}" \
  -v "${RemoteRoot}/apps/ai_api/data/output:/opt/app/apps/ai_api/data/output" \
  "${ImageName}:latest"

sleep 5
curl -fsS "http://127.0.0.1:${Port}/health" >/dev/null || {
  echo "Health check failed. Recent container logs:"
  docker logs --tail 120 "$ContainerName" || true
  exit 1
}

docker ps --filter "name=$ContainerName"
"@

Write-Host "[rf-service] building and restarting Docker container"
$remoteScript | ssh -i $resolvedKey $sshTarget "bash -s"

Remove-Item -LiteralPath $archive -Force
Write-Host "[rf-service] deployed container: http://${HostName}:$Port"
