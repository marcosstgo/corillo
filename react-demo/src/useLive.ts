import { useState, useEffect, useRef } from 'react';

export interface LivePath {
  name: string;
  ready: boolean;
  readers: unknown[];
}

export interface LiveState {
  [key: string]: { viewers: number; ready: boolean };
}

const POLL_MS = 15_000;
const API_URL = 'https://corillo.live/mediamtx-api/v3/paths/list';

export function useLive() {
  const [live, setLive] = useState<LiveState>({});
  const cacheRef = useRef<{ t: number; data: LiveState }>({ t: 0, data: {} });

  async function fetchLive() {
    const now = Date.now();
    if (now - cacheRef.current.t < 8_000) {
      setLive(cacheRef.current.data);
      return;
    }
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 5_000);
      const res = await fetch(API_URL, { signal: ctrl.signal });
      clearTimeout(timer);
      const json = await res.json();
      const state: LiveState = {};
      for (const p of json.items ?? []) {
        const key = (p.name as string).replace('live/', '');
        state[key] = { ready: p.ready, viewers: (p.readers ?? []).length };
      }
      cacheRef.current = { t: now, data: state };
      setLive(state);
    } catch {
      // network error — keep last state
    }
  }

  useEffect(() => {
    fetchLive();
    const id = setInterval(fetchLive, POLL_MS);
    const onVisible = () => { if (!document.hidden) { cacheRef.current.t = 0; fetchLive(); } };
    document.addEventListener('visibilitychange', onVisible);
    return () => { clearInterval(id); document.removeEventListener('visibilitychange', onVisible); };
  }, []);

  return live;
}
