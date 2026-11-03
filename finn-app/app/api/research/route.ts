import { execFile } from 'node:child_process';
import { readFile, access, readdir } from 'node:fs/promises';
import path from 'node:path';

export const runtime = 'nodejs';
const root = path.resolve(process.env.FINN_ROOT || path.join(process.cwd(), '..'));
type Job = { status: 'running' | 'failed'; started: number; error?: string };
const state = globalThis as typeof globalThis & { finnJobs?: Map<string, Job> };
const jobs = state.finnJobs ??= new Map();
async function recoveredJob(symbol: string): Promise<Job | null> {
  try {
    const saved = JSON.parse(await readFile(path.join(root, 'data/.jobs', `${symbol}.json`), 'utf8'));
    if (saved.status === 'failed') return { status: 'failed', started: saved.started, error: 'Previous research failed. Please retry.' };
    if (saved.status !== 'running' || !Number.isInteger(saved.pid) || saved.pid < 1) return null;
    if (Date.now() - saved.started > 1_800_000) return { status: 'failed', started: saved.started, error: 'Previous research was interrupted or exceeded its time limit. Please retry.' };
    try { process.kill(saved.pid, 0); } catch { return { status: 'failed', started: saved.started, error: 'Previous research was interrupted. Please retry.' }; }
    return { status: 'running', started: saved.started };
  } catch { return null; }
}
async function recoveredActiveJob() {
  try {
    for (const file of await readdir(path.join(root, 'data/.jobs'))) {
      if (!/^[A-Z0-9][A-Z0-9&-]{0,24}\.json$/.test(file)) continue;
      if ((await recoveredJob(file.slice(0, -5)))?.status === 'running') return true;
    }
  } catch { /* No prior jobs exist. */ }
  return false;
}
function symbolOf(request: Request) {
  const symbol = new URL(request.url).searchParams.get('symbol')?.toUpperCase().replace(/\.NS$/, '') || '';
  return /^[A-Z0-9][A-Z0-9&-]{0,24}$/.test(symbol) ? symbol : null;
}
async function cached(symbol: string) {
  try { return JSON.parse(await readFile(path.join(root, 'finn-app/public/data/pull', `${symbol}.json`), 'utf8')); }
  catch { return null; }
}
export async function GET(request: Request) {
  const symbol = symbolOf(request);
  if (!symbol) return Response.json({ error: 'Enter a valid NSE symbol.' }, { status: 400 });
  const data = await cached(symbol);
  if (data) return Response.json({ status: 'ready', data }, { headers: { 'Cache-Control': 'no-store' } });
  const job = jobs.get(symbol) || await recoveredJob(symbol);
  if (job?.status === 'running') {
    let stage = 'Starting primary-source research';
    try {
      const progress = JSON.parse(await readFile(path.join(root, 'data/.jobs', `${symbol}.json`), 'utf8'));
      if (Date.parse(progress.updated_at) >= job.started && typeof progress.stage === 'string') stage = progress.stage;
    } catch { /* The process may not have published its first stage yet. */ }
    return Response.json({ ...job, stage }, { headers: { 'Cache-Control': 'no-store' } });
  }
  return Response.json(job || { status: 'missing' }, { headers: { 'Cache-Control': 'no-store' } });
}
export async function POST(request: Request) {
  const symbol = symbolOf(request);
  if (!symbol) return Response.json({ error: 'Enter a valid NSE symbol.' }, { status: 400 });
  const data = await cached(symbol);
  if (data) return Response.json({ status: 'ready', data });
  if (process.env.FINN_ENABLE_RESEARCH !== '1') {
    return Response.json({ error: 'Live research is unavailable on this demo. Saved company research remains available.' }, { status: 503 });
  }
  // Serialize expensive jobs and retain a short cooldown after failures.
  const recovered = await recoveredJob(symbol);
  const recoveredActive = await recoveredActiveJob();
  const previous = jobs.get(symbol) || recovered;
  if (previous?.status === 'running') return Response.json(previous, { status: 202 });
  if (previous && Date.now() - previous.started < 60_000) return Response.json(previous, { status: 429 });
  if (recoveredActive || [...jobs.values()].some(j => j.status === 'running')) return Response.json({ error: 'Another company is being researched. Please try again shortly.' }, { status: 429 });
  const python = process.env.FINN_PYTHON || path.join(root, 'venv/bin/python');
  const started = Date.now();
  if (jobs.size > 100) jobs.clear();
  jobs.set(symbol, { status: 'running', started });
  try { await access(python); } catch {
    jobs.delete(symbol);
    return Response.json({ error: 'The research Python environment is not installed on this host.' }, { status: 503 });
  }
  execFile(/* turbopackIgnore: true */ python, ['research_job.py', symbol], { cwd: root, timeout: 1_830_000, maxBuffer: 2 * 1024 * 1024 }, (error) => {
    if (error) jobs.set(symbol, { status: 'failed', started, error: 'Primary-source research failed or timed out. Check server logs and source availability.' });
    else jobs.delete(symbol);
    if (error) console.error(`Research failed for ${symbol}:`, error.message);
  });
  return Response.json({ status: 'running', started }, { status: 202 });
}
