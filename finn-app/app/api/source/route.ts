import { readFile } from 'node:fs/promises';
import path from 'node:path';

export async function GET(request: Request) {
  const query = new URL(request.url).searchParams;
  const symbol = query.get('symbol') || '';
  const file = query.get('file') || '';
  const page = query.get('page');
  if (!/^[A-Z0-9][A-Z0-9&-]{0,24}$/.test(symbol) || !/^[a-zA-Z0-9_-]+\.json$/.test(file)) {
    return Response.json({ error: 'Invalid source.' }, { status: 400 });
  }
  if (page !== null && (!/^\d{1,5}$/.test(page) || Number(page) < 1)) return Response.json({ error: 'Invalid page.' }, { status: 400 });
  try {
    const root = path.resolve(process.env.FINN_ROOT || path.join(process.cwd(), '..'));
    const text = await readFile(path.join(root, 'finn-app/public/data/docs', symbol, file), 'utf8');
    const pages = JSON.parse(text);
    return Response.json(page ? pages.filter((item: { page: number }) => item.page === Number(page)) : pages, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return Response.json({ error: 'Source extract unavailable.' }, { status: 404 });
  }
}
