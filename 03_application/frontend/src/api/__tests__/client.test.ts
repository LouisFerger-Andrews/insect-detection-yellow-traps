import { apiClient } from '../client';

describe('apiClient', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('adds auth and json headers for GET', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );

    const out = await apiClient.get<{ ok: boolean }>('/health', 'token-123');

    expect(out.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('/health');
    const headers = new Headers(init?.headers);
    expect(headers.get('Authorization')).toBe('Bearer token-123');
    expect(headers.get('Content-Type')).toBe('application/json');
  });

  it('sends JSON body for POST/PATCH', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 2 }), { status: 200 }));

    await apiClient.post('/items', { name: 'x' });
    await apiClient.patch('/items/1', { name: 'y' });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [, postInit] = fetchMock.mock.calls[0];
    const [, patchInit] = fetchMock.mock.calls[1];
    expect(postInit?.method).toBe('POST');
    expect(postInit?.body).toBe(JSON.stringify({ name: 'x' }));
    expect(patchInit?.method).toBe('PATCH');
    expect(patchInit?.body).toBe(JSON.stringify({ name: 'y' }));
  });

  it('does not force json content type for FormData', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );
    const body = new FormData();
    body.append('f', new Blob(['a']), 'a.txt');

    await apiClient.postForm('/upload', body, 'abc');

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get('Authorization')).toBe('Bearer abc');
    expect(headers.get('Content-Type')).toBeNull();
  });

  it('throws api message for non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('bad request', { status: 400 }));
    await expect(apiClient.get('/bad')).rejects.toThrow('bad request');
  });

  it('throws reachability message on fetch error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network down'));
    await expect(apiClient.get('/x')).rejects.toThrow('Cannot reach API');
  });
});
