// Build a static export for Qoder Sites. Server API routes are parked for the
// build because static hosting cannot run them; the client uses published JSON.
import { existsSync, renameSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const root = process.cwd();
const api = path.join(root, 'app', 'api');
const parked = path.join(root, '.api-static-build');
const hadApi = existsSync(api);

try {
  if (hadApi) renameSync(api, parked);
  rmSync(path.join(root, '.next'), { recursive: true, force: true });
  const result = spawnSync('npm', ['run', 'build'], {
    stdio: 'inherit',
    env: { ...process.env, STATIC_EXPORT: '1', NEXT_PUBLIC_STATIC_DATA: '1' },
  });
  if (result.status !== 0) process.exitCode = result.status ?? 1;
} finally {
  if (hadApi && existsSync(parked)) renameSync(parked, api);
}
