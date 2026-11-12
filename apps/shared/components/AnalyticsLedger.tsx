import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Masthead } from './Masthead';
import { DetectionStamp, Stamp } from './Stamp';
import { ledgerRows, spanPercent, type LedgerRow, type LedgerSort } from './ledgerRows';
import { useContestants } from '../hooks/useContestants';
import { useVideos } from '../hooks/useVideos';
import { BAND_CUTOFFS, BAND_STAMP, bandFor, type Band } from '../lib/bands';
import { portraitSrc } from '../lib/portrait';
import { formatMmSs, videoShortName } from '../lib/format';
import type { VideoMetadata } from '../types';

type Variant = 'admin' | 'viewer';

const SORTS: Array<[LedgerSort, string]> = [
  ['appearances', '出場次數'],
  ['avgMatchScore', '平均分'],
];

const BAND_DOT: Record<Band, string> = {
  high: 'bg-carbon',
  medium: 'bg-stamp',
  low: 'bg-ink-muted',
};

/** The two designs share one table; only these measures and words differ. */
const LOOK = {
  admin: {
    root: 'px-8',
    scroller: 'min-h-0 flex-1 overflow-y-auto',
    select: 'field field-select w-[260px]',
    figures: 'border-b pb-4',
    head: ['編號', '參賽者', '出場次數', '平均分', '最高分', '出場時段'],
    widths: ['w-11', '', 'w-[88px]', 'w-28', 'w-28', 'w-61'],
    narrow: '',
    row: 'h-10',
    who: 'gap-2',
    realName: 'text-[12px]',
    count: 'text-[14px]',
    score: 'text-carbon',
    dash: '–',
  },
  viewer: {
    // Phones let the page scroll instead of boxing the table into a few rows.
    root: 'px-4 max-sm:h-auto max-sm:pt-6 sm:px-14',
    scroller: 'sm:min-h-0 sm:flex-1 sm:overflow-y-auto',
    select: 'field field-select h-10 w-[260px] max-w-full text-[14px] text-carbon-deep',
    figures: 'border-y py-3 max-sm:grid-cols-2 max-sm:gap-y-3',
    head: ['編號', '參賽者', '出場', '平均', '最高', '出現時段'],
    // 最高 and 出現時段 drop on phones so 參賽者 keeps room for a name.
    widths: [
      'w-10 sm:w-13',
      '',
      'w-12 sm:w-25',
      'w-24 sm:w-35',
      'max-sm:hidden sm:w-35',
      'max-sm:hidden sm:w-45',
    ],
    narrow: 'max-sm:hidden',
    row: 'h-9',
    who: 'gap-2.5',
    realName: 'text-[13px]',
    count: 'text-[13px]',
    score: 'text-carbon-soft',
    dash: ' — ',
  },
} as const;

function Score({
  value,
  label,
  className,
  decided,
}: {
  value: number | null;
  label: string;
  className: string;
  decided: boolean;
}) {
  if (value == null) {
    if (decided) {
      return (
        <span className="flex justify-end">
          <DetectionStamp detection={{ match_source: 'flag', match_score: null }} />
        </span>
      );
    }
    return (
      <span className={`block text-right font-mono text-[13px] tabular-nums ${className}`}>—</span>
    );
  }
  return (
    <span className="flex items-center justify-end gap-2" title={`${label} ${value.toFixed(3)}`}>
      <span className={`font-mono text-[13px] tabular-nums ${className}`}>{value.toFixed(2)}</span>
      <Stamp band={bandFor(value)} />
    </span>
  );
}

/** Admin leads with this reel's own crop of the face; the public copy with the cast portrait. */
function Face({
  videoId,
  row,
  portrait,
  variant,
}: {
  videoId: string;
  row: LedgerRow;
  portrait: string | null;
  variant: Variant;
}) {
  const crop =
    variant === 'admin' && row.crop
      ? `/api/faces/crop?video_id=${encodeURIComponent(videoId)}&frame_number=${row.crop.frameNumber}&detection_index=${row.crop.detectionIndex}&width=64`
      : null;
  const [failed, setFailed] = useState<string | null>(null);
  const src = crop && crop !== failed ? crop : portrait;
  const sized = src === portrait ? portraitSrc(src, 28) : src;
  return src && src !== failed ? (
    <img
      src={sized!}
      alt=""
      loading="lazy"
      className="size-7 shrink-0 rounded object-cover"
      onError={(e) => {
        // A failed resize retries the original once before the face is given up on.
        if (e.currentTarget.src.includes('/cdn-cgi/image/')) e.currentTarget.src = src!;
        else setFailed(src);
      }}
    />
  ) : (
    <div className="size-7 shrink-0 rounded bg-tint" />
  );
}

/**
 * 紀錄 — the ledger of who was filed, per reel. Same data, read as a filing record.
 * Shared by the back office and the viewer; `variant` picks which design it wears.
 */
export function AnalyticsLedger({ variant }: { variant: Variant }) {
  const look = LOOK[variant];
  const { data: videos = [] } = useVideos();
  const { data: contestants = [] } = useContestants();
  const [selectedVideoId, setSelectedVideoId] = useState<string>('');
  const [sortBy, setSortBy] = useState<LedgerSort>('appearances');

  const videoId = selectedVideoId || videos[0]?.id || '';

  const {
    data: metadata,
    isLoading,
    isError,
  } = useQuery<VideoMetadata>({
    queryKey: ['video-metadata', videoId],
    queryFn: async () => {
      const res = await fetch(`/api/videos/metadata/dense/${encodeURIComponent(videoId)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: !!videoId,
    staleTime: 5 * 60 * 1000,
  });

  const rows = useMemo(
    () => ledgerRows(metadata?.contestant_timeline, sortBy, metadata?.frame_data),
    [metadata, sortBy],
  );

  const portraits = useMemo(
    () =>
      new Map(
        (contestants as Array<{ id: string; portrait_url?: string | null }>).map((c) => [
          String(c.id),
          c.portrait_url ?? null,
        ]),
      ),
    [contestants],
  );

  const summary = metadata?.processing_summary;
  const duration = metadata?.video_info?.duration;

  const legend = (
    [
      ['high', `≥ ${BAND_CUTOFFS.high}`],
      ['medium', `${BAND_CUTOFFS.medium}${look.dash}${BAND_CUTOFFS.high}`],
      ['low', `< ${BAND_CUTOFFS.medium}`],
    ] as const
  ).map(([band, range]) => (
    <span key={band} className={`flex items-center ${variant === 'viewer' ? 'gap-1.5' : 'gap-1'}`}>
      {variant === 'viewer' ? <span className={`size-2 rounded-full ${BAND_DOT[band]}`} /> : null}
      <span
        className={`font-kai text-[12px] ${
          variant === 'viewer' ? 'text-carbon-deep' : 'text-carbon-soft'
        }`}
      >
        {BAND_STAMP[band].word}
      </span>
      <span className="font-mono text-[12px] tabular-nums text-ink-muted">{range}</span>
    </span>
  ));

  return (
    <div className={`flex h-full min-h-0 flex-1 flex-col gap-4 pb-5 pt-8 ${look.root}`}>
      <Masthead title="紀錄" hint="唯讀的辨識結果帳冊">
        <select
          aria-label="影片"
          className={look.select}
          value={videoId}
          onChange={(e) => setSelectedVideoId(e.target.value)}
        >
          {videos.map((v) => (
            <option key={v.id} value={v.id}>
              {videoShortName(v.name)}
            </option>
          ))}
        </select>
      </Masthead>

      {summary && (
        <div className={`grid grid-cols-4 border-carbon-deep/13 ${look.figures}`}>
          {[
            { label: '影格', value: summary.frames_processed.toLocaleString() },
            { label: '偵測', value: summary.total_faces_detected.toLocaleString() },
            { label: '辨識', value: summary.total_recognitions.toLocaleString() },
            { label: '出場', value: summary.unique_contestants.toLocaleString() },
          ].map((s) => (
            <div key={s.label} className="flex flex-col gap-1">
              <span className="font-kai text-[13px] text-carbon-soft">{s.label}</span>
              <span className="font-mono text-[28px] leading-tight tabular-nums text-carbon-deep">
                {s.value}
              </span>
            </div>
          ))}
        </div>
      )}

      {variant === 'admin' ? (
        <div className="flex items-center gap-2">
          <span className="font-kai text-[12px] text-ink-muted">排序</span>
          {SORTS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={sortBy === key}
              onClick={() => setSortBy(key)}
              className={`h-8 rounded-md border px-3 font-kai text-[13px] transition-colors ${
                sortBy === key
                  ? 'border-carbon-deep/33 bg-tint font-bold text-carbon-deep'
                  : 'border-carbon-deep/13 text-carbon-soft hover:bg-tint'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-4">
          <span className="font-kai text-[13px] text-carbon-soft">排序</span>
          {SORTS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={sortBy === key}
              onClick={() => setSortBy(key)}
              className={`border-b-2 py-1 font-kai text-[14px] transition-colors ${
                sortBy === key
                  ? 'border-stamp font-bold text-carbon-deep'
                  : 'border-transparent text-carbon-soft hover:text-carbon-deep'
              }`}
            >
              {label}
            </button>
          ))}
          <span className="ml-auto font-kai text-[12px] text-ink-muted">
            <span className="font-mono tabular-nums">{rows.length}</span> 位
          </span>
        </div>
      )}

      {isLoading ? (
        <div className="py-16 text-center font-kai text-[14px] text-carbon-soft">正在調閱紀錄…</div>
      ) : isError ? (
        <div className="py-16 text-center font-kai text-[14px] text-stamp">
          讀不到這卷影片的紀錄。
        </div>
      ) : rows.length === 0 ? (
        <div className="py-16 text-center font-kai text-[14px] text-carbon-soft">
          這卷影片沒有可核對的紀錄。
        </div>
      ) : (
        <div className={look.scroller}>
          <table className="w-full table-fixed border-separate border-spacing-0">
            <thead className="sticky top-0 z-10 bg-ground">
              <tr className="h-7">
                {look.head.map((label, i) => (
                  <th
                    key={label}
                    scope="col"
                    className={`border-b border-carbon-deep/33 font-kai text-[12px] font-normal text-ink-muted ${
                      look.widths[i]
                    } ${i < 2 ? 'text-left' : 'text-right'}`}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const span =
                  variant === 'admin' ? spanPercent(r.firstSeen, r.lastSeen, duration) : null;
                const cell = 'border-b border-carbon-deep/13';
                return (
                  <tr key={r.id} className={`${look.row} hover:bg-tint`}>
                    <td className={`${cell} font-mono text-[13px] tabular-nums text-carbon-soft`}>
                      {r.id.padStart(2, '0')}
                    </td>
                    <td className={cell}>
                      <span className={`flex min-w-0 items-center ${look.who}`}>
                        <Face
                          videoId={videoId}
                          row={r}
                          portrait={portraits.get(r.id) ?? null}
                          variant={variant}
                        />
                        <span className="truncate font-kai text-[15px] text-carbon-deep">
                          {r.nickname}
                        </span>
                        <span className={`truncate font-kai text-ink-muted ${look.realName}`}>
                          {r.name}
                        </span>
                      </span>
                    </td>
                    <td
                      className={`${cell} text-right font-mono tabular-nums text-carbon-deep ${look.count}`}
                    >
                      {r.appearances}
                    </td>
                    <td className={cell}>
                      <Score
                        value={r.avgMatchScore}
                        label="平均"
                        className={look.score}
                        decided={r.decided}
                      />
                    </td>
                    <td className={`${cell} ${look.narrow}`}>
                      <Score
                        value={r.maxMatchScore}
                        label="最高"
                        className={look.score}
                        decided={r.decided}
                      />
                    </td>
                    <td className={`${cell} ${look.narrow}`}>
                      <span className="flex items-center justify-end gap-2">
                        {span ? (
                          <span className="relative h-2 w-[120px] shrink-0 overflow-hidden rounded-xs bg-tint">
                            <span
                              className="absolute top-0 h-full bg-carbon-soft"
                              style={{ left: `${span.left}%`, width: `${span.width}%` }}
                            />
                          </span>
                        ) : null}
                        <span
                          className={`font-mono tabular-nums text-carbon-soft ${
                            variant === 'admin' ? 'text-[12px]' : 'text-[13px]'
                          }`}
                        >
                          {formatMmSs(r.firstSeen)}
                          {look.dash}
                          {formatMmSs(r.lastSeen)}
                        </span>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {variant === 'viewer' ? (
        <>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
            <span className="font-kai text-[12px] text-ink-muted">分級</span>
            {legend}
          </div>
          <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 font-kai text-[12px] text-ink-muted">
            <span>分級為暫定值，依實測誤配率調整</span>
            <span>唯讀檢視 · 所有改動在後台</span>
          </div>
        </>
      ) : (
        <div className="flex items-center justify-between gap-4 font-kai text-[12px] text-ink-muted">
          <div className="flex items-center gap-4">
            <span>分級</span>
            {legend}
            <span>分級為暫定值，依實測誤配率調整</span>
          </div>
          <span>唯讀檢視 · 所有改動在後台</span>
        </div>
      )}
    </div>
  );
}
