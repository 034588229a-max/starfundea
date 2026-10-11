# 一鍵部署：檢查 → 推上 Apps Script → 建立（或更新同一個）網頁應用程式部署 → 把正式網址寫回程式。
# 用法：雙擊專案根目錄的 deploy.bat；或  powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1 [-SkipTests] [-DryRun]
param([switch]$SkipTests, [switch]$DryRun, [string]$Description = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'   # 避免 cp950 視窗印不出測試名稱裡的符號

function Say($m) { Write-Host "▶ $m" -ForegroundColor Cyan }
function Run($cmd, $argList) {
  if ($DryRun) { Write-Host "  [DryRun] $cmd $($argList -join ' ')" -ForegroundColor DarkGray; return '' }
  # npm 等工具的警告會走 stderr，PowerShell 5.1 會把它當成錯誤，所以這裡暫時放寬，只看結束代碼
  $prev = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $out = & $cmd @argList 2>&1 | Out-String
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($code -ne 0) { throw "$cmd $($argList -join ' ') 失敗：`n$out" }
  return $out
}

# 1. 必要工具
Say '檢查 Node.js 與 clasp'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Say '沒有 Node.js，用 winget 安裝（會跳出系統確認視窗）'
    Run 'winget' @('install', '-e', '--id', 'OpenJS.NodeJS.LTS', '--accept-package-agreements', '--accept-source-agreements')
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
  } else { throw '請先安裝 Node.js（https://nodejs.org），再重新執行。' }
}
if (-not (Get-Command clasp -ErrorAction SilentlyContinue)) {
  Say '安裝 clasp'
  Run 'npm' @('install', '-g', '@google/clasp')
}
if (-not $DryRun) { Write-Host ('  clasp ' + (& clasp --version 2>$null)) }

# 2. 登入 Google（第一次會開瀏覽器，請用要擁有這個服務的 Google 帳號）
$rc = Join-Path $env:USERPROFILE '.clasprc.json'
if (-not (Test-Path $rc)) {
  Say '第一次使用：登入 Google（請先到 https://script.google.com/home/usersettings 開啟「Google Apps Script API」）'
  if ($DryRun) { Write-Host '  [DryRun] clasp login' } else { & clasp login; if ($LASTEXITCODE -ne 0) { throw 'clasp login 失敗' } }
}

# 3. 專案：沒有 .clasp.json 就建立新的 Apps Script 專案
if (-not (Test-Path '.clasp.json')) {
  $title = if ($DryRun) { '' } else { Read-Host '這是第一次部署。請幫新專案取名（例如：星樂創意 StarFunDea）' }
  if (-not $title) { $title = '星樂創意 StarFunDea' }
  Say "建立 Apps Script 專案：$title"
  Run 'clasp' @('create', '--type', 'webapp', '--title', $title, '--rootDir', 'src')
  if (-not $DryRun -and -not (Test-Path 'src\appsscript.json')) { Copy-Item 'scripts\appsscript.template.json' 'src\appsscript.json' }
}
# 一定要有 webapp 設定與台北時區，否則部署出來不是網站（clasp create 產生的檔案沒有）
if (-not $DryRun) { $m = if (Test-Path 'src\appsscript.json') { Get-Content 'src\appsscript.json' -Raw } else { '' }; if ($m -notmatch '\"webapp\"') { Say '補上網頁應用程式與台北時區設定（appsscript.json）'; Copy-Item 'scripts\appsscript.template.json' 'src\appsscript.json' -Force } }

# 4. 驗證（Apps Script 陷阱檢查＋測試）
Say '檢查程式'
Run 'python' @('scripts\check_gas.py') | Write-Host
if (-not $SkipTests) {
  foreach ($t in @('tests\integration_e2e.py', 'tests\layout_e2e.py', 'tests\saas_e2e.py', 'tests\installer_test.py')) {
    Say "測試 $t"
    $o = Run 'python' @($t)
    if (-not $DryRun) { ($o -split "`n" | Select-Object -Last 3) -join "`n" | Write-Host }
  }
}

# 5. 推上去
Say '推上 Apps Script'
Run 'clasp' @('push', '--force') | Write-Host

# 6. 部署（同一個部署作業，網址不變）
$idFile = '.deploy-id'
$desc = if ($Description) { $Description } else { '部署 ' + (Get-Date -Format 'yyyy-MM-dd HH:mm') }
$deployId = if (Test-Path $idFile) { (Get-Content $idFile -Raw).Trim() } else { '' }
if ($deployId) {
  Say "更新既有部署（網址不變）：$deployId"
  Run 'clasp' @('deploy', '--deploymentId', $deployId, '--description', $desc) | Write-Host
} else {
  Say '建立第一個部署'
  $out = Run 'clasp' @('deploy', '--description', $desc)
  $m = [regex]::Match($out, 'AKfy[\w-]+')
  if (-not $m.Success -and -not $DryRun) { throw "找不到部署 ID，clasp 回應：`n$out" }
  $deployId = $m.Value
  if (-not $DryRun) { Set-Content $idFile $deployId -Encoding ascii }
}
$url = "https://script.google.com/macros/s/$deployId/exec"

# 7. 把正式網址寫回程式（WEB_APP_URL），有變才重推
$codePath = 'src\Code.gs'
$code = [IO.File]::ReadAllText((Resolve-Path $codePath), [Text.Encoding]::UTF8)
if ($deployId -and $code -notmatch [regex]::Escape($url)) {
  Say '把正式網址寫進 Code.gs 並重新部署'
  $code = [regex]::Replace($code, "const WEB_APP_URL = '[^']*';", "const WEB_APP_URL = '$url';")
  if (-not $DryRun) { [IO.File]::WriteAllText((Resolve-Path $codePath), $code, (New-Object Text.UTF8Encoding($false))) }
  Run 'clasp' @('push', '--force') | Write-Host
  Run 'clasp' @('deploy', '--deploymentId', $deployId, '--description', $desc) | Write-Host
}

# 8. 啟用工具的服務網址
$cfg = 'installer\config.json'
if ($deployId -and (Test-Path $cfg) -and -not $DryRun) {
  $j = Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($j.serviceUrl -ne $url) { $j.serviceUrl = $url; ($j | ConvertTo-Json) | Set-Content $cfg -Encoding UTF8 }
}

Write-Host ''
Write-Host '✅ 部署完成' -ForegroundColor Green
Write-Host "   服務網址：$url"
Write-Host "   管理後台：$url`?p=admin"
Write-Host ''
Write-Host '第一次部署還要做一件事（只做一次）：'
Write-Host '  1. 用 clasp open 打開 Apps Script 編輯器，選函式 setupCenter 按「執行」並授權（建立授權中心）'
Write-Host '  2. 若要把原本的弘林單店轉入：選 adoptLegacyShop 按「執行」'
Write-Host '  3. 到上面「管理後台」網址，用管理員 Email 收驗證碼登入'
Write-Host '  4. 要給店家的啟用工具：installer\build_exe.bat（已自動填好服務網址）'
