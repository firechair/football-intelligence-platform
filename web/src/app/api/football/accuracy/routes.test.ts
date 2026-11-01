import { NextRequest } from 'next/server';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { GET as getResults } from './results/route';
import { GET as getSummary } from './summary/route';

afterEach(() => vi.unstubAllGlobals());

// Next.js kept the empty answer of a first visit and served it after the data arrived.
describe.each([
  ['summary', getSummary],
  ['results', getResults],
])('accuracy %s route', (name, get) => {
  it('never stores the backend answer', async () => {
    const backend = vi.fn(async () => Response.json({ success: true }));
    vi.stubGlobal('fetch', backend);
    await get(new NextRequest(`http://localhost/api/football/accuracy/${name}`));
    expect(backend.mock.calls[0]).toEqual([expect.any(String), expect.objectContaining({ cache: 'no-store' })]);
  });
});
