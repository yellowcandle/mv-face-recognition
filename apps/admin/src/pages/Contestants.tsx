import { useState, useMemo, useCallback } from 'react';
import { Search } from 'lucide-react';
import {
  AdminErrorNotice,
  Button,
  Masthead,
  Stamp,
  formatMmSs,
  useContestants,
  useCoverage,
  videoShortName,
} from '@mv/shared';
import { QUALITY_WORD } from '@mv/shared/lib/pipeline';
import { withCoverage } from '@mv/shared/lib/roster';
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

const QUALITY_TONE: Record<Contestant['quality'], 'carbon' | 'muted' | 'stamp'> = {
  good: 'carbon',
  weak: 'muted',
  missing: 'stamp',
};

/** A count the read model may not have: absent reads as an em dash, never as zero. */
function countText(value: number | undefined): string {
  return typeof value === 'number' ? String(value) : '—';
}

/** 名冊 — the cast, read as a filing index. One row per contestant. */
export function Contestants() {
  const {
    data: contestants = [],
    refetch,
    isLoading: rosterLoading,
    error: rosterError,
  } = useContestants();
  const { data: coverage, refetch: refetchCoverage } = useCoverage();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [appearances, setAppearances] = useState<Appearance[]>([]);
  const [stats, setStats] = useState<ContestantStats | null>(null);
  const [isLoadingAppearances, setIsLoadingAppearances] = useState(false);

  const roster = useMemo(
    () => withCoverage(contestants as Contestant[], coverage?.contestants),
    [contestants, coverage],
  );
  const selectedContestant = roster.find((c) => c.id === selectedId) ?? null;

  const filtered = useMemo(() => {
    const query = searchQuery.toLowerCase().trim();
    if (!query) return roster;
    return roster.filter(
      (c) =>
        c.name.toLowerCase().includes(query) ||
        c.nickname.toLowerCase().includes(query) ||
        String(c.id).includes(query),
    );
  }, [roster, searchQuery]);

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
            // The API's video_id is the reel's full name.
            video_name: videoShortName(String(r.video_id)),
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
      setSelectedId(c.id);
      setAppearances([]);
      setStats(null);
      void loadAppearances(c);
    },
    [loadAppearances],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-row">
      <div className="flex min-w-0 flex-1 flex-col px-8 pb-5 pt-8">
        <div className="pb-5">
          <Masthead title="參賽者" hint="名冊、參考照與出場次數" align="center">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                void refetch();
                void refetchCoverage();
              }}
            >
              重新調閱
            </Button>
          </Masthead>
        </div>

        {rosterError ? (
          <AdminErrorNotice error={rosterError} onRetry={() => void refetch()} className="mb-3" />
        ) : null}

        <div className="flex flex-row items-center justify-between gap-4 pb-3">
          <div className="relative w-full max-w-[360px]">
            <Search
              aria-hidden
              className="pointer-events-none absolute left-2.5 top-2 size-4 text-carbon-soft"
            />
            <input
              type="search"
              aria-label="搜尋參賽者"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜尋編號、姓名或暱稱"
              className="field w-full pl-8 placeholder:text-ink-muted"
            />
          </div>
          <span className="shrink-0 font-mono text-[13px] tabular-nums text-carbon-soft">
            {rosterLoading ? (
              <span className="font-kai">調閱中…</span>
            ) : rosterError ? (
              '—'
            ) : (
              `${filtered.length} / ${roster.length}`
            )}
          </span>
        </div>

        <div className="flex h-6 flex-row items-center border-b border-carbon-deep/33 px-2 font-kai text-[12px] text-ink-muted">
          <span className="w-10">編號</span>
          <span className="w-[52px]" />
          <span className="flex-1">姓名</span>
          <span className="w-16 text-right">參考相</span>
          <span className="w-16 text-right">出場</span>
          <span className="w-[72px] text-center">品質</span>
        </div>

        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          {filtered.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => open(c)}
              aria-current={selectedContestant?.id === c.id ? 'true' : undefined}
              className={`flex h-[52px] shrink-0 flex-row items-center border-b border-carbon-deep/13 px-2 text-left transition-colors hover:bg-tint ${
                selectedContestant?.id === c.id ? 'bg-tint' : ''
              }`}
            >
              <span className="w-10 font-mono text-[13px] tabular-nums text-carbon-soft">
                {String(c.id).padStart(2, '0')}
              </span>
              <span className="w-[52px]">
                <span className="block h-11 w-10 overflow-hidden rounded bg-paper-dark">
                  <img
                    src={c.portrait_url ?? `/api/contestants/${c.id}/thumb/face`}
                    alt=""
                    className="h-full w-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.visibility = 'hidden';
                    }}
                  />
                </span>
              </span>
              <span className="flex min-w-0 flex-1 items-end gap-2 font-kai">
                <span
                  className={`truncate text-[15px] text-carbon-deep ${
                    selectedContestant?.id === c.id ? 'font-bold' : ''
                  }`}
                >
                  {c.nickname}
                </span>
                <span className="truncate text-[12px] text-ink-muted">{c.name}</span>
              </span>
              <span className="w-16 text-right font-mono text-[13px] tabular-nums text-carbon-soft">
                {c.reference_count}
              </span>
              <span className="w-16 text-right font-mono text-[13px] tabular-nums text-carbon-soft">
                {countText(c.detection_count)}
              </span>
              <span className="flex w-[72px] justify-center">
                <Stamp tone={QUALITY_TONE[c.quality]}>{QUALITY_WORD[c.quality]}</Stamp>
              </span>
            </button>
          ))}
          {rosterLoading && (
            <div className="py-12 text-center font-kai text-[14px] text-carbon-soft">調閱中…</div>
          )}
          {!rosterLoading && !rosterError && filtered.length === 0 && (
            <div className="border-b border-carbon-deep/13 py-12 text-center font-kai text-[14px] text-carbon-soft">
              名冊裡沒有這個人。
            </div>
          )}
        </div>
      </div>

      {/* Filing card */}
      <aside
        aria-label="參賽者檔案"
        className="flex min-h-0 w-[400px] shrink-0 flex-col border-l border-carbon-deep/13 pb-5 pl-6 pr-8 pt-8"
      >
        {selectedContestant ? (
          <>
            <div className="flex flex-row items-center justify-between pb-3">
              <span className="font-mono text-[12px] tabular-nums text-ink-muted">
                參賽者 {String(selectedContestant.id).padStart(2, '0')}
              </span>
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="rounded-md font-kai text-[13px] text-carbon-soft hover:text-stamp"
              >
                收起
              </button>
            </div>

            <div className="flex flex-row gap-4 pb-4">
              <div className="h-48 w-40 shrink-0 overflow-hidden rounded bg-paper-dark">
                <img
                  src={
                    selectedContestant.portrait_url ??
                    `/api/contestants/${selectedContestant.id}/thumb/face`
                  }
                  alt={selectedContestant.name}
                  className="h-full w-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.visibility = 'hidden';
                  }}
                />
              </div>
              <div className="flex min-w-0 flex-col items-start gap-1.5">
                <h2 className="break-words font-kai text-[32px] font-normal leading-tight text-carbon-deep">
                  {selectedContestant.nickname}
                </h2>
                <span className="font-kai text-[14px] text-carbon-soft">
                  {selectedContestant.name}
                </span>
                <span className="font-mono text-[12px] tabular-nums text-ink-muted">
                  編號 {selectedContestant.id}
                  {selectedContestant.age ? ` · ${selectedContestant.age} 歲` : ''}
                </span>
                <Stamp tone={QUALITY_TONE[selectedContestant.quality]}>
                  參考相 {QUALITY_WORD[selectedContestant.quality]}
                </Stamp>
              </div>
            </div>

            <div className="flex flex-row border-y border-carbon-deep/13 py-3">
              {[
                ['參考相', countText(selectedContestant.reference_count)],
                ['偵測', countText(selectedContestant.detection_count)],
                ['影片', countText(selectedContestant.videos_seen_in)],
              ].map(([label, value]) => (
                <div key={String(label)} className="flex flex-1 flex-col gap-0.5">
                  <span className="font-kai text-[12px] text-carbon-soft">{label}</span>
                  <span className="font-mono text-[28px] leading-tight tabular-nums text-carbon-deep">
                    {value}
                  </span>
                </div>
              ))}
            </div>

            <div className="flex flex-row items-end justify-between pb-2 pt-4">
              <h3 className="font-kai text-[18px] font-normal leading-tight text-carbon-deep">
                出場紀錄
              </h3>
              <span className="font-mono text-[12px] tabular-nums text-ink-muted">
                {isLoadingAppearances ? (
                  <span className="font-kai">調閱中…</span>
                ) : (
                  `${appearances.length} 筆`
                )}
              </span>
            </div>

            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
              {appearances.slice(0, 40).map((a, i) => (
                <div
                  key={`${a.video_id}-${a.timestamp}-${i}`}
                  className="flex h-8 shrink-0 flex-row items-center gap-3 border-b border-carbon-deep/13 text-[13px]"
                >
                  <span className="font-mono tabular-nums text-carbon-soft">
                    {formatMmSs(a.timestamp)}
                  </span>
                  <span className="min-w-0 flex-1 truncate font-kai text-carbon-soft">
                    {a.video_name}
                  </span>
                  <span
                    className="font-mono tabular-nums text-carbon-deep"
                    title={a.match_score == null ? undefined : String(a.match_score)}
                  >
                    {a.match_score == null ? '—' : a.match_score.toFixed(2)}
                  </span>
                </div>
              ))}
              {!isLoadingAppearances && appearances.length === 0 && (
                <div className="py-6 font-kai text-[13px] text-carbon-soft">沒有已記錄的出場。</div>
              )}
            </div>

            {stats && (
              <div className="mt-3 flex flex-row items-baseline justify-between border-t border-carbon-deep/13 pt-2.5">
                <span className="font-kai text-[12px] text-ink-muted">合計</span>
                <span className="font-mono text-[13px] tabular-nums text-carbon">
                  {stats.total_appearances} 次 · {stats.videos_appeared_in} 片
                </span>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-center font-kai text-[14px] leading-relaxed text-carbon-soft">
            從左邊的名冊
            <br />
            挑一個人來看檔案。
          </div>
        )}
      </aside>
    </div>
  );
}
