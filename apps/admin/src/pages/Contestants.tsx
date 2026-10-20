import { useState, useMemo, useCallback } from 'react';
import { useContestants } from '@mv/shared';
import type { Contestant } from '@mv/shared';

interface Appearance {
  video_id: string;
  video_name: string;
  timestamp: number;
  match_score: number | null;
}

interface ContestantStats {
  total_appearances: number;
  screen_time_seconds: number;
  videos_appeared_in: number;
}

const QUALITY_WORD: Record<Contestant['quality'], string> = {
  good: '齊全',
  weak: '偏弱',
  missing: '缺',
};
const QUALITY_INK: Record<Contestant['quality'], string> = {
  good: 'text-carbon border-carbon',
  weak: 'text-stamp border-stamp',
  missing: 'text-ledger border-ledger',
};

function stamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/** 名冊 — the cast, read as a filing index. 96 people, one row each. */
export function Contestants() {
  const { data: contestants = [], refetch } = useContestants();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedContestant, setSelectedContestant] = useState<Contestant | null>(null);
  const [appearances, setAppearances] = useState<Appearance[]>([]);
  const [stats, setStats] = useState<ContestantStats | null>(null);
  const [isLoadingAppearances, setIsLoadingAppearances] = useState(false);

  const filtered = useMemo(() => {
    const query = searchQuery.toLowerCase().trim();
    if (!query) return contestants as Contestant[];
    return (contestants as Contestant[]).filter(
      (c) =>
        c.name.toLowerCase().includes(query) ||
        c.nickname.toLowerCase().includes(query) ||
        String(c.id).includes(query),
    );
  }, [contestants, searchQuery]);

  const loadAppearances = useCallback(async (contestant: Contestant) => {
    setIsLoadingAppearances(true);
    try {
      const res = await fetch(`/api/recognition/results?contestant_id=${contestant.id}`);
      if (res.ok) {
        const data = await res.json();
        const results = data.results || data || [];
        setAppearances(
          results.map((r: Record<string, unknown>) => ({
            video_id: String(r.video_id),
            video_name: `Video ${r.video_id}`,
            timestamp: r.timestamp as number,
            match_score: (r.match_score ?? null) as number | null,
          })),
        );
        setStats({
          total_appearances: results.length,
          screen_time_seconds: results.length * 2,
          videos_appeared_in: new Set(results.map((r: Record<string, unknown>) => r.video_id)).size,
        });
      }
    } catch {
      setAppearances([]);
      setStats(null);
    } finally {
      setIsLoadingAppearances(false);
    }
  }, []);

  const open = useCallback(
    (c: Contestant) => {
      setSelectedContestant(c);
      setAppearances([]);
      setStats(null);
      void loadAppearances(c);
    },
    [loadAppearances],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-row px-9 pb-6 pt-7">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-row items-end justify-between gap-6">
          <div className="flex flex-col gap-1.5">
            <div className="font-mono text-[10px] tracking-[0.28em] text-carbon-soft">
              BACK OFFICE · LOCAL ONLY · 127.0.0.1
            </div>
            <div className="flex flex-row items-baseline gap-3.5">
              <h1 className="font-serif text-[44px] font-black leading-none tracking-[0.06em] text-carbon">
                名冊
              </h1>
              <span className="font-mono text-[11px] tracking-[0.26em] text-ledger">
                CAST · 全民造星 IV
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void refetch()}
            className="border border-carbon/45 px-3 py-1.5 font-kai text-[12px] tracking-[0.12em] text-carbon hover:border-stamp hover:text-stamp"
          >
            重新調閱
          </button>
        </div>

        <div className="mt-4 h-px bg-carbon/45" />

        <div className="flex flex-row items-end justify-between py-3">
          <div className="flex flex-1 flex-col gap-1">
            <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">
              SEARCH 編號 / 姓名 / 暱稱
            </span>
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜尋…"
              className="w-full max-w-[420px] border-b border-carbon/45 bg-transparent pb-1.5 font-kai text-[15px] text-carbon-deep placeholder:text-ledger focus:border-stamp focus:outline-none"
            />
          </div>
          <span className="font-mono text-[10px] text-carbon-soft">
            {filtered.length} / {96}
          </span>
        </div>

        <div className="flex flex-row items-center border-b border-carbon/40 pb-2">
          <span className="w-[44px] font-mono text-[8px] tracking-[0.16em] text-ledger">編號</span>
          <span className="w-[52px]" />
          <span className="flex-1 font-mono text-[8px] tracking-[0.16em] text-ledger">姓名</span>
          <span className="w-[70px] text-right font-mono text-[8px] tracking-[0.16em] text-ledger">
            參考相
          </span>
          <span className="w-[70px] text-right font-mono text-[8px] tracking-[0.16em] text-ledger">
            出場
          </span>
          <span className="w-[70px] text-center font-mono text-[8px] tracking-[0.16em] text-ledger">
            品質
          </span>
        </div>

        <div className="flex flex-col overflow-y-auto">
          {filtered.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => open(c)}
              className={`flex flex-row items-center border-b border-carbon/15 py-2 text-left hover:bg-paper-light ${
                selectedContestant?.id === c.id ? 'bg-paper-light' : ''
              }`}
            >
              <span className="w-[44px] font-mono text-[12px] text-carbon-soft">
                {String(c.id).padStart(2, '0')}
              </span>
              <span className="h-[42px] w-[38px] shrink-0 overflow-hidden border border-carbon/35 bg-paper-dark">
                <img
                  src={`/api/contestants/${c.id}/photo`}
                  alt=""
                  className="h-full w-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.visibility = 'hidden';
                  }}
                />
              </span>
              <span className="ml-3 flex flex-1 items-baseline gap-2">
                <span className="font-kai text-[15px] font-bold text-carbon-deep">{c.nickname}</span>
                <span className="font-kai text-[12px] text-carbon-soft">{c.name}</span>
              </span>
              <span className="w-[70px] text-right font-mono text-[11px] text-carbon-soft">
                {c.reference_count}
              </span>
              <span className="w-[70px] text-right font-mono text-[11px] text-carbon-soft">
                {c.detection_count}
              </span>
              <span className="flex w-[70px] justify-center">
                <span
                  className={`-rotate-2 border px-1.5 py-0.5 font-kai text-[10px] tracking-[0.1em] ${QUALITY_INK[c.quality]}`}
                >
                  {QUALITY_WORD[c.quality]}
                </span>
              </span>
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="border-b border-carbon/15 py-12 text-center font-kai text-[13px] text-carbon-soft">
              名冊裡沒有這個人。
            </div>
          )}
        </div>
      </div>

      {/* Filing card */}
      <div className="ml-6 flex w-[360px] shrink-0 flex-col border-l border-carbon/25 pl-6 pt-7">
        {selectedContestant ? (
          <>
            <div className="flex flex-row items-baseline justify-between">
              <span className="font-mono text-[9px] tracking-[0.2em] text-ledger">
                CONTESTANT {String(selectedContestant.id).padStart(2, '0')}
              </span>
              <button
                type="button"
                onClick={() => setSelectedContestant(null)}
                className="font-kai text-[11px] text-carbon-soft hover:text-stamp"
              >
                收起
              </button>
            </div>

            <div className="mt-3 flex flex-row gap-4">
              <div className="h-[132px] w-[112px] shrink-0 overflow-hidden border border-carbon bg-paper-dark">
                <img
                  src={`/api/contestants/${selectedContestant.id}/photo`}
                  alt={selectedContestant.name}
                  className="h-full w-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.visibility = 'hidden';
                  }}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="font-kai text-[24px] font-bold leading-none text-carbon-deep">
                  {selectedContestant.nickname}
                </span>
                <span className="font-kai text-[13px] text-carbon-soft">
                  {selectedContestant.name}
                </span>
                <span className="font-mono text-[9px] tracking-[0.12em] text-ledger">
                  編號 {selectedContestant.id}
                  {selectedContestant.age ? ` · ${selectedContestant.age} 歲` : ''}
                </span>
                <span
                  className={`mt-1 w-fit -rotate-2 border px-1.5 py-0.5 font-kai text-[10px] tracking-[0.1em] ${QUALITY_INK[selectedContestant.quality]}`}
                >
                  參考相 {QUALITY_WORD[selectedContestant.quality]}
                </span>
              </div>
            </div>

            <div className="mt-4 flex flex-row gap-6 border-y border-carbon/25 py-2.5">
              {[
                ['參考相', selectedContestant.reference_count],
                ['偵測', selectedContestant.detection_count],
                ['影片', selectedContestant.videos_seen_in],
              ].map(([label, value]) => (
                <div key={String(label)} className="flex flex-col gap-0.5">
                  <span className="font-mono text-[8px] tracking-[0.16em] text-ledger">{label}</span>
                  <span className="font-mono text-[16px] text-carbon">{value}</span>
                </div>
              ))}
            </div>

            <div className="mt-3 flex flex-row items-baseline justify-between">
              <span className="font-kai text-[13px] font-bold text-carbon">出場紀錄</span>
              <span className="font-mono text-[9px] text-ledger">
                {isLoadingAppearances ? '調閱中…' : `${appearances.length} 筆`}
              </span>
            </div>

            <div className="mt-1 flex flex-col overflow-y-auto">
              {appearances.slice(0, 40).map((a, i) => (
                <div
                  key={`${a.video_id}-${a.timestamp}-${i}`}
                  className="flex flex-row items-center gap-3 border-b border-carbon/15 py-2"
                >
                  <span className="w-[46px] font-mono text-[11px] text-carbon-soft">
                    {stamp(a.timestamp)}
                  </span>
                  <span className="flex-1 truncate font-mono text-[9px] tracking-[0.1em] text-ledger">
                    {a.video_name}
                  </span>
                  <span className="font-mono text-[10px] text-carbon-soft">
                    {a.match_score == null ? '—' : a.match_score.toFixed(2)}
                  </span>
                </div>
              ))}
              {!isLoadingAppearances && appearances.length === 0 && (
                <div className="py-6 font-kai text-[12px] text-carbon-soft">
                  沒有已記錄的出場。
                </div>
              )}
            </div>

            {stats && (
              <div className="mt-auto flex flex-row items-baseline justify-between border-t border-carbon/25 pt-2.5">
                <span className="font-mono text-[9px] tracking-[0.14em] text-ledger">TOTAL</span>
                <span className="font-mono text-[11px] text-carbon">
                  {stats.total_appearances} 次 · {stats.videos_appeared_in} 片
                </span>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-center font-kai text-[13px] leading-relaxed text-carbon-soft">
            從左邊的名冊
            <br />
            挑一個人來看檔案。
          </div>
        )}
      </div>
    </div>
  );
}
