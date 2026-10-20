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

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
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
    <div className="flex items-center gap-3 bg-paper-light border border-paper-dark rounded-none px-4 py-2">
      {/* Playback buttons */}
      <div className="flex items-center gap-1">
        <button
          className="text-carbon hover:text-white px-1.5 py-1 text-sm disabled:opacity-40"
          onClick={() => onSkipSeconds(-5)}
          disabled={disabled}
          title="Back 5 seconds"
        >
          -5s
        </button>
        <button
          className="text-carbon hover:text-white px-1.5 py-1 text-sm disabled:opacity-40"
          onClick={() => onSkipFrames(-1)}
          disabled={disabled}
          title="Previous frame"
        >
          &lt;
        </button>
        <button
          className="w-10 h-10 rounded-full bg-stamp hover:bg-stamp text-white text-lg flex items-center justify-center disabled:opacity-40 disabled:hover:bg-stamp"
          onClick={onTogglePlay}
          disabled={disabled}
        >
          {isPlaying ? '\u23F8' : '\u25B6'}
        </button>
        <button
          className="text-carbon hover:text-white px-1.5 py-1 text-sm disabled:opacity-40"
          onClick={() => onSkipFrames(1)}
          disabled={disabled}
          title="Next frame"
        >
          &gt;
        </button>
        <button
          className="text-carbon hover:text-white px-1.5 py-1 text-sm disabled:opacity-40"
          onClick={() => onSkipSeconds(5)}
          disabled={disabled}
          title="Forward 5 seconds"
        >
          +5s
        </button>
      </div>

      {/* Time display */}
      <span className="text-carbon-soft text-sm font-mono whitespace-nowrap">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>

      {/* Seek bar */}
      <div className="flex-1 mx-2">
        <input
          type="range"
          className="w-full h-1.5 rounded-full appearance-none cursor-pointer bg-paper-deep accent-stamp"
          min={0}
          max={duration || 0}
          step={0.1}
          value={currentTime}
          onChange={(e) => onSeek(parseFloat(e.target.value))}
          disabled={disabled}
        />
      </div>

      {/* Speed selector */}
      <div className="flex items-center gap-1">
        <span className="text-ledger text-xs">Speed</span>
        <select
          className="bg-paper-dark text-carbon-deep border border-paper-deep rounded px-1.5 py-1 text-xs"
          value={playbackSpeed}
          onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
        >
          {SPEED_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}x
            </option>
          ))}
        </select>
      </div>

      {/* Volume */}
      <div className="flex items-center gap-1.5">
        <span className="text-carbon-soft text-sm">Vol</span>
        <input
          type="range"
          className="w-16 h-1 rounded-full appearance-none cursor-pointer bg-paper-deep accent-stamp"
          min={0}
          max={1}
          step={0.1}
          value={volume}
          onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
        />
      </div>
    </div>
  );
}
