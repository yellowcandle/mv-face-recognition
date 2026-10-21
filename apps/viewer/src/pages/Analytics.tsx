import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Masthead, useVideos } from '@mv/shared';
import { BAND_STAMP, bandFor, formatMmSs } from '@mv/shared';
import type { Band, VideoMetadata } from '@mv/shared';

interface ContestantStat {
  id: string;
  nickname: string;
  name: string;
  appearances: number;
  avgMatchScore: number;
  maxMatchScore: number;
  firstSeen: number;
  lastSeen: number;
}

function BandStamp({ band, title }: { band: Band; title: string }) {
  return (
    <span
      title={title}
      className={`inline-block -rotate-2 border px-1.5 py-0.5 font-kai text-[10px] tracking-[0.12em] ${BAND_STAMP[band].ink}`}
    >
      {BAND_STAMP[band].word}
    </span>
  );
}

/** 紀錄 — the ledger of who was filed, per reel. Same data, read as a filing record. */
export function Analytics() {
  const { data: videos = [] } = useVideos();
  const [selectedVideoId, setSelectedVideoId] = useState<string>('');
  const [sortBy, setSortBy] = useState<'appearances' | 'avgMatchScore'>('appearances');

  const videoId = selectedVideoId || videos[0]?.id || '';
  const numericId = videoId.match(/^(\d+)/)?.[1] || videoId;

  const { data: metadata, isLoading } = useQuery<VideoMetadata>({
    queryKey: ['video-metadata', numericId],
    queryFn: async () => {
      const res = await fetch(`/api/videos/metadata/dense/${numericId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: !!numericId,
    staleTime: 5 * 60 * 1000,
  });

  const stats = useMemo<ContestantStat[]>(() => {
    if (!metadata?.contestant_timeline) return [];
    return Object.entries(metadata.contestant_timeline)
      .map(([key, info]) => ({
        id: key,
        nickname: info.contestant_info?.nickname ?? key,
        name: info.contestant_info?.name ?? key,
        appearances: info.total_appearances,
        avgMatchScore: info.average_match_score,
        maxMatchScore: Math.max(0, ...(info.appearances ?? []).map((a) => a.match_score)),
        firstSeen: info.first_appearance,
        lastSeen: info.last_appearance,
      }))
      .sort((a, b) =>
        sortBy === 'appearances'
          ? b.appearances - a.appearances
          : b.avgMatchScore - a.avgMatchScore,
      );
  }, [metadata, sortBy]);

  const summary = metadata?.processing_summary;

  return (
    <div className="flex min-h-0 flex-1 flex-col px-10 pb-8 pt-7">
      <Masthead eyebrow="MV FACE RECOGNITION · 全民造星 IV" title="紀錄" latin="RECOGNITION LEDGER">
        <div className="flex flex-col items-end gap-1">
        <span className="font-mono text-[9px] tracking-[0.2em] text-ledger">REEL</span>
        <select
        className="min-w-[260px] border border-carbon/45 bg-paper-light px-2.5 py-1.5 font-kai text-[13px] text-carbon-deep focus:border-stamp focus:outline-none"
        value={selectedVideoId}
        onChange={(e) => setSelectedVideoId(e.target.value)}
        >
        {videos.map((v) => (
        <option key={v.id} value={v.id}>
        {v.name}
        </option>
        ))}
        </select>
        </div>
      </Masthead>

      <div className="mt-4 h-px bg-carbon/45" />

      {summary && (
        <div className="flex flex-row items-end gap-10 py-3.5">
          {[
            { label: 'FRAMES', value: summary.frames_processed.toLocaleString() },
            { label: 'FACES DETECTED', value: summary.total_faces_detected.toLocaleString() },
            { label: 'RECOGNISED', value: summary.total_recognitions.toLocaleString() },
            { label: 'CONTESTANTS', value: String(summary.unique_contestants) },
          ].map((s) => (
            <div key={s.label} className="flex flex-col gap-1">
              <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">{s.label}</span>
              <span className="font-mono text-[22px] leading-none text-carbon">{s.value}</span>
            </div>
          ))}
        </div>
      )}
      <div className="h-px bg-carbon/20" />

      <div className="flex flex-row items-center gap-4 py-2.5">
        <span className="font-mono text-[9px] tracking-[0.2em] text-ledger">SORT</span>
        {(
          [
            ['appearances', '出場次數'],
            ['avgMatchScore', '平均分'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setSortBy(key)}
            className={`border px-2 py-0.5 font-kai text-[11px] tracking-[0.1em] ${
              sortBy === key
                ? '-rotate-1 border-stamp text-stamp'
                : 'border-carbon/25 text-carbon-soft hover:border-carbon/50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="py-16 text-center font-kai text-[13px] text-carbon-soft">正在調閱紀錄…</div>
      ) : stats.length === 0 ? (
        <div className="mt-1 border border-dashed border-carbon/35 px-4 py-14 text-center font-kai text-[13px] text-carbon-soft">
          這卷影片沒有可核對的紀錄。
        </div>
      ) : (
        <div className="overflow-hidden border border-carbon/35">
          <div className="flex flex-row items-center border-b border-carbon/40 bg-paper-dark px-4 py-2.5">
            <span className="w-[52px] font-mono text-[8px] tracking-[0.18em] text-ledger">NO.</span>
            <span className="flex-1 font-mono text-[8px] tracking-[0.18em] text-ledger">CONTESTANT</span>
            <span className="w-[110px] text-right font-mono text-[8px] tracking-[0.18em] text-ledger">
              APPEARANCES
            </span>
            <span className="w-[120px] text-right font-mono text-[8px] tracking-[0.18em] text-ledger">
              AVG
            </span>
            <span className="w-[120px] text-right font-mono text-[8px] tracking-[0.18em] text-ledger">
              MAX
            </span>
            <span className="w-[150px] text-right font-mono text-[8px] tracking-[0.18em] text-ledger">
              SCREEN TIME
            </span>
          </div>

          {stats.map((s) => {
            const avgBand = bandFor(s.avgMatchScore);
            const maxBand = bandFor(s.maxMatchScore);
            return (
              <div
                key={s.id}
                className="flex flex-row items-center border-b border-carbon/15 px-4 py-2.5 last:border-b-0 hover:bg-paper-light"
              >
                <span className="w-[52px] font-mono text-[11px] text-carbon-soft">
                  {String(s.id).padStart(2, '0')}
                </span>
                <span className="flex flex-1 items-baseline gap-2">
                  <span className="font-kai text-[15px] font-bold text-carbon-deep">{s.nickname}</span>
                  <span className="font-mono text-[9px] text-ledger">#{s.id}</span>
                </span>
                <span className="w-[110px] text-right font-mono text-[12px] text-carbon">
                  {s.appearances}
                </span>
                <span className="flex w-[120px] justify-end">
                  <BandStamp
                    band={avgBand}
                    title={`${s.avgMatchScore.toFixed(2)} cosine average`}
                  />
                </span>
                <span className="flex w-[120px] justify-end">
                  <BandStamp band={maxBand} title={`${s.maxMatchScore.toFixed(2)} cosine max`} />
                </span>
                <span className="w-[150px] text-right font-mono text-[10px] text-carbon-soft">
                  {formatMmSs(s.firstSeen)} — {formatMmSs(s.lastSeen)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <div className="flex-1" />
      <div className="flex flex-row items-center justify-between border-t border-carbon/25 pt-3">
        <span className="font-mono text-[9px] tracking-[0.18em] text-ledger">
          分級為暫定值，依實測誤配率調整
        </span>
        <span className="font-kai text-[11px] text-carbon-soft">唯讀檢視 · 所有改動在後台</span>
      </div>
    </div>
  );
}
