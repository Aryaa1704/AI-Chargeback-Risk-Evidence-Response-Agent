import { useEffect, useState } from 'react';
import { ApiError } from '../api/client';

export function useApiData<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [data, setData] = useState<T>(); const [error, setError] = useState<string>(); const [reload, setReload] = useState(0);
  useEffect(() => { const controller = new AbortController(); setError(undefined); load(controller.signal).then(setData).catch((caught: unknown) => { if (!(caught instanceof DOMException && caught.name === 'AbortError')) setError(caught instanceof ApiError ? caught.message : 'An unexpected API error occurred.'); }); return () => controller.abort(); }, [load, reload]);
  return { data, error, retry: () => setReload((value) => value + 1) };
}
