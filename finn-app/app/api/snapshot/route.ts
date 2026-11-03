import { readFile } from 'node:fs/promises';
import path from 'node:path';

export const runtime = 'nodejs';
export async function GET() {
  try {
    const root = path.resolve(process.env.FINN_ROOT || path.join(process.cwd(), '..'));
    return Response.json(JSON.parse(await readFile(path.join(root, 'finn-app/public/data/snapshot.json'), 'utf8')), { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return Response.json({ error: 'The portfolio snapshot is unavailable. Please retry after a source refresh.' }, { status: 503 });
  }
}
