/**
 * Cloudflare Worker for MV Face Recognition
 * Serves static frontend and provides API for metadata/videos
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const { pathname } = url;

    // CORS headers for all responses
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // API routes
      if (pathname.startsWith('/api/')) {
        return await handleApiRequest(pathname, request, env, corsHeaders);
      }

      // Video files from R2
      if (pathname.startsWith('/videos/')) {
        return await handleVideoRequest(pathname, request, env, corsHeaders);
      }

      // Static frontend files
      return await handleStaticRequest(pathname, request, env, corsHeaders);
      
    } catch (error) {
      console.error('Worker error:', error);
      return new Response(JSON.stringify({ error: 'Internal server error' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  }
};

/**
 * Handle API requests
 */
async function handleApiRequest(pathname, request, env, corsHeaders) {
  const path = pathname.replace('/api', '');

  switch (path) {
    case '/system/status':
      return new Response(JSON.stringify({
        chromadb_connected: true,
        model_loaded: true,
        services_running: true,
        contestant_count: 96,
        video_count: 5,
        processing_jobs: 0
      }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });

    case '/contestants':
      const contestants = await env.METADATA_KV.get('contestants');
      return new Response(contestants || '[]', {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });

    case '/videos':
      const videos = await env.METADATA_KV.get('videos_list');
      return new Response(videos || '[]', {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });

    case '/settings':
      if (request.method === 'GET') {
        const settings = await env.METADATA_KV.get('app_settings');
        return new Response(settings || JSON.stringify({
          theme: 'auto',
          notifications: true,
          autoRefresh: true,
          refreshInterval: 30,
          maxConcurrentJobs: 3,
          videoQuality: 'medium',
          faceDetectionThreshold: 0.8
        }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      } else if (request.method === 'PUT') {
        const newSettings = await request.json();
        await env.METADATA_KV.put('app_settings', JSON.stringify(newSettings));
        return new Response(JSON.stringify(newSettings), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
      break;

    default:
      if (path.startsWith('/videos/') && path.endsWith('/metadata')) {
        // Get video metadata
        const videoId = path.split('/')[2];
        const metadata = await env.METADATA_KV.get(`video_metadata_${videoId}`);
        return new Response(metadata || '{}', {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
  }

  return new Response(JSON.stringify({ error: 'API endpoint not found' }), {
    status: 404,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

/**
 * Handle video file requests from R2
 */
async function handleVideoRequest(pathname, request, env, corsHeaders) {
  const videoPath = pathname.replace('/videos/', '');
  
  try {
    // Check if R2 bucket is available
    if (!env.VIDEOS_BUCKET) {
      return new Response(JSON.stringify({ 
        error: 'Video storage not configured. Please enable R2 in your Cloudflare dashboard.' 
      }), { 
        status: 503,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const object = await env.VIDEOS_BUCKET.get(videoPath);
    
    if (!object) {
      return new Response('Video not found', { 
        status: 404,
        headers: corsHeaders 
      });
    }

    const headers = {
      ...corsHeaders,
      'Content-Type': 'video/mp4',
      'Cache-Control': 'public, max-age=86400', // Cache for 24 hours
    };

    // Handle range requests for video streaming
    const range = request.headers.get('Range');
    if (range) {
      const size = object.size;
      const [start, end] = parseRange(range, size);
      
      headers['Content-Range'] = `bytes ${start}-${end}/${size}`;
      headers['Content-Length'] = (end - start + 1).toString();
      headers['Accept-Ranges'] = 'bytes';
      
      const stream = object.body.slice(start, end + 1);
      return new Response(stream, {
        status: 206,
        headers
      });
    }

    return new Response(object.body, { headers });
    
  } catch (error) {
    console.error('Error serving video:', error);
    return new Response('Error serving video', { 
      status: 500,
      headers: corsHeaders 
    });
  }
}

/**
 * Handle static frontend files
 */
async function handleStaticRequest(pathname, request, env, corsHeaders) {
  // For now, return a simple message indicating the frontend will be served
  // In production, you'd upload the built files to KV store or use Workers Sites
  
  if (pathname === '/' || pathname === '/index.html') {
    return new Response(`
<!DOCTYPE html>
<html>
<head>
  <title>MV Face Recognition</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; }
    .container { max-width: 800px; margin: 0 auto; }
    .status { padding: 20px; border-radius: 8px; margin: 20px 0; }
    .info { background: #e7f3ff; border: 1px solid #b3d9ff; }
    .success { background: #d4edda; border: 1px solid #c3e6cb; }
    .warning { background: #fff3cd; border: 1px solid #ffeaa7; }
    .error { background: #f8d7da; border: 1px solid #f5c6cb; }
  </style>
</head>
<body>
  <div class="container">
    <h1>🎥 MV Face Recognition</h1>
    <div class="status success">
      <h3>✅ Worker Deployed Successfully!</h3>
      <p>Your Cloudflare Worker is now running.</p>
    </div>
    
    <div class="status info">
      <h3>📊 System Status</h3>
      <p>API endpoints are available at:</p>
      <ul>
        <li><a href="/api/system/status">/api/system/status</a></li>
        <li><a href="/api/contestants">/api/contestants</a></li>
        <li><a href="/api/videos">/api/videos</a></li>
        <li><a href="/api/settings">/api/settings</a></li>
      </ul>
    </div>
    
    <div class="status warning">
      <h3>⚠️ Next Steps</h3>
      <p>To complete setup:</p>
      <ol>
        <li>Enable R2 in your Cloudflare dashboard</li>
        <li>Upload your processed videos using the upload scripts</li>
        <li>Upload metadata to KV store</li>
        <li>The full SvelteKit frontend will be available</li>
      </ol>
    </div>
  </div>
</body>
</html>
    `, {
      headers: {
        ...corsHeaders,
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=3600'
      }
    });
  }

  return new Response('File not found', { 
    status: 404,
    headers: corsHeaders 
  });
}

/**
 * Parse HTTP Range header
 */
function parseRange(range, size) {
  const parts = range.replace(/bytes=/, '').split('-');
  const start = parseInt(parts[0], 10) || 0;
  const end = parseInt(parts[1], 10) || size - 1;
  return [start, end];
}

/**
 * Get content type based on file extension
 */
function getContentType(filePath) {
  const ext = filePath.split('.').pop()?.toLowerCase();
  
  const mimeTypes = {
    'html': 'text/html; charset=utf-8',
    'js': 'application/javascript',
    'css': 'text/css',
    'json': 'application/json',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'svg': 'image/svg+xml',
    'ico': 'image/x-icon',
    'woff': 'font/woff',
    'woff2': 'font/woff2',
    'ttf': 'font/ttf',
    'eot': 'application/vnd.ms-fontobject'
  };

  return mimeTypes[ext] || 'application/octet-stream';
}