/** Compile only the two production browser-transport modules for contract execution.
 * This is NOT a substitute for Vite, React rendering, or project-wide type checking.
 */
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
const require = createRequire(import.meta.url);
let ts;
try { ts = require('../frontend/node_modules/typescript'); }
catch { ts = require(resolve(execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim(), 'typescript')); }
const output = resolve(process.argv[2] ?? resolve(root, 'artifacts/browser-transport'));
mkdirSync(output, { recursive: true });
for (const name of ['client', 'sse']) {
  const source = resolve(root, 'frontend/src/api', `${name}.ts`);
  const result = ts.transpileModule(readFileSync(source, 'utf8'), {
    fileName: source, reportDiagnostics: true,
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, strict: true },
  });
  const errors = result.diagnostics?.filter(diagnostic => diagnostic.category === ts.DiagnosticCategory.Error) ?? [];
  if (errors.length) throw new Error(errors.map(error => ts.flattenDiagnosticMessageText(error.messageText, '\n')).join('\n'));
  writeFileSync(resolve(output, `${name}.js`), result.outputText);
}
console.log(JSON.stringify({ scope: 'production browser transport only', typescript: ts.version, output }));
