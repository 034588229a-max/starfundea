shaders 4.0.4（MIT，https://github.com/shader-effects-inc/shaders）
由 npm 套件 shaders 的 js 入口用 esbuild 打包成單一檔案：
  import { createShader } from "shaders/js"; window.__createShader = createShader;
官網首屏背景特效用；沒有 WebGPU 或使用者設定「減少動態」時不會載入。
