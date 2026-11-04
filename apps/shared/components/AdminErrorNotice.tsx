import { errorMessage, isSessionExpired } from '../lib/adminApi';

interface AdminErrorNoticeProps {
  /** The caught error; renders nothing when falsy. */
  error: unknown;
  /** Shown as a retry button for non-session errors. */
  onRetry?: () => void;
  /** Prefix for non-session errors, e.g. "標記失敗". Defaults to "讀取失敗". */
  label?: string;
  className?: string;
}

/**
 * One inline failure strip. It names the actual error and, when the failure is an expired
 * Cloudflare Access session, offers the only action that can fix it: reload.
 */
export function AdminErrorNotice({
  error,
  onRetry,
  label = '讀取失敗',
  className = '',
}: AdminErrorNoticeProps) {
  if (!error) return null;
  const expired = isSessionExpired(error);
  return (
    <div
      role="alert"
      className={`flex flex-row items-center justify-between gap-4 border border-stamp/50 bg-stamp/5 px-4 py-2.5 ${className}`}
    >
      <span className="font-kai text-[12px] leading-snug text-stamp">
        {expired ? '登入已過期，請重新載入頁面。' : `${label} — ${errorMessage(error)}`}
      </span>
      {expired ? (
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="shrink-0 border border-stamp px-3 py-1 font-kai text-[11px] text-stamp hover:bg-stamp hover:text-paper-light"
        >
          重新載入
        </button>
      ) : onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 border border-stamp/60 px-3 py-1 font-kai text-[11px] text-stamp hover:bg-stamp hover:text-paper-light"
        >
          重試
        </button>
      ) : null}
    </div>
  );
}
