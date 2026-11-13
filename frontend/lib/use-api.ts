"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "./api";

export type Async<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  setData: (d: T) => void;
};

/** Minimal data hook: no cache library, because the dataset is small and a
 *  stale financial figure is worse than a second request. */
export function useApi<T>(path: string | null, deps: unknown[] = []): Async<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [nonce, setNonce] = useState(0);
  const alive = useRef(true);

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  useEffect(() => {
    if (!path) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.get<T>(path)
      .then((d) => { if (!cancelled && alive.current) { setData(d); setError(null); } })
      .catch((e: unknown) => {
        if (cancelled || !alive.current) return;
        setError(e instanceof ApiError ? e.message : String(e));
      })
      .finally(() => { if (!cancelled && alive.current) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, nonce, ...deps]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, reload, setData };
}

/** Imperative mutation with pending/error state for buttons. */
export function useMutation<TIn, TOut>(fn: (input: TIn) => Promise<TOut>) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const run = useCallback(async (input: TIn): Promise<TOut | undefined> => {
    setPending(true); setError(null);
    try { return await fnRef.current(input); }
    catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      return undefined;
    } finally { setPending(false); }
  }, []);
  return { run, pending, error, setError };
}
