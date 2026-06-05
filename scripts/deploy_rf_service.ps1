param(
    [Parameter(Mandatory = $true)]
    [string]$HostName,

    [string]$User = "ubuntu",
    [string]$KeyPath = "..\..\github-actions-wifi-backend",
    [string]$RemoteRoot = "/opt/rf-service",
    [string]$ServiceName = "rf-service",
    [int]$Port = 9000,
    [string]$EnvFile = ".env"
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
$archive = Join-Path ([System.IO.Path]::GetTempPath()) ("rf-service-deploy-{0}.tar.gz" -f ([guid]::NewGuid().ToString("N")))
$remoteArchive = "/tmp/rf-service-deploy.tar.gz"
$sshTarget = "$User@$HostName"
$keyCandidate = if ([System.IO.Path]::IsPathRooted($KeyPath)) {
    $KeyPath
} else {
    Join-Path $PSScriptRoot $KeyPath
}
$resolvedKey = Resolve-Path $keyCandidate
$envPath = Join-Path $repoRoot $EnvFile

Write-Host "[rf-service] packaging $repoRoot"
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
    Write-Host "[rf-service] env file not found, remote existing .env will be kept: $envPath"
}

$remoteScript = @"
set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip
elif ! python3 -m venv --help >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3-venv python3-pip
fi
sudo mkdir -p "$RemoteRoot"
sudo tar -xzf "$remoteArchive" -C "$RemoteRoot"
sudo chown -R "${User}:${User}" "$RemoteRoot"
cd "$RemoteRoot/apps/ai_api"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if [ -f requirements-rf.txt ]; then pip install -r requirements-rf.txt; fi
if [ -f /tmp/rf-service.env ]; then
  mv /tmp/rf-service.env "$RemoteRoot/apps/ai_api/.env"
fi
sudo tee /etc/systemd/system/$ServiceName.service >/dev/null <<'UNIT'
[Unit]
Description=WiFi Capstone RF/AI API
After=network.target

[Service]
Type=simple
WorkingDirectory=$RemoteRoot/apps/ai_api
EnvironmentFile=-$RemoteRoot/apps/ai_api/.env
Environment=HOST=0.0.0.0
Environment=PORT=$Port
ExecStart=$RemoteRoot/apps/ai_api/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port $Port
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable $ServiceName
sudo systemctl restart $ServiceName
sudo systemctl --no-pager --full status $ServiceName
sleep 2
curl -fsS "http://127.0.0.1:$Port/health" >/dev/null || {
  echo "Health check failed. Recent logs:"
  sudo journalctl -u $ServiceName -n 80 --no-pager
  exit 1
}
"@

Write-Host "[rf-service] installing and restarting service"
$remoteScript | ssh -i $resolvedKey $sshTarget "bash -s"

Remove-Item -LiteralPath $archive -Force
Write-Host "[rf-service] deployed: http://${HostName}:$Port"
