import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react';
import { formatMmSs } from '../../lib/format';
import { tickPercent } from './faceView';

interface PlayerControlsProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  playbackSpeed: number;
  volume: number;
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
  onSpeedChange: (speed: number) => void;
  onVolumeChange: (volume: number) => void;
  onSkipFrames: (frames: number) => void;
  onSkipSeconds: (seconds: number) => void;
  disabled: boolean;
}

const SPEED_OPTIONS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2];

const STEP =
  'inline-flex h-8 items-center justify-center rounded-md px-2 font-mono text-[13px] text-carbon transition-colors hover:bg-tint disabled:cursor-not-allowed disabled:opacity-45';

/** A native range for input and keyboard, invisible over a drawn track. */
function Slider({
  label,
  value,
  max,
  step,
  disabled,
  knob,
  onChange,
}: {
  label: string;
  value: number;
  max: number;
  step: number;
  disabled?: boolean;
  knob?: boolean;
  onChange: (value: number) => void;
}) {
  const percent = tickPercent(value, max);
  return (
    <div className="relative h-4 w-full">
      <input
        type="range"
        aria-label={label}
        className="peer absolute inset-0 z-10 m-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
        min={0}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
      <div className="absolute inset-x-0 top-1.5 h-1 rounded-xs bg-carbon-deep/13 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-stamp" />
      <div
        className="absolute left-0 top-1.5 h-1 rounded-xs bg-carbon"
        style={{ width: `${percent}%` }}
      />
      {knob ? (
        <div
          className="absolute top-0.5 h-3 w-2 -translate-x-1/2 rounded-xs bg-carbon-deep"
          style={{ left: `${percent}%` }}
        />
      ) : null}
    </div>
  );
}

export function PlayerControls({
  isPlaying,
  currentTime,
  duration,
  playbackSpeed,
  volume,
  onTogglePlay,
  onSeek,
  onSpeedChange,
  onVolumeChange,
  onSkipFrames,
  onSkipSeconds,
  disabled,
}: PlayerControlsProps) {
  return (
    <div className="flex h-10 items-center gap-3">
      <div className="flex items-center gap-1">
        <button
          className={STEP}
          onClick={() => onSkipSeconds(-5)}
          disabled={disabled}
          title="後退五秒"
          aria-label="後退五秒"
        >
          -5s
        </button>
        <button
          className={STEP}
          onClick={() => onSkipFrames(-1)}
          disabled={disabled}
          title="上一格"
          aria-label="上一格"
        >
          <ChevronLeft size={16} aria-hidden />
        </button>
        <button
          className="inline-flex size-10 items-center justify-center rounded-md bg-carbon-deep text-paper-light transition-colors hover:bg-carbon disabled:cursor-not-allowed disabled:opacity-45"
          onClick={onTogglePlay}
          disabled={disabled}
          aria-label={isPlaying ? '暫停' : '播放'}
        >
          {isPlaying ? <Pause size={16} aria-hidden /> : <Play size={16} aria-hidden />}
        </button>
        <button
          className={STEP}
          onClick={() => onSkipFrames(1)}
          disabled={disabled}
          title="下一格"
          aria-label="下一格"
        >
          <ChevronRight size={16} aria-hidden />
        </button>
        <button
          className={STEP}
          onClick={() => onSkipSeconds(5)}
          disabled={disabled}
          title="前進五秒"
          aria-label="前進五秒"
        >
          +5s
        </button>
      </div>

      <span className="whitespace-nowrap font-mono text-[13px] tabular-nums text-carbon-soft">
        {formatMmSs(currentTime)} / {formatMmSs(duration)}
      </span>

      <div className="min-w-0 flex-1">
        <Slider
          label="播放位置"
          value={currentTime}
          max={duration || 0}
          step={0.1}
          disabled={disabled}
          knob
          onChange={onSeek}
        />
      </div>

      <label className="flex items-center gap-2 font-kai text-[12px] text-ink-muted">
        速度
        <select
          className="field field-select w-[72px] pl-2 pr-6 font-mono"
          value={playbackSpeed}
          onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
        >
          {SPEED_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}x
            </option>
          ))}
        </select>
      </label>

      <div className="flex items-center gap-2">
        <span aria-hidden className="font-kai text-[12px] text-ink-muted">
          音量
        </span>
        <div className="w-16">
          <Slider label="音量" value={volume} max={1} step={0.1} onChange={onVolumeChange} />
        </div>
      </div>
    </div>
  );
}
