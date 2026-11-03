import { readFile, writeFile, rename, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { categories, defaults } from '../../../lib/format';

const directory = path.resolve(process.env.FINN_ROOT || path.join(process.cwd(), '..'), 'data');
export async function GET() {
  try { return Response.json(JSON.parse(await readFile(path.join(directory, 'alert_rules.json'), 'utf8')), { headers: { 'Cache-Control': 'no-store' } }); }
  catch { return Response.json(defaults); }
}
export async function POST(request: Request) {
  let input;
  try { input = await request.json(); } catch { return Response.json({ error: 'Invalid preferences.' }, { status: 400 }); }
  if (!input || !Number.isFinite(input.price) || input.price < 1 || input.price > 10 || !Number.isFinite(input.volume) || input.volume < 1 || input.volume > 5 || !Array.isArray(input.categories) || input.categories.some((value: unknown) => typeof value !== 'string' || !categories.includes(value))) return Response.json({ error: 'Invalid alert thresholds or categories.' }, { status: 400 });
  const rules = { price: input.price, volume: input.volume, categories: [...new Set(input.categories)] };
  await mkdir(directory, { recursive: true });
  const temporary = path.join(directory, `.rules-${randomUUID()}.tmp`);
  await writeFile(temporary, JSON.stringify(rules, null, 2));
  await rename(temporary, path.join(directory, 'alert_rules.json'));
  return Response.json(rules);
}
