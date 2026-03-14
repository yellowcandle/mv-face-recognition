import { Link } from 'react-router';
import { Card } from '@mv/shared';
import { useVideos } from '@mv/shared';

export function Home() {
  const { data: videos = [], isLoading } = useVideos();

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-slate-100 mb-2">MV Face Recognition</h1>
        <p className="text-slate-400">
          Watch music videos with AI-powered face recognition overlays identifying contestants in real-time.
        </p>
      </div>

      {isLoading ? (
        <div className="text-center py-20 text-slate-500">Loading videos...</div>
      ) : videos.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg mb-2">No processed videos yet</p>
          <p className="text-sm">Videos will appear here after processing.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {videos.map((video) => (
            <Link key={video.id} to={`/player?video=${video.id}`}>
              <Card className="hover:border-slate-600 transition-colors cursor-pointer group">
                <div className="aspect-video bg-slate-800 rounded mb-3 flex items-center justify-center">
                  <span className="text-4xl opacity-50 group-hover:opacity-80 transition-opacity">▶️</span>
                </div>
                <h3 className="font-medium text-slate-200 truncate">{video.name}</h3>
                <p className="text-xs text-slate-500 mt-1">ID: {video.id}</p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
