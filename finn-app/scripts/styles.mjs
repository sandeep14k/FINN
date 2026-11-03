// Compile Tailwind in the main process so Next's loader worker is unnecessary.
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { watch } from 'node:fs';
import { spawn } from 'node:child_process';
import path from 'node:path';
const require = createRequire(import.meta.url);
const loader = require('@tailwindcss/turbopack');
const root = process.cwd();
const source = path.join(root, 'app/globals.css');
const output = path.join(root, 'app/generated.css');
async function compile() {
  const input = await readFile(source, 'utf8');
  const css = await new Promise((resolve, reject) => loader.call({
    resourcePath: source, resource: source,
    getOptions: () => ({ base: path.join(root, 'app') }),
    async: () => (error, result) => error ? reject(error) : resolve(result),
    addDependency() {}, addContextDependency() {},
  }, input));
  await writeFile(output, css);
}
await compile();
if (process.argv.includes('--dev')) {
  let pending;
  const watchers = ['app', 'components', 'lib'].map(directory => watch(path.join(root, directory), { recursive: true }, (_event, filename) => {
    if (filename?.endsWith('generated.css')) return;
    clearTimeout(pending);
    pending = setTimeout(() => compile().catch(console.error), 150);
  }));
  const child = spawn(process.execPath, [require.resolve('next/dist/bin/next'), 'dev', ...process.argv.slice(3)], { stdio: 'inherit' });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
  child.on('exit', code => { watchers.forEach(watcher => watcher.close()); process.exit(code || 0); });
}
