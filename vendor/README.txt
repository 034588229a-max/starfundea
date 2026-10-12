shaders 4.0.4（MIT，https://github.com/shader-effects-inc/shaders）
官網首屏背景特效用（LinearGradient＋CursorTrail 游標拖尾）。

2026-10-11 起改成「精簡版」：只打包官網用到的 2 個效果（原本 200 個全包），
2.6 MB → 1.3 MB（gzip 約 720 KB → 310 KB）。重新產生：
  cd 任一暫存資料夾 && npm i shaders@4.0.4 esbuild
  node <專案>/scripts/build_shaders_slim.mjs LinearGradient CursorTrail
  把產生的 slim.js 複製成 site/vendor/shaders.bundle.js
完整版備份：test-skills/backup/shaders.bundle.full-4.0.4.js

載入規則（site/index.template.html）：只給有滑鼠、寬度 861px 以上的電腦；
封面動畫播完（2.6 秒後）且瀏覽器有空才載入；沒有 WebGPU、使用者選「減少動態」或出錯就不顯示。
已關閉套件內建的使用統計回傳（disableTelemetry: true，原本約 5% 訪客會把網域、瀏覽器、裝置類型送到 shaders.com）。
