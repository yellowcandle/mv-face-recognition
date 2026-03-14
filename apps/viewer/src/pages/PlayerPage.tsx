import { Player } from '@mv/shared';

export function PlayerPage() {
  return (
    <div className="h-[calc(100vh-3.5rem)]">
      <Player mode="viewer" apiBase="" />
    </div>
  );
}
