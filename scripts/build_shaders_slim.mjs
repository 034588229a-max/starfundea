// 產生精簡版 shaders 套件：只保留指定的效果，其他 200 個效果不打包。
// 用法（在已 npm i shaders@4.0.4 esbuild 的資料夾）：node build_shaders_slim.mjs LinearGradient CursorTrail
// 輸出：slim.js（IIFE，提供 window.__createShader）
import * as esbuild from 'esbuild'; import fs from 'fs';
const KEEP = new Set(process.argv.slice(2));
if (!KEEP.size) { console.error('請列出要保留的效果名稱'); process.exit(1); }
fs.writeFileSync('entry.js', 'import { createShader } from "shaders/js"; window.__createShader = createShader;\n');
const plug = { name: 'slim', setup(b) { b.onLoad({ filter: /shaders[\\/]dist[\\/]core[\\/](index\.js|registry\.js|shaderRegistry-[\w-]+\.js)$/ }, a => {
  let s = fs.readFileSync(a.path, 'utf8'); const drop = new Set();
  s = s.replace(/^import "\.\/([A-Z][A-Za-z0-9]*)-[\w-]+\.js";\n/gm, (m, name) => KEEP.has(name) ? m : '');
  s = s.replace(/^import \{ [a-z] as (componentDefinition(?:\$\d+)?) \} from "\.\/([A-Z][A-Za-z0-9]*)-[\w-]+\.js";\n/gm, (m, v, name) => { if (KEEP.has(name)) return m; drop.add(v); return ''; });
  s = s.replace(/^\s*[A-Za-z0-9_]+: (componentDefinition(?:\$\d+)?),?\n/gm, (m, v) => drop.has(v) ? '' : m);
  return { contents: s, loader: 'js', resolveDir: a.path.replace(/[\\/][^\\/]+$/, '') };
}); } };
await esbuild.build({ entryPoints: ['entry.js'], bundle: true, format: 'iife', minify: true, outfile: 'slim.js', plugins: [plug], logLevel: 'warning', legalComments: 'none' });
console.log('slim.js', fs.statSync('slim.js').size, 'bytes');
