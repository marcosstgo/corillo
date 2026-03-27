import { useState, useEffect } from 'react';

export interface Vod {
  id: string;
  channel: string;
  filename: string;
  duration: number;
  date: string;
  thumb: string;
  preview: string;
}

const PB_URL = 'https://pb.corillo.live';

export function useVods(limit = 6) {
  const [vods, setVods] = useState<Vod[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(
      `${PB_URL}/api/collections/vods/records?sort=-date&perPage=${limit}&fields=id,channel,filename,thumb,preview,duration,date`,
      { signal: ctrl.signal }
    )
      .then(r => r.json())
      .then(j => setVods(j.items ?? []))
      .catch(() => {});
    return () => ctrl.abort();
  }, [limit]);

  return vods;
}
