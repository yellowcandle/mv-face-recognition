import React, { useMemo, useCallback } from 'react';
import { BAND_STAMP, bandFor } from '../../lib/bands';

interface Appearance {
  timestamp: number;
  frame_number: number;
  match_score: number; // raw cosine
  bbox: [number, number, number, number]; // frame fractions, canonical [x1, y1, x2, y2]
}

interface ContestantData {
  appearances: Appearance[];
  total_appearances: number;
  average_match_score: number; // raw cosine
  first_appearance: number;
  last_appearance: number;
  contestant_info: { id: string; name: string; nickname: string };
}

interface ContestantTimelineProps {
  contestantTimeline: Record<string, ContestantData>;
  duration: number;
  currentTime: number;
  onSeek: (time: number) => void;
}

interface Segment {
  start: number;
  end: number;
}

function buildSegments(appearances: Appearance[], gap = 1.0): Segment[] {
  if (appearances.length === 0) return [];

  const sorted = [...appearances].sort((a, b) => a.timestamp - b.timestamp);
  const segments: Segment[] = [];
  let start = sorted[0].timestamp;
  let end = sorted[0].timestamp;

  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].timestamp - end < gap) {
      end = sorted[i].timestamp;
    } else {
      segments.push({ start, end });
      start = sorted[i].timestamp;
      end = sorted[i].timestamp;
    }
  }
  segments.push({ start, end });
  return segments;
}

export const ContestantTimeline = React.memo(function ContestantTimeline({
  contestantTimeline,
  duration,
  currentTime,
  onSeek,
}: ContestantTimelineProps) {
  const entries = useMemo(() => {
    return Object.entries(contestantTimeline).map(([key, data]) => ({
      key,
      data,
      segments: buildSegments(data.appearances),
    }));
  }, [contestantTimeline]);

  const handleBarClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>, _entry: (typeof entries)[number]) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const ratio = x / rect.width;
      onSeek(ratio * duration);
    },
    [duration, onSeek],
  );

  const playheadPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="flex w-full flex-col gap-2">
      <h3 className="font-kai text-[18px] font-normal text-carbon-deep">參賽者時間軸</h3>

      <div className="max-h-[180px] overflow-y-auto">
        {entries.map((entry) => (
          <div
            key={entry.key}
            className="flex h-9 items-center gap-2 border-b border-carbon-deep/13"
          >
            <div
              className="w-16 shrink-0 truncate font-kai text-[12px] text-carbon-soft"
              title={`${entry.data.contestant_info.nickname} · 平均 ${entry.data.average_match_score.toFixed(2)} ${BAND_STAMP[bandFor(entry.data.average_match_score)].word}`}
            >
              {entry.data.contestant_info.nickname}
            </div>

            <div
              className="relative h-5 flex-1 cursor-pointer overflow-hidden rounded-xs bg-tint"
              onClick={(e) => handleBarClick(e, entry)}
            >
              {entry.segments.map((seg, i) => {
                if (duration <= 0) return null;
                const left = (seg.start / duration) * 100;
                const width = Math.max(((seg.end - seg.start) / duration) * 100, 0.3);
                return (
                  <div
                    key={i}
                    className="absolute top-0 h-full bg-carbon-soft"
                    style={{ left: `${left}%`, width: `${width}%` }}
                  />
                );
              })}

              <div
                className="pointer-events-none absolute top-0 z-10 h-full w-0.5 bg-stamp"
                style={{ left: `${playheadPercent}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});
