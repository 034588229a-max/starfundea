@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo   星樂創意 StarFunDea  一鍵部署到 Google Apps Script
echo ================================================
echo.
if not exist ".deploy-id" (
  >".deploy-id" echo AKfycbwPhHfsMZ-cXx3r_YLv1hQsk6lf_isDBN8GXybqTb46qKceAC8CVXhhpi6WWPTAYGE
)
if exist ".clasp.json" goto run
echo 第一次在這台電腦部署，需要「指令碼 ID」（只要貼一次）：
echo   1. 打開 https://script.google.com ，點進 StarFunDea 的專案
echo   2. 左邊齒輪「專案設定」，複製「ID」那一串
echo.
set /p SID=請貼上指令碼 ID 後按 Enter： 
if "%SID%"=="" (
  echo 沒有輸入指令碼 ID，已停止。為了不建出第二個專案，一定要用原本的那一個。
  pause
  exit /b 1
)
>".clasp.json" echo {"scriptId":"%SID%","rootDir":"src"}
:run
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\deploy.ps1" -SkipTests
if errorlevel 1 echo.
if errorlevel 1 echo 部署沒有完成，請看上面的訊息。
pause
