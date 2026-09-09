/** Parse all shipped TS/TSX with the installed compiler. Not a typecheck or build. */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'frontend/package.json'));
let ts;
try { ts = require('typescript'); }
catch {
  const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const globalRoot = execFileSync(npm, ['root', '-g'], { encoding: 'utf8' }).trim();
  ts = require(path.join(globalRoot, 'typescript'));
}
function* walk(dir) {
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    if (['node_modules', 'dist', 'public', 'test-results', 'playwright-report', 'test-results-ifc', 'playwright-report-ifc'].includes(item.name)) continue;
    const filename = path.join(dir, item.name);
    if (item.isDirectory()) yield* walk(filename);
    else if (/\.tsx?$/.test(item.name)) yield filename;
  }
}
let count = 0;
let errors = 0;
for (const file of walk(path.join(root, 'frontend'))) {
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
  count += 1;
  for (const diagnostic of source.parseDiagnostics) {
    const location = source.getLineAndCharacterOfPosition(diagnostic.start ?? 0);
    console.error(`${path.relative(root, file)}:${location.line + 1}:${location.character + 1}: ${ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n')}`);
    errors += 1;
  }
}
console.log(`${errors ? 'FAIL' : 'PASS'}: ${count} TS/TSX files parsed with TypeScript ${ts.version}. Syntax only; dependencies and types were NOT checked.`);
process.exitCode = errors ? 1 : 0;
