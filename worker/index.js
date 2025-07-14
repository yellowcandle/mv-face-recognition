/**
 * Cloudflare Worker for MV Face Recognition API
 * Serves SvelteKit frontend, API endpoints, and video streaming
 */

// Mock data for demonstration
const MOCK_VIDEOS = [
  {
    id: "1",
    name: "《全民造星IV》主題曲 《前傳》MV",
    filename: "video-1.mp4",
    duration: 240.5,
    uploadedAt: "2024-07-01T00:00:00Z",
    status: "completed",
    thumbnail: "/api/videos/1/thumbnail"
  },
  {
    id: "2", 
    name: "女團の駅 Performance",
    filename: "video-2.mp4",
    duration: 180.2,
    uploadedAt: "2024-07-02T00:00:00Z", 
    status: "completed",
    thumbnail: "/api/videos/2/thumbnail"
  },
  {
    id: "3",
    name: "Practice Session Video",
    filename: "video-3.mp4",
    duration: 300.8,
    uploadedAt: "2024-07-03T00:00:00Z",
    status: "completed", 
    thumbnail: "/api/videos/3/thumbnail"
  },
  {
    id: "4",
    name: "Behind the Scenes",
    filename: "video-4.mp4", 
    duration: 420.1,
    uploadedAt: "2024-07-04T00:00:00Z",
    status: "processing",
    thumbnail: "/api/videos/4/thumbnail"
  },
  {
    id: "5",
    name: "Rehearsal Footage", 
    filename: "video-5.mp4",
    duration: 195.6,
    uploadedAt: "2024-07-05T00:00:00Z",
    status: "completed",
    thumbnail: "/api/videos/5/thumbnail"
  }
];

const MOCK_CONTESTANTS = [
  { id: 1, name: "張三", nickname: "小張", age: 22, photo: "/api/contestants/1/photo" },
  { id: 2, name: "李四", nickname: "小李", age: 21, photo: "/api/contestants/2/photo" },
  { id: 3, name: "王五", nickname: "小王", age: 23, photo: "/api/contestants/3/photo" },
  { id: 4, name: "趙六", nickname: "小趙", age: 20, photo: "/api/contestants/4/photo" },
  { id: 5, name: "錢七", nickname: "小錢", age: 24, photo: "/api/contestants/5/photo" }
];

const MOCK_RECOGNITION_RESULTS = [
  {
    confidence: 0.89,
    video_id: "1",
    contestant_id: "1",
    timestamp: 12.5,
    bounding_box: { x: 120, y: 80, width: 180, height: 240 }
  },
  {
    confidence: 0.92,
    video_id: "1", 
    contestant_id: "2",
    timestamp: 15.2,
    bounding_box: { x: 350, y: 90, width: 160, height: 220 }
  },
  {
    confidence: 0.78,
    video_id: "1",
    contestant_id: "3", 
    timestamp: 28.7,
    bounding_box: { x: 200, y: 150, width: 170, height: 230 }
  },
  {
    confidence: 0.85,
    video_id: "2",
    contestant_id: "1",
    timestamp: 45.3,
    bounding_box: { x: 180, y: 120, width: 175, height: 235 }
  },
  {
    confidence: 0.94,
    video_id: "2",
    contestant_id: "4",
    timestamp: 67.8,
    bounding_box: { x: 300, y: 100, width: 165, height: 225 }
  },
  {
    confidence: 0.81,
    video_id: "2",
    contestant_id: "5",
    timestamp: 89.1,
    bounding_box: { x: 150, y: 180, width: 185, height: 245 }
  },
  {
    confidence: 0.76,
    video_id: "3",
    contestant_id: "2",
    timestamp: 102.4,
    bounding_box: { x: 250, y: 140, width: 168, height: 228 }
  },
  {
    confidence: 0.88,
    video_id: "3",
    contestant_id: "3",
    timestamp: 125.9,
    bounding_box: { x: 320, y: 110, width: 172, height: 232 }
  },
  {
    confidence: 0.93,
    video_id: "4",
    contestant_id: "1",
    timestamp: 156.2,
    bounding_box: { x: 190, y: 95, width: 178, height: 238 }
  },
  {
    confidence: 0.79,
    video_id: "4", 
    contestant_id: "4",
    timestamp: 178.6,
    bounding_box: { x: 280, y: 160, width: 164, height: 224 }
  },
  {
    confidence: 0.86,
    video_id: "5",
    contestant_id: "2",
    timestamp: 201.3,
    bounding_box: { x: 210, y: 130, width: 174, height: 234 }
  },
  {
    confidence: 0.91,
    video_id: "5",
    contestant_id: "5", 
    timestamp: 223.7,
    bounding_box: { x: 340, y: 105, width: 169, height: 229 }
  },
  {
    confidence: 0.83,
    video_id: "1",
    contestant_id: "4",
    timestamp: 245.8,
    bounding_box: { x: 160, y: 175, width: 176, height: 236 }
  },
  {
    confidence: 0.77,
    video_id: "2",
    contestant_id: "3",
    timestamp: 268.4,
    bounding_box: { x: 290, y: 125, width: 166, height: 226 }
  },
  {
    confidence: 0.90,
    video_id: "3", 
    contestant_id: "1",
    timestamp: 291.1,
    bounding_box: { x: 230, y: 155, width: 180, height: 240 }
  },
  {
    confidence: 0.84,
    video_id: "5",
    contestant_id: "4",
    timestamp: 314.5,
    bounding_box: { x: 270, y: 115, width: 173, height: 233 }
  }
];

// CORS headers
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Max-Age': '86400',
};

// Embedded static assets (will be populated by build script)
const STATIC_ASSETS = {};

/**
 * Handle CORS preflight requests
 */
function handleCORS(request) {
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 200,
      headers: corsHeaders
    });
  }
  return null;
}

/**
 * Parse range header for video streaming
 */
function parseRange(range, totalSize) {
  if (!range) return null;
  
  const rangeMatch = range.match(/bytes=(\d+)-(\d*)/);
  if (!rangeMatch) return null;
  
  const start = parseInt(rangeMatch[1], 10);
  const end = rangeMatch[2] ? parseInt(rangeMatch[2], 10) : totalSize - 1;
  
  return { start, end };
}

/**
 * Handle video streaming with range requests
 */
async function handleVideoRequest(pathname, request, env, corsHeaders) {
  const videoKey = pathname.replace('/videos/', '');
  const range = request.headers.get('Range');
  
  if (env.VIDEOS_BUCKET) {
    try {
      if (range) {
        // Get object metadata first to determine size
        const object = await env.VIDEOS_BUCKET.head(videoKey);
        if (!object) {
          return new Response('Video not found', { status: 404, headers: corsHeaders });
        }
        
        const totalSize = object.size;
        const rangeInfo = parseRange(range, totalSize);
        
        if (rangeInfo) {
          const { start, end } = rangeInfo;
          const rangeHeader = `bytes=${start}-${end}`;
          
          const rangedObject = await env.VIDEOS_BUCKET.get(videoKey, {
            range: { offset: start, length: end - start + 1 }
          });
          
          if (rangedObject) {
            return new Response(rangedObject.body, {
              status: 206,
              headers: {
                ...corsHeaders,
                'Content-Range': `bytes ${start}-${end}/${totalSize}`,
                'Accept-Ranges': 'bytes',
                'Content-Length': (end - start + 1).toString(),
                'Content-Type': 'video/mp4',
                'Cache-Control': 'public, max-age=31536000'
              }
            });
          }
        }
      }
      
      // Fallback to full video
      const object = await env.VIDEOS_BUCKET.get(videoKey);
      if (object) {
        return new Response(object.body, {
          headers: {
            ...corsHeaders,
            'Content-Type': 'video/mp4',
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'public, max-age=31536000'
          }
        });
      }
    } catch (error) {
      console.error('Error serving video:', error);
    }
  }
  
  // Mock video response for development
  return new Response('Mock video content - configure R2 bucket for actual videos', {
    status: 200,
    headers: {
      ...corsHeaders,
      'Content-Type': 'video/mp4'
    }
  });
}

/**
 * Handle metadata requests
 */
async function handleMetadataRequest(pathname, request, env, corsHeaders) {
  const metadataKey = pathname.replace('/metadata/', '');
  
  if (env.METADATA_KV) {
    try {
      const metadata = await env.METADATA_KV.get(metadataKey);
      if (metadata) {
        return new Response(metadata, {
          headers: {
            ...corsHeaders,
            'Content-Type': 'application/json',
            'Cache-Control': 'public, max-age=3600'
          }
        });
      }
    } catch (error) {
      console.error('Error fetching metadata:', error);
    }
  }
  
  // Mock metadata response
  const mockMetadata = {
    video_info: {
      filename: metadataKey.replace('_metadata.json', '') + '.mp4',
      duration: 240.5,
      fps: 30,
      resolution: { width: 1920, height: 1080 }
    },
    timeline: [
      {
        frame_number: 0,
        timestamp: 0.0,
        contestants: []
      }
    ],
    processing_info: {
      processed_at: new Date().toISOString(),
      version: "1.0.0"
    }
  };
  
  return new Response(JSON.stringify(mockMetadata), {
    headers: {
      ...corsHeaders,
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=3600'
    }
  });
}

/**
 * Handle API requests
 */
async function handleAPIRequest(pathname, request, env, corsHeaders) {
  const segments = pathname.split('/').filter(Boolean);
  
  // Remove 'api' from segments
  segments.shift();
  
  switch (segments[0]) {
    case 'system':
      if (segments[1] === 'status') {
        return new Response(JSON.stringify({
          status: 'online',
          version: '1.0.0',
          timestamp: new Date().toISOString(),
          environment: env.ENVIRONMENT || 'development',
          features: {
            video_streaming: !!env.VIDEOS_BUCKET,
            metadata_storage: !!env.METADATA_KV,
            face_recognition: true,
            websocket: true
          }
        }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
      break;
      
    case 'videos':
      if (segments.length === 1) {
        // GET /api/videos - list all videos
        return new Response(JSON.stringify({
          videos: MOCK_VIDEOS,
          total: MOCK_VIDEOS.length
        }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      } else if (segments[1] === 'processed' && segments[2] === 'list') {
        // GET /api/videos/processed/list
        const processedVideos = MOCK_VIDEOS.filter(v => v.status === 'completed');
        return new Response(JSON.stringify({
          videos: processedVideos,
          total: processedVideos.length
        }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      } else if (segments[1] === 'metadata' && segments[2] === 'dense') {
        // GET /api/videos/metadata/dense/{video_id}
        const videoId = segments[3];
        return handleMetadataRequest(`video_${videoId}_dense_metadata.json`, request, env, corsHeaders);
      }
      break;
      
    case 'contestants':
      return new Response(JSON.stringify({
        contestants: MOCK_CONTESTANTS,
        total: MOCK_CONTESTANTS.length
      }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
      
    case 'recognition':
      if (segments[1] === 'results') {
        const url = new URL(request.url);
        const videoIdFilter = url.searchParams.get('video_id');
        const contestantIdFilter = url.searchParams.get('contestant_id');
        
        let filteredResults = [...MOCK_RECOGNITION_RESULTS];
        
        if (videoIdFilter) {
          filteredResults = filteredResults.filter(result => result.video_id === videoIdFilter);
        }
        
        if (contestantIdFilter) {
          filteredResults = filteredResults.filter(result => result.contestant_id === contestantIdFilter);
        }
        
        return new Response(JSON.stringify({
          results: filteredResults,
          total: filteredResults.length,
          filters: {
            video_id: videoIdFilter,
            contestant_id: contestantIdFilter
          }
        }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
      break;
      
    case 'settings':
      return new Response(JSON.stringify({
        theme: 'auto',
        language: 'zh-TW',
        processing: {
          confidence_threshold: 0.7,
          max_faces_per_frame: 10,
          enable_tracking: true
        },
        display: {
          show_confidence: true,
          show_bounding_boxes: true,
          overlay_opacity: 0.8
        }
      }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
      
    default:
      return new Response('API endpoint not found', {
        status: 404,
        headers: corsHeaders
      });
  }
  
  return new Response('API endpoint not implemented', {
    status: 501,
    headers: corsHeaders
  });
}

/**
 * Serve static assets
 */
function serveStaticAsset(pathname) {
  // Remove leading slash
  const assetPath = pathname.slice(1);
  
  if (STATIC_ASSETS[assetPath]) {
    const asset = STATIC_ASSETS[assetPath];
    
    // Determine content type
    let contentType = 'text/plain';
    if (assetPath.endsWith('.html')) contentType = 'text/html';
    else if (assetPath.endsWith('.js')) contentType = 'application/javascript';
    else if (assetPath.endsWith('.css')) contentType = 'text/css';
    else if (assetPath.endsWith('.json')) contentType = 'application/json';
    else if (assetPath.endsWith('.png')) contentType = 'image/png';
    else if (assetPath.endsWith('.jpg') || assetPath.endsWith('.jpeg')) contentType = 'image/jpeg';
    else if (assetPath.endsWith('.svg')) contentType = 'image/svg+xml';
    else if (assetPath.endsWith('.ico')) contentType = 'image/x-icon';
    
    return new Response(asset.content, {
      headers: {
        ...corsHeaders,
        'Content-Type': contentType,
        'Cache-Control': assetPath.includes('_app/') ? 'public, max-age=31536000, immutable' : 'public, max-age=3600'
      }
    });
  }
  
  return null;
}

/**
 * Main request handler
 */
export default {
  async fetch(request, env, ctx) {
    try {
      // Handle CORS preflight
      const corsResponse = handleCORS(request);
      if (corsResponse) return corsResponse;
      
      const url = new URL(request.url);
      const pathname = url.pathname;
      
      // API routes
      if (pathname.startsWith('/api/')) {
        return await handleAPIRequest(pathname, request, env, corsHeaders);
      }
      
      // Video streaming
      if (pathname.startsWith('/videos/')) {
        return await handleVideoRequest(pathname, request, env, corsHeaders);
      }
      
      // Metadata serving
      if (pathname.startsWith('/metadata/')) {
        return await handleMetadataRequest(pathname, request, env, corsHeaders);
      }
      
      // Static assets
      const staticResponse = serveStaticAsset(pathname);
      if (staticResponse) return staticResponse;
      
      // SPA fallback - serve index.html for all other routes
      const indexAsset = STATIC_ASSETS['index.html'];
      if (indexAsset) {
        return new Response(indexAsset.content, {
          headers: {
            ...corsHeaders,
            'Content-Type': 'text/html',
            'Cache-Control': 'public, max-age=3600'
          }
        });
      }
      
      // Fallback response when no static assets are embedded
      return new Response(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>MV Face Recognition</title>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body>
          <h1>MV Face Recognition API</h1>
          <p>Worker is running. Frontend assets need to be embedded.</p>
          <p>API Status: <a href="/api/system/status">/api/system/status</a></p>
          <p>Videos: <a href="/api/videos">/api/videos</a></p>
          <p>Contestants: <a href="/api/contestants">/api/contestants</a></p>
        </body>
        </html>
      `, {
        headers: {
          ...corsHeaders,
          'Content-Type': 'text/html'
        }
      });
      
    } catch (error) {
      console.error('Worker error:', error);
      return new Response('Internal Server Error', {
        status: 500,
        headers: corsHeaders
      });
    }
  }
};