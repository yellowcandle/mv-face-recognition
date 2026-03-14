import { Card, Button } from '@mv/shared';
import { useVideos, useFlaggedFaces } from '@mv/shared';

export function Dashboard() {
  const { data: videos = [] } = useVideos();
  const { data: flagged = [] } = useFlaggedFaces();

  const stats = [
    { label: 'Videos Processed', value: videos.length, icon: '🎬' },
    { label: 'Contestants', value: 96, icon: '👥' },
    { label: 'Pending Flags', value: flagged.filter(f => f.status === 'pending').length, icon: '🚩' },
  ];

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid grid-cols-3 gap-4">
        {stats.map(s => (
          <Card key={s.label}>
            <div className="text-3xl mb-1">{s.icon}</div>
            <div className="text-3xl font-semibold text-slate-100">{s.value}</div>
            <div className="text-sm text-slate-500 mt-1">{s.label}</div>
          </Card>
        ))}
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">Quick Links</h2>
        <div className="grid grid-cols-2 gap-3">
          {[
            { href: '/player', icon: '▶️', label: 'Video Player', desc: 'Watch annotated videos with face overlays' },
            { href: '/contestants', icon: '👥', label: 'Contestants', desc: 'Browse contestant directory' },
            { href: '/embedding-workbench', icon: '🧬', label: 'Embedding Workbench', desc: 'Evaluate and improve embeddings' },
            { href: '/ingestion', icon: '📤', label: 'Ingestion', desc: 'Process new videos' },
            { href: '/flagging', icon: '🚩', label: 'Flagging', desc: 'Review face corrections' },
          ].map(link => (
            <a key={link.href} href={link.href} className="block">
              <Card className="hover:border-slate-600 transition-colors cursor-pointer">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{link.icon}</span>
                  <div>
                    <div className="font-medium text-slate-200">{link.label}</div>
                    <div className="text-xs text-slate-500">{link.desc}</div>
                  </div>
                </div>
              </Card>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
