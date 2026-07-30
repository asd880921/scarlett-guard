# Scarlett Guard — 一鍵建置腳本 (onedir + zip)
# 會自動：建立 .venv（若無）→ 安裝 requirements → 產生圖示 → 打包 → 壓成 zip
# 用法（在專案根目錄）：  powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root ".venv"
$py = Join-Path $venv "Scripts\python.exe"
$appOut = Join-Path $root "dist\Scarlett Guard"
# 檔名固定不帶版本：README 的下載連結是
# /releases/latest/download/scarlett-guard.zip，改檔名會讓那個連結失效
$zipOut = Join-Path $root "dist\scarlett-guard.zip"
$version = (Get-Content (Join-Path $root "VERSION") -Raw).Trim()
Write-Host ("建置版本 v{0}" -f $version) -ForegroundColor Cyan

# 關掉可能佔用交付資料夾的執行中 exe（只比對本專案 dist 路徑，不影響其他程式）
function Stop-BuiltExe {
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "*\dist\Scarlett Guard\*" } |
        ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
}

Write-Host "==> 1/5 準備虛擬環境 .venv" -ForegroundColor Cyan
if (-not (Test-Path $py)) {
    python -m venv $venv
}

Write-Host "==> 2/5 安裝相依套件 (requirements.txt)" -ForegroundColor Cyan
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r (Join-Path $root "requirements.txt")

Write-Host "==> 3/5 產生圖示 (與系統匣同一份繪製程式)" -ForegroundColor Cyan
& $py (Join-Path $root "tools\make_icon.py")
if ($LASTEXITCODE -ne 0) { throw "產生圖示失敗 (exit $LASTEXITCODE)" }

Write-Host "==> 4/5 打包 (PyInstaller onedir)" -ForegroundColor Cyan
Stop-BuiltExe
Start-Sleep -Milliseconds 500
& $py -m PyInstaller --clean --noconfirm (Join-Path $root "scarlett_guard.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失敗 (exit $LASTEXITCODE)" }

Write-Host "==> 5/5 壓成 zip" -ForegroundColor Cyan
# 壓縮前再關一次執行中的 exe（避免 _internal 檔案被佔用），
# 並加重試處理防毒即時掃描的短暫鎖檔
Stop-BuiltExe
Start-Sleep -Milliseconds 800
Remove-Item $zipOut -Force -ErrorAction SilentlyContinue
$zipped = $false
for ($i = 1; $i -le 5; $i++) {
    try {
        Compress-Archive -Path $appOut -DestinationPath $zipOut -CompressionLevel Optimal -Force
        $zipped = $true
        break
    } catch {
        Write-Host ("   檔案被佔用，重試 {0}/5 ..." -f $i) -ForegroundColor Yellow
        Start-Sleep -Seconds 1
    }
}
if (-not $zipped) {
    throw "壓縮失敗：檔案持續被佔用。請關閉執行中的 Scarlett Guard.exe（或暫停防毒即時掃描）後重試。"
}

$size = (Get-ChildItem $appOut -Recurse -File | Measure-Object -Property Length -Sum).Sum
$zsize = (Get-Item $zipOut).Length
Write-Host ("完成: v{0}" -f $version) -ForegroundColor Green
Write-Host ("  資料夾 → {0}  ({1:N1} MB)" -f $appOut, ($size / 1MB)) -ForegroundColor Green
Write-Host ("  壓縮包 → {0}  ({1:N1} MB)" -f $zipOut, ($zsize / 1MB)) -ForegroundColor Green
Write-Host "解壓後進資料夾，對 `"Scarlett Guard.exe`" 按右鍵以系統管理員身分執行。"
Write-Host ("要正式發佈就推 tag：git tag v{0} ; git push origin v{0}  (GitHub Actions 會自動建 Release)" -f $version) -ForegroundColor DarkGray
