param(
  [Parameter(Mandatory = $true)]
  [string]$ImagePath
)

if (-not (Test-Path $ImagePath)) {
  throw "Image not found: $ImagePath"
}

Write-Host "GET /health"
Invoke-RestMethod -Uri "http://127.0.0.1:9000/health" -Method Get | ConvertTo-Json

Write-Host "POST /wall/unet"
$formUnet = @{
  file_id = "smoke-test-unet"
  file = Get-Item $ImagePath
}
Invoke-RestMethod -Uri "http://127.0.0.1:9000/wall/unet" -Method Post -Form $formUnet | ConvertTo-Json

Write-Host "POST /objects/yolo"
$formYolo = @{
  file_id = "smoke-test-yolo"
  file = Get-Item $ImagePath
}
Invoke-RestMethod -Uri "http://127.0.0.1:9000/objects/yolo" -Method Post -Form $formYolo | ConvertTo-Json
