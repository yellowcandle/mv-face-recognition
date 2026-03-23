import React, { useMemo, useCallback } from "react";

interface Appearance {
  timestamp: number;
  frame_number: number;
  confidence: number;
  face_location: number[];
}

interface ContestantData {
  appearances: Appearance[];
  total_appearances: number;
  average_confidence: number;
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

const SEGMENT_COLORS = [
  "#22C55E",
  "#FF8400",
  "#4363D8",
  "#E6194B",
  "#42D4F4",
  "#F032E6",
];

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
    return Object.entries(contestantTimeline).map(([key, data], index) => ({
      key,
      data,
      color: SEGMENT_COLORS[index % SEGMENT_COLORS.length],
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
    <div
      className="w-full rounded-lg p-4"
      style={{ backgroundColor: "#1A1A1A" }}
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">
          Contestant Timeline
        </h3>
      </div>

      <div
        className="overflow-y-auto"
        style={{ maxHeight: `${5 * (36 + 8 * 2)}px` }}
      >
        {entries.map((entry) => (
          <div
            key={entry.key}
            className="flex items-center"
            style={{
              height: "36px",
              paddingTop: "8px",
              paddingBottom: "8px",
              borderBottom: "1px solid #2E2E2E",
            }}
          >
            <div
              className="shrink-0 truncate pr-2 text-xs text-gray-300"
              style={{
                width: "60px",
                fontFamily:
                  'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK JP", sans-serif',
              }}
              title={entry.data.contestant_info.nickname}
            >
              {entry.data.contestant_info.nickname}
            </div>

            <div
              className="relative flex-1 cursor-pointer rounded-sm"
              style={{ backgroundColor: "#2E2E2E", height: "20px" }}
              onClick={(e) => handleBarClick(e, entry)}
            >
              {entry.segments.map((seg, i) => {
                if (duration <= 0) return null;
                const left = (seg.start / duration) * 100;
                const width = Math.max(
                  ((seg.end - seg.start) / duration) * 100,
                  0.3,
                );
                return (
                  <div
                    key={i}
                    className="absolute top-0 h-full rounded-sm"
                    style={{
                      left: `${left}%`,
                      width: `${width}%`,
                      backgroundColor: entry.color,
                      opacity: 0.85,
                    }}
                  />
                );
              })}

              <div
                className="pointer-events-none absolute top-0 h-full"
                style={{
                  left: `${playheadPercent}%`,
                  width: "2px",
                  backgroundColor: "#FF8400",
                  zIndex: 10,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});
