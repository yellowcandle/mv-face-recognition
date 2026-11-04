import { useSearchParams } from 'react-router';
import { Player as SharedPlayer } from '@mv/shared';

export function Player() {
  // `?video=<id>` is how a link into a specific reel is spelled; the shared player falls back to
  // the first video when the id is absent or names one it does not have.
  const [searchParams] = useSearchParams();
  return <SharedPlayer mode="admin" apiBase="" initialVideoId={searchParams.get('video')} />;
}
