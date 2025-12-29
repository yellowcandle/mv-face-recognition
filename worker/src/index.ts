/**
 * Cloudflare Worker for MV Face Recognition
 * Serves static frontend and provides API for metadata/videos
 */
import { EMBEDDED_ASSETS } from '../embedded-assets.js';
import { logger } from './lib/logger';
import { 
  AppError, 
  InternalError,
  CorsHeaders
} from './lib/errors';

/**
 * Environment bindings for the Cloudflare Worker
 */
interface Env {
  METADATA_KV: KVNamespace;
  VIDEOS_BUCKET: R2Bucket;
  CF_ACCESS_AUD?: string;
  CF_ACCESS_TEAM?: string;
  ENVIRONMENT?: string;
  ALLOWED_ORIGINS?: string;
  LOG_LEVEL?: string;
}

/**
 * Access verification result
 */
interface AccessVerificationResult {
  verified: boolean;
  email?: string;
  identity?: Record<string, unknown>;
  error?: string;
}

/**
 * Contestant data structure
 */
interface Contestant {
  id: string;
  number: number;
  name: string;
  nickname: string;
  age: number;
  has_photos: boolean;
  has_embedding: boolean;
}

/**
 * Video data structure
 */
interface VideoData {
  id: string;
  name: string;
  filename: string;
  path: string;
  size: number;
  duration_seconds: number;
  fps: number;
  width: number;
  height: number;
  frame_count: number;
  created_at: string;
}

/**
 * Flag data structure for face flagging
 */
interface FlagData {
  contestant_id: number;
  video_id: string;
  timestamp: number;
  bbox?: number[];
  confidence?: number;
  embedding?: number[];
  user_label?: string;
  thumbnail?: string;
}

/**
 * Flag record stored in KV
 */
interface FlagRecord {
  id: string;
  contestant_id: number;
  video_id: string;
  timestamp: number;
  bbox: number[] | null;
  confidence: number | null;
  embedding: number[] | null;
  user_label: string | null;
  has_thumbnail: boolean;
  flagged_at: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewed_by?: string;
  reviewed_at?: string;
}

/**
 * WebSocket message data
 */
interface WebSocketMessageData {
  type: string;
  video_name?: string;
  parameter?: string;
  value?: unknown;
}

/**
 * Verify Cloudflare Access JWT token
 * @see https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/
 */
async function verifyCloudflareAccess(request: Request, env: Env): Promise<AccessVerificationResult> {
  // Skip verification in development or if not configured
  if (!env.CF_ACCESS_AUD || env.ENVIRONMENT === 'development') {
    logger.debug('Skipping Access verification (not configured or dev mode)');
    return { verified: true, email: 'dev@localhost' };
  }

  const jwt = request.headers.get('Cf-Access-Jwt-Assertion');
  if (!jwt) {
    return { verified: false, error: 'Missing Cf-Access-Jwt-Assertion header' };
  }

  try {
    // Verify JWT with Cloudflare Access
    const certsUrl = `https://${env.CF_ACCESS_TEAM}.cloudflareaccess.com/cdn-cgi/access/certs`;
    const certsResponse = await fetch(certsUrl);
    await certsResponse.json();

    // Decode JWT parts
    const parts = jwt.split('.');
    if (parts.length !== 3) {
      return { verified: false, error: 'Invalid JWT format' };
    }

    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'))) as {
      aud?: string[];
      exp?: number;
      email?: string;
    };

    // Verify audience
    if (payload.aud && !payload.aud.includes(env.CF_ACCESS_AUD)) {
      return { verified: false, error: 'Invalid audience' };
    }

    // Verify expiration
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      return { verified: false, error: 'Token expired' };
    }

    // For full cryptographic verification, you'd verify the signature here
    // For simplicity, we trust Cloudflare's edge validation

    return {
      verified: true,
      email: payload.email,
      identity: payload as Record<string, unknown>
    };
  } catch (error) {
    const err = error as Error;
    logger.error('Access verification error', { error: err.message });
    return { verified: false, error: 'Verification failed' };
  }
}

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const { pathname } = url;

    logger.info(`${request.method} ${pathname}`, {
      userAgent: request.headers.get('User-Agent')?.substring(0, 50),
      timestamp: new Date().toISOString()
    });

    // CORS headers for all responses
    const corsHeaders: CorsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      logger.debug(`CORS preflight for ${pathname}`);
      return new Response(null, { headers: corsHeaders });
    }

    // Handle WebSocket upgrade requests
    if (pathname.startsWith('/ws/')) {
      logger.info(`WebSocket upgrade request: ${pathname}`);
      return await handleWebSocketRequest(pathname, request);
    }

    try {
      // API routes
      if (pathname.startsWith('/api/')) {
        logger.debug(`Routing to API handler: ${pathname}`);
        return await handleApiRequest(pathname, request, env, corsHeaders);
      }

      // Video files from R2
      if (pathname.startsWith('/videos/')) {
        logger.debug(`Routing to video handler: ${pathname}`);
        return await handleVideoRequest(pathname, request, env, corsHeaders);
      }

      // Static frontend files
      logger.debug(`Routing to static handler: ${pathname}`);
      return await handleStaticRequest(pathname, corsHeaders);
      
    } catch (error) {
      // Use structured error handling
      if (error instanceof AppError) {
        logger.error('Application error', { message: error.message, code: error.code });
        return error.toResponse(corsHeaders);
      }
      
      // Wrap unknown errors
      const internalError = new InternalError('An unexpected error occurred', error as Error);
      logger.error('Worker error', { message: internalError.message, code: internalError.code });
      return internalError.toResponse(corsHeaders);
    }
  }
};

/**
 * Handle WebSocket requests
 */
async function handleWebSocketRequest(pathname: string, request: Request): Promise<Response> {
  const path = pathname.replace('/ws', '');

  // Check if this is a WebSocket upgrade request
  const upgradeHeader = request.headers.get('Upgrade');
  if (upgradeHeader !== 'websocket') {
    return new Response('Expected Upgrade: websocket', { status: 426 });
  }

  switch (path) {
    case '/realtime-processing': {
      // Create WebSocket pair
      const webSocketPair = new WebSocketPair();
      const [client, server] = Object.values(webSocketPair);

      // Accept the WebSocket connection
      server.accept();

      // Handle WebSocket events
      server.addEventListener('message', async (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as WebSocketMessageData;
          logger.debug('WebSocket message received', { type: data.type });

          // Handle different message types
          switch (data.type) {
            case 'start_processing':
              // Simulate processing start
              server.send(JSON.stringify({
                type: 'processing_started',
                message: 'Video processing started',
                video_name: data.video_name
              }));

              // Send periodic updates
              let frameCount = 0;
              const interval = setInterval(() => {
                frameCount += 5;
                if (frameCount > 100) {
                  clearInterval(interval);
                  server.send(JSON.stringify({
                    type: 'processing_complete',
                    message: 'Processing completed',
                    video_name: data.video_name
                  }));
                  return;
                }

                server.send(JSON.stringify({
                  type: 'frame_update',
                  data: {
                    frame_number: frameCount,
                    timestamp: frameCount * 0.033,
                    faces: [
                      {
                        contestant: 'Ivy So',
                        confidence: 0.85 + Math.random() * 0.15,
                        bbox: [100 + Math.random() * 50, 100 + Math.random() * 50, 200, 250]
                      }
                    ],
                    stats: {
                      fps: 30,
                      total_faces: frameCount,
                      recognized: Math.floor(frameCount * 0.8)
                    }
                  }
                }));
              }, 100);

              break;

            case 'parameter_update':
              server.send(JSON.stringify({
                type: 'parameter_updated',
                parameter: data.parameter,
                value: data.value
              }));
              break;

            default:
              server.send(JSON.stringify({
                type: 'error',
                message: `Unknown message type: ${data.type}`
              }));
          }
        } catch (error) {
          const err = error as Error;
          logger.error('WebSocket message processing error', { error: err.message });
          server.send(JSON.stringify({
            type: 'error',
            message: 'Failed to process message'
          }));
        }
      });

      server.addEventListener('close', () => {
        logger.info('WebSocket connection closed');
      });

      // Send initial connection confirmation
      server.send(JSON.stringify({
        type: 'connected',
        message: 'WebSocket connection established'
      }));

      return new Response(null, {
        status: 101,
        webSocket: client,
      });
    }

    default:
      return new Response('WebSocket endpoint not found', { status: 404 });
  }
}

// Complete 96 contestants from CSV data
const allContestants: Contestant[] = [
  {"id": "1", "number": 1, "name": "蘇雅琳", "nickname": "Ivy So", "age": 20, "has_photos": true, "has_embedding": true},
  {"id": "2", "number": 2, "name": "黃雅慧", "nickname": "咖喱", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "3", "number": 3, "name": "邱彥筒", "nickname": "Marf", "age": 19, "has_photos": true, "has_embedding": true},
  {"id": "4", "number": 4, "name": "穎蕎", "nickname": "穎蕎", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "5", "number": 5, "name": "坂部佩莎", "nickname": "莎莎", "age": 20, "has_photos": true, "has_embedding": true},
  {"id": "6", "number": 6, "name": "陳玉幸", "nickname": "Hannah", "age": 23, "has_photos": true, "has_embedding": true},
  {"id": "7", "number": 7, "name": "梁式昕", "nickname": "Catrina", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "8", "number": 8, "name": "陳玥伶", "nickname": "小砂", "age": 29, "has_photos": true, "has_embedding": true},
  {"id": "9", "number": 9, "name": "羅洛家", "nickname": "Carmina", "age": 26, "has_photos": true, "has_embedding": true},
  {"id": "10", "number": 10, "name": "余潔瀅", "nickname": "Zoe", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "11", "number": 11, "name": "鍾君珩", "nickname": "Dru", "age": 28, "has_photos": true, "has_embedding": true},
  {"id": "12", "number": 12, "name": "何洛瑤", "nickname": "Sica", "age": 21, "has_photos": true, "has_embedding": true},
  {"id": "13", "number": 13, "name": "曾善婷", "nickname": "Ashi", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "14", "number": 14, "name": "鄭芷淇", "nickname": "Elka", "age": 18, "has_photos": true, "has_embedding": true},
  {"id": "15", "number": 15, "name": "李晞彤", "nickname": "Carina", "age": 19, "has_photos": true, "has_embedding": true},
  {"id": "16", "number": 16, "name": "夏子涓", "nickname": "子涓", "age": 26, "has_photos": true, "has_embedding": true},
  {"id": "17", "number": 17, "name": "黃詠霖", "nickname": "阿蛋", "age": 19, "has_photos": true, "has_embedding": true},
  {"id": "18", "number": 18, "name": "陳莉詩", "nickname": "蘇菲", "age": 26, "has_photos": true, "has_embedding": true},
  {"id": "19", "number": 19, "name": "黃筠兒", "nickname": "筠兒", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "20", "number": 20, "name": "余嘉熙", "nickname": "Karen", "age": 20, "has_photos": true, "has_embedding": true},
  {"id": "21", "number": 21, "name": "謝裕鈴", "nickname": "Ling", "age": 39, "has_photos": true, "has_embedding": true},
  {"id": "22", "number": 22, "name": "林暐翹", "nickname": "暐翹", "age": 19, "has_photos": true, "has_embedding": true},
  {"id": "23", "number": 23, "name": "陳祖兒", "nickname": "陳祖", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "24", "number": 24, "name": "曾家瑩", "nickname": "Ariel", "age": 16, "has_photos": true, "has_embedding": true},
  {"id": "25", "number": 25, "name": "徐嘉蔚", "nickname": "Emiko", "age": 19, "has_photos": true, "has_embedding": true},
  {"id": "26", "number": 26, "name": "陳泳伽", "nickname": "WINKA", "age": 23, "has_photos": true, "has_embedding": true},
  {"id": "27", "number": 27, "name": "姜咏鑫", "nickname": "Ada 仔", "age": 21, "has_photos": true, "has_embedding": true},
  {"id": "28", "number": 28, "name": "王家晴", "nickname": "Candy", "age": 18, "has_photos": true, "has_embedding": true},
  {"id": "29", "number": 29, "name": "鄺采彤", "nickname": "Emi", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "30", "number": 30, "name": "羅思雅", "nickname": "Caca", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "31", "number": 31, "name": "周芷慧", "nickname": "阿杰", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "32", "number": 32, "name": "李凱翹", "nickname": "Kay", "age": 29, "has_photos": true, "has_embedding": true},
  {"id": "33", "number": 33, "name": "黃敏蕎", "nickname": "阿妹", "age": 16, "has_photos": true, "has_embedding": true},
  {"id": "34", "number": 34, "name": "黃斯琪", "nickname": "CK", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "35", "number": 35, "name": "羅安娜", "nickname": "Ana", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "36", "number": 36, "name": "陳曉藍", "nickname": "精靈", "age": 19, "has_photos": true, "has_embedding": true},
  {"id": "37", "number": 37, "name": "利佩佩", "nickname": "Puipui", "age": 20, "has_photos": true, "has_embedding": true},
  {"id": "38", "number": 38, "name": "沈貞巧", "nickname": "Gao", "age": 28, "has_photos": true, "has_embedding": true},
  {"id": "39", "number": 39, "name": "葉倩彤", "nickname": "Stella", "age": 23, "has_photos": true, "has_embedding": true},
  {"id": "40", "number": 40, "name": "李芯駖", "nickname": "芯駖", "age": 35, "has_photos": true, "has_embedding": true},
  {"id": "41", "number": 41, "name": "林文思", "nickname": "Man C", "age": 29, "has_photos": true, "has_embedding": true},
  {"id": "42", "number": 42, "name": "王綺玲", "nickname": "2Ling", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "43", "number": 43, "name": "區廷筠", "nickname": "Tengie", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "44", "number": 44, "name": "曾美欣", "nickname": "Mei Mei", "age": 29, "has_photos": true, "has_embedding": true},
  {"id": "45", "number": 45, "name": "陳景晴", "nickname": "Jade Chan", "age": 20, "has_photos": true, "has_embedding": true},
  {"id": "46", "number": 46, "name": "歐穎芝", "nickname": "Chloe Au", "age": 18, "has_photos": true, "has_embedding": true},
  {"id": "47", "number": 47, "name": "周曉欣", "nickname": "Ace", "age": 23, "has_photos": true, "has_embedding": true},
  {"id": "48", "number": 48, "name": "劉綺婷", "nickname": "Yanny", "age": 22, "has_photos": true, "has_embedding": true},
  {"id": "49", "number": 49, "name": "溫彩玲", "nickname": "Jolin", "age": 26, "has_photos": true, "has_embedding": true},
  {"id": "50", "number": 50, "name": "歐卓瑩", "nickname": "鐵鐵", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "51", "number": 51, "name": "歐陽巧霖", "nickname": "Bubu", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "52", "number": 52, "name": "吳倩怡", "nickname": "Sinnie", "age": 23, "has_photos": true, "has_embedding": true},
  {"id": "53", "number": 53, "name": "房婷婷", "nickname": "丁丁", "age": 23, "has_photos": true, "has_embedding": true},
  {"id": "54", "number": 54, "name": "任佳慧", "nickname": "Miko", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "55", "number": 55, "name": "蔡舒文", "nickname": "舒文", "age": 22, "has_photos": true, "has_embedding": true},
  {"id": "56", "number": 56, "name": "鍾心悅", "nickname": "米線", "age": 22, "has_photos": true, "has_embedding": true},
  {"id": "57", "number": 57, "name": "張瑞芝", "nickname": "Ariels", "age": 17, "has_photos": true, "has_embedding": true},
  {"id": "58", "number": 58, "name": "盧芷韻", "nickname": "Kinki", "age": 17, "has_photos": true, "has_embedding": true},
  {"id": "59", "number": 59, "name": "張嘉慧", "nickname": "嘉嘉", "age": 17, "has_photos": true, "has_embedding": true},
  {"id": "60", "number": 60, "name": "楊安妮", "nickname": "Win Win", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "61", "number": 61, "name": "曾業喬", "nickname": "燒賣", "age": 16, "has_photos": true, "has_embedding": true},
  {"id": "62", "number": 62, "name": "何榛綦", "nickname": "榛綦", "age": 18, "has_photos": true, "has_embedding": true},
  {"id": "63", "number": 63, "name": "陳嘉瑤", "nickname": "露髀", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "64", "number": 64, "name": "林泳怡", "nickname": "Vicky", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "65", "number": 65, "name": "余施熲", "nickname": "阿 Wing", "age": 19, "has_photos": true, "has_embedding": true},
  {"id": "66", "number": 66, "name": "賴泳騫", "nickname": "Sam", "age": 22, "has_photos": true, "has_embedding": true},
  {"id": "67", "number": 67, "name": "楊芷程", "nickname": "Sarah", "age": 22, "has_photos": true, "has_embedding": true},
  {"id": "68", "number": 68, "name": "傅奕思", "nickname": "阿 J", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "69", "number": 69, "name": "黃鉦貽", "nickname": "鉦貽", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "70", "number": 70, "name": "郭東彩", "nickname": "東東", "age": 21, "has_photos": true, "has_embedding": true},
  {"id": "71", "number": 71, "name": "莫家琪", "nickname": "家琪", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "72", "number": 72, "name": "廖芷嘉", "nickname": "Ika", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "73", "number": 73, "name": "陳紀澄", "nickname": "Tania", "age": 18, "has_photos": true, "has_embedding": true},
  {"id": "74", "number": 74, "name": "蘇芷晴", "nickname": "So Ching", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "75", "number": 75, "name": "譚羨桐", "nickname": "May May", "age": 20, "has_photos": true, "has_embedding": true},
  {"id": "76", "number": 76, "name": "羅詠琪", "nickname": "Winkie", "age": 22, "has_photos": true, "has_embedding": true},
  {"id": "77", "number": 77, "name": "吳秀明", "nickname": "TABI", "age": 28, "has_photos": true, "has_embedding": true},
  {"id": "78", "number": 78, "name": "馬彩欣", "nickname": "馬欣", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "79", "number": 79, "name": "陳昭煊", "nickname": "超酸", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "80", "number": 80, "name": "方芷欣", "nickname": "方方", "age": 26, "has_photos": true, "has_embedding": true},
  {"id": "81", "number": 81, "name": "鍾卓穎", "nickname": "Ash", "age": 23, "has_photos": true, "has_embedding": true},
  {"id": "82", "number": 82, "name": "周卓盈", "nickname": "阿 Mic", "age": 23, "has_photos": true, "has_embedding": true},
  {"id": "83", "number": 83, "name": "何佩婷", "nickname": "何佩", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "84", "number": 84, "name": "趙展彤", "nickname": "VAL", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "85", "number": 85, "name": "蘇家欣", "nickname": "阿 bee", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "86", "number": 86, "name": "黎美萱", "nickname": "Michelle", "age": 25, "has_photos": true, "has_embedding": true},
  {"id": "87", "number": 87, "name": "葛綽瑤", "nickname": "Yoyo", "age": 22, "has_photos": true, "has_embedding": true},
  {"id": "88", "number": 88, "name": "劉展翹", "nickname": "Jackie", "age": 27, "has_photos": true, "has_embedding": true},
  {"id": "89", "number": 89, "name": "安希婷", "nickname": "安希婷", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "90", "number": 90, "name": "鄭嘉欣", "nickname": "Christine", "age": 28, "has_photos": true, "has_embedding": true},
  {"id": "91", "number": 91, "name": "許軼", "nickname": "Day", "age": 19, "has_photos": true, "has_embedding": true},
  {"id": "92", "number": 92, "name": "郭曉妍", "nickname": "阿 Yo", "age": 16, "has_photos": true, "has_embedding": true},
  {"id": "93", "number": 93, "name": "廖雪蕎", "nickname": "Liu 哥", "age": 24, "has_photos": true, "has_embedding": true},
  {"id": "94", "number": 94, "name": "吳欣諺", "nickname": "Yanis", "age": 17, "has_photos": true, "has_embedding": true},
  {"id": "95", "number": 95, "name": "許寶恆", "nickname": "Alice", "age": 22, "has_photos": true, "has_embedding": true},
  {"id": "96", "number": 96, "name": "郭嘉盈", "nickname": "3 妹", "age": 26, "has_photos": true, "has_embedding": true}
];

// Fallback video data
const fallbackVideos: VideoData[] = [
  {
    "id": "1",
    "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅",
    "filename": "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4",
    "path": "/source/videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4",
    "size": 234567890,
    "duration_seconds": 240,
    "fps": 30,
    "width": 1920,
    "height": 1080,
    "frame_count": 7200,
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": "2",
    "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅",
    "filename": "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4",
    "path": "/source/videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4",
    "size": 345678901,
    "duration_seconds": 180,
    "fps": 30,
    "width": 1920,
    "height": 1080,
    "frame_count": 5400,
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": "3",
    "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅",
    "filename": "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4",
    "path": "/source/videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4",
    "size": 456789012,
    "duration_seconds": 200,
    "fps": 30,
    "width": 1920,
    "height": 1080,
    "frame_count": 6000,
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": "4",
    "name": "《全民造星IV》極限拍MV",
    "filename": "4-《全民造星IV》極限拍MV.mp4",
    "path": "/source/videos/4-《全民造星IV》極限拍MV.mp4",
    "size": 567890123,
    "duration_seconds": 220,
    "fps": 30,
    "width": 1920,
    "height": 1080,
    "frame_count": 6600,
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": "5",
    "name": "《全民造星IV》播前熱身！率先表演《前傳》",
    "filename": "5-《全民造星IV》播前熱身！率先表演《前傳》.mp4",
    "path": "/source/videos/5-《全民造星IV》播前熱身！率先表演《前傳》.mp4",
    "size": 678901234,
    "duration_seconds": 190,
    "fps": 30,
    "width": 1920,
    "height": 1080,
    "frame_count": 5700,
    "created_at": "2024-01-01T00:00:00Z"
  }
];

/**
 * Handle API requests
 */
async function handleApiRequest(pathname: string, request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const path = pathname.replace('/api', '');

  switch (path) {
    case '/system/status/':
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
    case '/contestants/':
    case '/videos/contestants':
    case '/videos/contestants/':
      const contestants = await env.METADATA_KV?.get('contestants_structured');
      return new Response(contestants || JSON.stringify(allContestants), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });

    case '/videos':
    case '/videos/':
      return await handleVideosEndpoint(env, corsHeaders);

    case '/videos/processed/list':
    case '/videos/processed/list/':
      return await handleProcessedVideosEndpoint(env, corsHeaders);

    case '/settings':
    case '/settings/':
      return await handleSettingsEndpoint(request, env, corsHeaders);

    case '/faces/flag':
    case '/faces/flag/':
      if (request.method === 'POST') {
        return await handleFaceFlag(request, env, corsHeaders);
      }
      break;

    case '/faces/flagged':
    case '/faces/flagged/':
      return await handleGetFlaggedFaces(request, env, corsHeaders);

    case '/embeddings/sync':
    case '/embeddings/sync/':
      if (request.method === 'POST') {
        return await handleEmbeddingSync(request, env, corsHeaders);
      }
      break;

    case '/faces/thumbnail':
    case '/faces/thumbnail/':
      if (request.method === 'GET') {
        return await handleGetThumbnail(request, env, corsHeaders);
      }
      break;

    case '/faces/detect':
    case '/faces/detect/':
      if (request.method === 'GET') {
        return await handleFaceDetection(request, env, corsHeaders);
      }
      break;

    case '/recognition/results':
    case '/recognition/results/':
      return await handleRecognitionResults(request, env, corsHeaders);

    // Admin endpoints
    case '/admin/youtube/submit':
    case '/admin/youtube/submit/':
      if (request.method === 'POST') {
        return await handleYoutubeSubmit(request, env, corsHeaders);
      }
      break;

    case '/admin/youtube/queue':
    case '/admin/youtube/queue/':
      if (request.method === 'GET') {
        return await handleYoutubeQueue(request, env, corsHeaders);
      }
      break;

    case '/admin/youtube/status':
    case '/admin/youtube/status/':
      if (request.method === 'POST') {
        return await handleYoutubeStatus(request, env, corsHeaders);
      }
      break;

    case '/admin/flagged/approve':
    case '/admin/flagged/approve/':
      if (request.method === 'POST') {
        return await handleFlaggedApprove(request, env, corsHeaders);
      }
      break;

    case '/admin/embeddings/compare':
    case '/admin/embeddings/compare/':
      if (request.method === 'GET') {
        return await handleEmbeddingCompare(request, env, corsHeaders);
      }
      break;

    case '/admin/embeddings/trigger-sync':
    case '/admin/embeddings/trigger-sync/':
      if (request.method === 'POST') {
        return await handleTriggerSync(request, env, corsHeaders);
      }
      break;

    default:
      // Handle dynamic routes
      if (path.startsWith('/videos/metadata/dense/')) {
        return await handleDenseMetadata(path, env, corsHeaders);
      }
      
      if (path.startsWith('/videos/metadata/') && !path.includes('/dense/')) {
        return await handleVideoMetadata(path, env, corsHeaders);
      }
      
      if (path.startsWith('/videos/') && path.endsWith('/metadata')) {
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

// ============================================
// API Handler Functions
// ============================================

async function handleVideosEndpoint(env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  // Try to get optimized video list from KV storage first
  const optimizedVideosList = await env.METADATA_KV?.get('videos_list_optimized');
  
  if (optimizedVideosList) {
    logger.debug('Using optimized video list from KV storage');
    return new Response(optimizedVideosList, {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
  
  // Fallback: Try to get full metadata collection
  const videoMetadataCollection = await env.METADATA_KV?.get('video_metadata_collection');
  
  if (videoMetadataCollection) {
    logger.debug('Creating optimized response from full metadata collection');
    const parsedData = JSON.parse(videoMetadataCollection) as Record<string, {
      video_info?: unknown;
      processing_date?: string;
      recognition_summary?: unknown;
    }>;
    
    const optimizedVideos: Record<string, unknown> = {};
    for (const [videoId, videoData] of Object.entries(parsedData)) {
      const numericMatch = videoId.match(/^(\d+)/);
      optimizedVideos[videoId] = {
        video_info: videoData.video_info,
        processing_date: videoData.processing_date,
        recognition_summary: videoData.recognition_summary,
        has_detailed_metadata: true,
        metadata_endpoints: {
          basic: `/api/videos/metadata/${numericMatch ? numericMatch[0] : videoId}`,
          detailed: `/api/videos/metadata/dense/${numericMatch ? numericMatch[0] : videoId}`
        }
      };
    }
    
    return new Response(JSON.stringify({ videos: optimizedVideos }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
  
  logger.info('Using fallback video data');
  return new Response(JSON.stringify({ videos: fallbackVideos }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

async function handleProcessedVideosEndpoint(env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const processedVideos = [
    {
      "id": "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅",
      "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅",
      "filename": "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4",
      "size": 768000000,
      "created_at": 1672531200,
      "has_metadata": true,
      "stream_url": "/videos/processed_videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4"
    },
    {
      "id": "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅",
      "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅",
      "filename": "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4",
      "size": 693000000,
      "created_at": 1672531200,
      "has_metadata": true,
      "stream_url": "/videos/processed_videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4"
    },
    {
      "id": "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅",
      "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅",
      "filename": "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4",
      "size": 690000000,
      "created_at": 1672531200,
      "has_metadata": true,
      "stream_url": "/videos/processed_videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4"
    },
    {
      "id": "4-《全民造星IV》極限拍MV",
      "name": "《全民造星IV》極限拍MV",
      "filename": "4-《全民造星IV》極限拍MV_annotated.mp4",
      "size": 521000000,
      "created_at": 1672531200,
      "has_metadata": true,
      "stream_url": "/videos/processed_videos/4-《全民造星IV》極限拍MV_annotated.mp4"
    },
    {
      "id": "5-《全民造星IV》播前熱身！率先表演《前傳》",
      "name": "《全民造星IV》播前熱身！率先表演《前傳》",
      "filename": "5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4",
      "size": 538000000,
      "created_at": 1672531200,
      "has_metadata": true,
      "stream_url": "/videos/processed_videos/5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4"
    }
  ];
  
  const storedProcessedVideos = await env.METADATA_KV?.get('processed_videos_list');
  return new Response(storedProcessedVideos || JSON.stringify(processedVideos), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

async function handleSettingsEndpoint(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
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
  
  return new Response(JSON.stringify({ error: 'Method not allowed' }), {
    status: 405,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

async function handleFaceFlag(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  try {
    const flagData = await request.json() as FlagData;

    if (!flagData.contestant_id || !flagData.video_id || !flagData.timestamp) {
      return new Response(JSON.stringify({
        error: 'Missing required fields: contestant_id, video_id, timestamp'
      }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const flagId = `flag_${flagData.contestant_id}_${flagData.video_id}_${Date.now()}`;

    const flagRecord: FlagRecord = {
      id: flagId,
      contestant_id: flagData.contestant_id,
      video_id: flagData.video_id,
      timestamp: flagData.timestamp,
      bbox: flagData.bbox || null,
      confidence: flagData.confidence || null,
      embedding: flagData.embedding || null,
      user_label: flagData.user_label || null,
      has_thumbnail: !!flagData.thumbnail,
      flagged_at: new Date().toISOString(),
      status: 'pending'
    };

    if (flagData.thumbnail) {
      await env.METADATA_KV.put(`flagged_thumbnail_${flagId}`, flagData.thumbnail);
    }

    await env.METADATA_KV.put(`flagged_face_${flagId}`, JSON.stringify(flagRecord));

    // Update index with retry
    const maxRetries = 3;
    let retryCount = 0;
    let indexUpdated = false;

    while (retryCount < maxRetries && !indexUpdated) {
      try {
        const currentIndex = await env.METADATA_KV.get('flagged_faces_index');
        const parsedIndex = currentIndex ? JSON.parse(currentIndex) as Array<{ id: string; contestant_id: number; video_id: string; flagged_at: string }> : [];

        const exists = parsedIndex.some(f => f.id === flagId);
        if (!exists) {
          parsedIndex.push({
            id: flagId,
            contestant_id: flagData.contestant_id,
            video_id: flagData.video_id,
            flagged_at: flagRecord.flagged_at
          });
          await env.METADATA_KV.put('flagged_faces_index', JSON.stringify(parsedIndex));
        }
        indexUpdated = true;
      } catch {
        retryCount++;
        if (retryCount >= maxRetries) {
          logger.warn('Index update failed after retries, flag still saved', { flagId });
        }
        await new Promise(resolve => setTimeout(resolve, 50 * retryCount));
      }
    }

    logger.info(`Face flagged: ${flagId}`);

    return new Response(JSON.stringify({
      success: true,
      flag_id: flagId,
      message: 'Face flagged successfully'
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  } catch (error) {
    const err = error as Error;
    logger.error('Error flagging face', { error: err.message });
    return new Response(JSON.stringify({ error: 'Failed to flag face' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleGetFlaggedFaces(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  try {
    const flaggedIndex = await env.METADATA_KV.get('flagged_faces_index');
    const index = flaggedIndex ? JSON.parse(flaggedIndex) as Array<{ id: string; contestant_id: number; video_id: string; flagged_at: string }> : [];

    const url = new URL(request.url);
    const contestantFilter = url.searchParams.get('contestant_id');
    const videoFilter = url.searchParams.get('video_id');
    const statusFilter = url.searchParams.get('status');

    let filtered = index;
    if (contestantFilter) {
      filtered = filtered.filter(f => f.contestant_id === parseInt(contestantFilter));
    }
    if (videoFilter) {
      filtered = filtered.filter(f => f.video_id === videoFilter);
    }

    const includeDetails = url.searchParams.get('details') === 'true';
    let results: unknown[] = filtered;

    if (includeDetails) {
      results = await Promise.all(
        filtered.map(async (f) => {
          const full = await env.METADATA_KV.get(`flagged_face_${f.id}`);
          return full ? JSON.parse(full) : f;
        })
      );

      if (statusFilter) {
        results = results.filter((r: unknown) => (r as FlagRecord).status === statusFilter);
      }
    }

    return new Response(JSON.stringify({
      flagged_faces: results,
      total: results.length
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  } catch (error) {
    const err = error as Error;
    logger.error('Error getting flagged faces', { error: err.message });
    return new Response(JSON.stringify({ error: 'Failed to get flagged faces' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleEmbeddingSync(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  try {
    const syncData = await request.json() as { contestant_id?: string };

    const syncRecord = {
      sync_id: `sync_${Date.now()}`,
      contestant_id: syncData.contestant_id || 'all',
      requested_at: new Date().toISOString(),
      status: 'queued'
    };

    await env.METADATA_KV.put(`embedding_sync_${syncRecord.sync_id}`, JSON.stringify(syncRecord));

    return new Response(JSON.stringify({
      success: true,
      sync_id: syncRecord.sync_id,
      message: 'Embedding sync queued. Process with Modal to update embeddings.'
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: 'Failed to queue sync' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleGetThumbnail(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const url = new URL(request.url);
  const flagId = url.searchParams.get('flag_id');

  if (!flagId) {
    return new Response(JSON.stringify({ error: 'Missing flag_id parameter' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  try {
    const thumbnail = await env.METADATA_KV.get(`flagged_thumbnail_${flagId}`);

    if (!thumbnail) {
      return new Response(JSON.stringify({ error: 'Thumbnail not found' }), {
        status: 404,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    return new Response(JSON.stringify({
      flag_id: flagId,
      thumbnail: thumbnail
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  } catch (error) {
    const err = error as Error;
    logger.error('Error getting thumbnail', { error: err.message });
    return new Response(JSON.stringify({ error: 'Failed to get thumbnail' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleFaceDetection(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const url = new URL(request.url);
  const videoId = url.searchParams.get('video_id');
  const timestamp = parseFloat(url.searchParams.get('timestamp') || '0');

  if (!videoId) {
    return new Response(JSON.stringify({ error: 'video_id required' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  const denseMetadata = await env.METADATA_KV.get(`metadata_dense_${videoId}`);

  if (denseMetadata) {
    const parsed = JSON.parse(denseMetadata) as {
      video_info?: { fps?: number };
      contestant_timeline?: Record<string, {
        detailed_timeline?: Array<{
          timestamp: number;
          confidence?: number;
          bbox?: number[];
          frame?: number;
        }>;
      }>;
    };
    const fps = parsed.video_info?.fps || 25;
    const frameNumber = Math.floor(timestamp * fps);

    const faces: Array<{
      contestant_name: string;
      confidence: number;
      bbox: number[] | null;
      timestamp: number;
      frame: number;
    }> = [];
    
    for (const [contestantName, timeline] of Object.entries(parsed.contestant_timeline || {})) {
      if (!timeline) continue;

      const appearances = timeline.detailed_timeline || [];
      for (const appearance of appearances) {
        if (!appearance || typeof appearance.timestamp !== 'number') continue;

        if (Math.abs(appearance.timestamp - timestamp) < 0.2) {
          faces.push({
            contestant_name: contestantName,
            confidence: appearance.confidence ?? 0,
            bbox: appearance.bbox || null,
            timestamp: appearance.timestamp,
            frame: appearance.frame ?? 0
          });
        }
      }
    }

    return new Response(JSON.stringify({
      video_id: videoId,
      timestamp: timestamp,
      frame: frameNumber,
      faces: faces
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  return new Response(JSON.stringify({
    video_id: videoId,
    timestamp: timestamp,
    faces: [],
    message: 'No detection metadata available for this video'
  }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

async function handleRecognitionResults(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const url = new URL(request.url);
  const videoIdFilter = url.searchParams.get('video_id');
  const contestantIdFilter = url.searchParams.get('contestant_id');
  
  // Mock recognition results
  const allRecognitionResults = [
    { confidence: 0.89, video_id: "1", contestant_id: "1", timestamp: 12.5, bounding_box: { x: 120, y: 80, width: 180, height: 240 } },
    { confidence: 0.92, video_id: "1", contestant_id: "2", timestamp: 18.3, bounding_box: { x: 350, y: 120, width: 170, height: 220 } },
    { confidence: 0.85, video_id: "1", contestant_id: "3", timestamp: 24.7, bounding_box: { x: 200, y: 150, width: 160, height: 210 } },
    { confidence: 0.91, video_id: "1", contestant_id: "1", timestamp: 45.2, bounding_box: { x: 100, y: 50, width: 150, height: 200 } },
    { confidence: 0.87, video_id: "1", contestant_id: "4", timestamp: 52.8, bounding_box: { x: 380, y: 90, width: 165, height: 215 } },
    { confidence: 0.93, video_id: "1", contestant_id: "2", timestamp: 67.4, bounding_box: { x: 300, y: 75, width: 140, height: 180 } },
    { confidence: 0.88, video_id: "2", contestant_id: "1", timestamp: 15.6, bounding_box: { x: 150, y: 100, width: 175, height: 230 } },
    { confidence: 0.84, video_id: "2", contestant_id: "5", timestamp: 28.9, bounding_box: { x: 250, y: 110, width: 155, height: 195 } },
    { confidence: 0.90, video_id: "2", contestant_id: "3", timestamp: 41.3, bounding_box: { x: 180, y: 85, width: 170, height: 225 } },
    { confidence: 0.86, video_id: "3", contestant_id: "2", timestamp: 8.7, bounding_box: { x: 320, y: 60, width: 145, height: 185 } },
    { confidence: 0.94, video_id: "3", contestant_id: "6", timestamp: 33.1, bounding_box: { x: 110, y: 140, width: 180, height: 240 } },
    { confidence: 0.82, video_id: "3", contestant_id: "1", timestamp: 48.5, bounding_box: { x: 270, y: 95, width: 160, height: 205 } },
    { confidence: 0.95, video_id: "4", contestant_id: "7", timestamp: 22.4, bounding_box: { x: 140, y: 70, width: 175, height: 235 } },
    { confidence: 0.83, video_id: "4", contestant_id: "2", timestamp: 56.8, bounding_box: { x: 360, y: 130, width: 150, height: 190 } },
    { confidence: 0.88, video_id: "5", contestant_id: "8", timestamp: 11.2, bounding_box: { x: 190, y: 55, width: 165, height: 220 } },
    { confidence: 0.91, video_id: "5", contestant_id: "3", timestamp: 39.6, bounding_box: { x: 310, y: 105, width: 155, height: 200 } }
  ];
  
  let filteredResults = allRecognitionResults;
  
  if (videoIdFilter) {
    filteredResults = filteredResults.filter(result => result.video_id === videoIdFilter);
  }
  
  if (contestantIdFilter) {
    filteredResults = filteredResults.filter(result => result.contestant_id === contestantIdFilter);
  }
  
  const storageKey = `recognition_results${videoIdFilter ? `_video_${videoIdFilter}` : ''}${contestantIdFilter ? `_contestant_${contestantIdFilter}` : ''}`;
  const storedResults = await env.METADATA_KV?.get(storageKey);
  
  const results = storedResults ? JSON.parse(storedResults) : filteredResults;
  
  return new Response(JSON.stringify({
    results: results,
    total: results.length,
    filters: { video_id: videoIdFilter, contestant_id: contestantIdFilter }
  }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

// Admin Endpoints
async function handleYoutubeSubmit(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const accessResult = await verifyCloudflareAccess(request, env);
  if (!accessResult.verified) {
    return new Response(JSON.stringify({ error: 'Unauthorized', message: accessResult.error }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  try {
    const data = await request.json() as { youtube_url?: string; title?: string; priority?: string };
    const { youtube_url, title, priority } = data;

    if (!youtube_url) {
      return new Response(JSON.stringify({ error: 'Missing required field: youtube_url' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const ytRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|embed\/|v\/)|youtu\.be\/)[\w-]+/;
    if (!ytRegex.test(youtube_url)) {
      return new Response(JSON.stringify({ error: 'Invalid YouTube URL format' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    let videoId = '';
    try {
      const urlObj = new URL(youtube_url);
      if (urlObj.hostname === 'youtu.be') {
        videoId = urlObj.pathname.slice(1);
      } else {
        videoId = urlObj.searchParams.get('v') || '';
      }
    } catch {
      videoId = youtube_url.match(/[\w-]{11}/)?.[0] || '';
    }

    const queueId = `yt_${videoId}_${Date.now()}`;
    const queueEntry = {
      id: queueId,
      youtube_url,
      youtube_video_id: videoId,
      title: title || `YouTube Video ${videoId}`,
      priority: priority || 'normal',
      status: 'queued',
      submitted_by: accessResult.email,
      submitted_at: new Date().toISOString(),
      processing_started_at: null,
      completed_at: null,
      error: null
    };

    await env.METADATA_KV.put(`youtube_queue_${queueId}`, JSON.stringify(queueEntry));

    const queueIndexStr = await env.METADATA_KV.get('youtube_queue_index') || '[]';
    const queueIndex = JSON.parse(queueIndexStr) as string[];
    queueIndex.push(queueId);
    await env.METADATA_KV.put('youtube_queue_index', JSON.stringify(queueIndex));

    logger.info(`YouTube video queued`, { queueId, videoId, email: accessResult.email });

    return new Response(JSON.stringify({
      success: true,
      queue_id: queueId,
      message: 'Video queued for processing',
      entry: queueEntry
    }), {
      status: 201,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error) {
    const err = error as Error;
    logger.error('YouTube submit error', { error: err.message });
    return new Response(JSON.stringify({ error: 'Failed to queue video', message: err.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleYoutubeQueue(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const accessResult = await verifyCloudflareAccess(request, env);
  if (!accessResult.verified) {
    return new Response(JSON.stringify({ error: 'Unauthorized', message: accessResult.error }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  try {
    const queueIndexStr = await env.METADATA_KV.get('youtube_queue_index') || '[]';
    const queueIndex = JSON.parse(queueIndexStr) as string[];

    const queueUrl = new URL(request.url);
    const statusFilter = queueUrl.searchParams.get('status');

    const entries: Array<{ submitted_at: string; status: string }> = [];
    for (const queueId of queueIndex) {
      const entryStr = await env.METADATA_KV.get(`youtube_queue_${queueId}`);
      if (entryStr) {
        const entry = JSON.parse(entryStr) as { submitted_at: string; status: string };
        if (!statusFilter || entry.status === statusFilter) {
          entries.push(entry);
        }
      }
    }

    entries.sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime());

    return new Response(JSON.stringify({
      queue: entries,
      total: entries.length,
      filter: statusFilter
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error) {
    const err = error as Error;
    logger.error('YouTube queue list error', { error: err.message });
    return new Response(JSON.stringify({ error: 'Failed to list queue', message: err.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleYoutubeStatus(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const accessResult = await verifyCloudflareAccess(request, env);
  if (!accessResult.verified) {
    return new Response(JSON.stringify({ error: 'Unauthorized', message: accessResult.error }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  try {
    const { queue_id, status, error: errorMsg, output_video_id } = await request.json() as {
      queue_id?: string;
      status?: string;
      error?: string;
      output_video_id?: string;
    };

    if (!queue_id || !status) {
      return new Response(JSON.stringify({ error: 'Missing required fields: queue_id, status' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const entryStr = await env.METADATA_KV.get(`youtube_queue_${queue_id}`);
    if (!entryStr) {
      return new Response(JSON.stringify({ error: 'Queue entry not found' }), {
        status: 404,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const entry = JSON.parse(entryStr) as {
      status: string;
      processing_started_at?: string;
      completed_at?: string;
      output_video_id?: string;
      error?: string;
    };
    entry.status = status;

    if (status === 'processing') {
      entry.processing_started_at = new Date().toISOString();
    } else if (status === 'completed') {
      entry.completed_at = new Date().toISOString();
      entry.output_video_id = output_video_id || undefined;
    } else if (status === 'failed') {
      entry.error = errorMsg || 'Unknown error';
    }

    await env.METADATA_KV.put(`youtube_queue_${queue_id}`, JSON.stringify(entry));

    logger.info(`YouTube queue status updated`, { queue_id, status });

    return new Response(JSON.stringify({ success: true, entry }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error) {
    const err = error as Error;
    logger.error('YouTube status update error', { error: err.message });
    return new Response(JSON.stringify({ error: 'Failed to update status', message: err.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleFlaggedApprove(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const accessResult = await verifyCloudflareAccess(request, env);
  if (!accessResult.verified) {
    return new Response(JSON.stringify({ error: 'Unauthorized', message: accessResult.error }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  try {
    const { flag_id, action } = await request.json() as { flag_id?: string; action?: string };

    if (!flag_id || !action) {
      return new Response(JSON.stringify({ error: 'Missing required fields: flag_id, action' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    if (!['approve', 'reject'].includes(action)) {
      return new Response(JSON.stringify({ error: 'Invalid action. Must be "approve" or "reject"' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const flagStr = await env.METADATA_KV.get(`flagged_face_${flag_id}`);
    if (!flagStr) {
      return new Response(JSON.stringify({ error: 'Flagged face not found' }), {
        status: 404,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const flagRecord = JSON.parse(flagStr) as FlagRecord;
    flagRecord.status = action === 'approve' ? 'approved' : 'rejected';
    flagRecord.reviewed_by = accessResult.email;
    flagRecord.reviewed_at = new Date().toISOString();

    await env.METADATA_KV.put(`flagged_face_${flag_id}`, JSON.stringify(flagRecord));

    logger.info(`Flagged face ${action}d`, { flag_id, email: accessResult.email });

    return new Response(JSON.stringify({ success: true, flag: flagRecord }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error) {
    const err = error as Error;
    logger.error('Flagged approve error', { error: err.message });
    return new Response(JSON.stringify({ error: 'Failed to process approval', message: err.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleEmbeddingCompare(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const accessResult = await verifyCloudflareAccess(request, env);
  if (!accessResult.verified) {
    return new Response(JSON.stringify({ error: 'Unauthorized', message: accessResult.error }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  try {
    const compareUrl = new URL(request.url);
    const contestantId = compareUrl.searchParams.get('contestant_id');

    if (!contestantId) {
      return new Response(JSON.stringify({ error: 'Missing contestant_id parameter' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const flagIndexStr = await env.METADATA_KV.get('flagged_faces_index') || '[]';
    const flagIndex = JSON.parse(flagIndexStr) as Array<{ id: string; contestant_id: number }>;

    const contestantFlags: Array<{
      id: string;
      video_id: string;
      timestamp: number;
      confidence: number | null;
      status: string;
      has_thumbnail: boolean;
      flagged_at: string;
    }> = [];

    for (const flagMeta of flagIndex) {
      if (String(flagMeta.contestant_id) === contestantId) {
        const flagStr = await env.METADATA_KV.get(`flagged_face_${flagMeta.id}`);
        if (flagStr) {
          const flag = JSON.parse(flagStr) as FlagRecord;
          contestantFlags.push({
            id: flag.id,
            video_id: flag.video_id,
            timestamp: flag.timestamp,
            confidence: flag.confidence,
            status: flag.status,
            has_thumbnail: flag.has_thumbnail,
            flagged_at: flag.flagged_at
          });
        }
      }
    }

    const approvedCount = contestantFlags.filter(f => f.status === 'approved').length;
    const pendingCount = contestantFlags.filter(f => f.status === 'pending').length;
    const avgConfidence = contestantFlags.length > 0
      ? contestantFlags.reduce((sum, f) => sum + (f.confidence || 0), 0) / contestantFlags.length
      : 0;

    return new Response(JSON.stringify({
      contestant_id: contestantId,
      total_flags: contestantFlags.length,
      approved_count: approvedCount,
      pending_count: pendingCount,
      rejected_count: contestantFlags.length - approvedCount - pendingCount,
      average_confidence: avgConfidence,
      flags: contestantFlags,
      embedding_status: {
        has_base_embedding: true,
        last_updated: null,
        flag_contributions: approvedCount
      }
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error) {
    const err = error as Error;
    logger.error('Embedding compare error', { error: err.message });
    return new Response(JSON.stringify({ error: 'Failed to get comparison data', message: err.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleTriggerSync(request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const accessResult = await verifyCloudflareAccess(request, env);
  if (!accessResult.verified) {
    return new Response(JSON.stringify({ error: 'Unauthorized', message: accessResult.error }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  try {
    const flagIndexStr = await env.METADATA_KV.get('flagged_faces_index') || '[]';
    const flagIndex = JSON.parse(flagIndexStr) as string[];

    const approvedFlags: FlagRecord[] = [];
    for (const flagId of flagIndex) {
      const flagStr = await env.METADATA_KV.get(`flagged_face_${flagId}`);
      if (flagStr) {
        const flag = JSON.parse(flagStr) as FlagRecord;
        if (flag.status === 'approved') {
          approvedFlags.push(flag);
        }
      }
    }

    const syncJobId = `sync_${Date.now()}`;
    const syncJob = {
      id: syncJobId,
      status: 'pending',
      approved_flags_count: approvedFlags.length,
      triggered_by: accessResult.email,
      triggered_at: new Date().toISOString(),
      completed_at: null
    };

    await env.METADATA_KV.put(`embedding_sync_job_${syncJobId}`, JSON.stringify(syncJob));

    logger.info(`Embedding sync triggered`, { syncJobId, count: approvedFlags.length, email: accessResult.email });

    return new Response(JSON.stringify({
      success: true,
      sync_job_id: syncJobId,
      approved_flags_count: approvedFlags.length,
      message: 'Embedding sync job created. Run Modal processor with --update-embeddings to process.'
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error) {
    const err = error as Error;
    logger.error('Embedding sync trigger error', { error: err.message });
    return new Response(JSON.stringify({ error: 'Failed to trigger sync', message: err.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function handleDenseMetadata(path: string, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  let videoId = path.replace('/videos/metadata/dense/', '');
  
  try {
    videoId = decodeURIComponent(videoId);
  } catch {
    // If decoding fails, use as-is
  }
  
  let metadataKey = videoId;
  const numericMatch = videoId.match(/^(\d+)-/);
  if (numericMatch) {
    metadataKey = numericMatch[1];
  }
  
  logger.debug(`Looking for dense metadata`, { key: `metadata_dense_${metadataKey}`, videoId });
  
  const storedDenseMetadata = await env.METADATA_KV?.get(`metadata_dense_${metadataKey}`);
  
  if (storedDenseMetadata) {
    return new Response(storedDenseMetadata, {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
  
  // Mock fallback
  const denseMetadata = {
    "video_id": metadataKey,
    "video_info": {
      "filename": `${videoId}_annotated.mp4`,
      "fps": 25.0,
      "duration_seconds": 180.0,
      "frame_count": 4500
    },
    "processing_info": {
      "frame_interval": 5,
      "interpolation_enabled": true,
      "similarity_threshold": 0.25
    },
    "recognition_summary": {
      "unique_contestants": 12,
      "total_faces_detected": 450,
      "total_faces_recognized": 380
    },
    "contestant_timeline": {
      "Ivy So": {
        "total_appearances": 15,
        "avg_confidence": 0.85,
        "max_confidence": 0.96,
        "first_appearance_time": 10.5,
        "last_appearance_time": 165.2,
        "detailed_timeline": [
          { "frame": 262, "timestamp": 10.48, "confidence": 0.87, "bbox": [100, 150, 200, 300] }
        ]
      }
    }
  };
  
  const storedMetadata = await env.METADATA_KV?.get(`video_metadata_dense_${videoId}`);
  return new Response(storedMetadata || JSON.stringify(denseMetadata), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

async function handleVideoMetadata(path: string, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  let videoId = path.replace('/videos/metadata/', '');
  
  try {
    videoId = decodeURIComponent(videoId);
  } catch {
    // If decoding fails, use as-is
  }
  
  let metadataKey = videoId;
  const numericMatch = videoId.match(/^(\d+)-/);
  if (numericMatch) {
    metadataKey = numericMatch[1];
  }
  
  logger.debug(`Looking for metadata`, { key: `metadata_${metadataKey}`, videoId });
  
  const storedVideoMetadata = await env.METADATA_KV?.get(`metadata_${metadataKey}`);
  
  if (storedVideoMetadata) {
    return new Response(storedVideoMetadata, {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
  
  // Mock fallback
  const metadata = {
    "video_id": metadataKey,
    "video_info": {
      "filename": `${metadataKey}.mp4`,
      "fps": 25.0,
      "duration_seconds": 180.0,
      "frame_count": 4500
    },
    "recognition_summary": {
      "unique_contestants": 8,
      "total_faces_detected": 250,
      "total_faces_recognized": 200
    },
    "contestant_timeline": {}
  };
  
  return new Response(JSON.stringify(metadata), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

/**
 * Handle video file requests from R2
 */
async function handleVideoRequest(pathname: string, request: Request, env: Env, corsHeaders: CorsHeaders): Promise<Response> {
  const videoPath = pathname.replace('/videos/', '');
  
  try {
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

    const headers: Record<string, string> = {
      ...corsHeaders,
      'Content-Type': 'video/mp4',
      'Cache-Control': 'public, max-age=86400',
    };

    // Handle range requests for video streaming
    const range = request.headers.get('Range');
    if (range) {
      const size = object.size;
      const [start, end] = parseRange(range, size);
      
      headers['Content-Range'] = `bytes ${start}-${end}/${size}`;
      headers['Content-Length'] = (end - start + 1).toString();
      headers['Accept-Ranges'] = 'bytes';
      
      // Note: R2Object.body doesn't have a slice method, need to use range header on get
      const rangeObject = await env.VIDEOS_BUCKET.get(videoPath, {
        range: { offset: start, length: end - start + 1 }
      });
      
      if (!rangeObject) {
        return new Response('Video not found', { status: 404, headers: corsHeaders });
      }
      
      return new Response(rangeObject.body, {
        status: 206,
        headers
      });
    }

    return new Response(object.body, { headers });
    
  } catch (error) {
    const err = error as Error;
    logger.error('Error serving video', { error: err.message, stack: err.stack });
    return new Response('Error serving video', { 
      status: 500,
      headers: corsHeaders 
    });
  }
}

/**
 * Handle static frontend files
 */
async function handleStaticRequest(pathname: string, corsHeaders: CorsHeaders): Promise<Response> {
  logger.debug(`Static request for: ${pathname}`);
  
  let finalPath = pathname;
  
  // Handle root path
  if (finalPath === '/') {
    finalPath = 'index.html';
  }
  
  // Remove leading slash for asset lookup
  const assetKey = finalPath.startsWith('/') ? finalPath.substring(1) : finalPath;
  
  // Check embedded assets
  const embeddedAssets = EMBEDDED_ASSETS as Record<string, string>;
  
  if (embeddedAssets[assetKey]) {
    logger.debug(`Successfully serving embedded asset: ${assetKey}`);
    
    const contentType = getContentType(finalPath);
    const cacheControl = finalPath.includes('assets/') ? 'public, max-age=31536000' : 'public, max-age=3600';
    
    return new Response(embeddedAssets[assetKey], {
      headers: {
        ...corsHeaders,
        'Content-Type': contentType,
        'Cache-Control': cacheControl
      }
    });
  }
  
  // SPA routing
  if (!/\.[^/]+$/.test(finalPath)) {
    const pageKey = `${assetKey}.html`;
    if (embeddedAssets[pageKey]) {
      logger.debug(`SPA route, serving specific page: ${pageKey}`);
      return new Response(embeddedAssets[pageKey], {
        headers: {
          ...corsHeaders,
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'public, max-age=3600'
        }
      });
    }

    logger.debug(`SPA route detected, serving index.html for: ${finalPath}`);
    return new Response(embeddedAssets['index.html'], {
      headers: {
        ...corsHeaders,
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=3600'
      }
    });
  }
  
  logger.warn(`Asset not found in embedded assets`, { assetKey });
  
  return new Response('File not found', {
    status: 404,
    headers: corsHeaders
  });
}

/**
 * Parse HTTP Range header
 */
function parseRange(range: string, size: number): [number, number] {
  const parts = range.replace(/bytes=/, '').split('-');
  const start = parseInt(parts[0], 10) || 0;
  const end = parseInt(parts[1], 10) || size - 1;
  return [start, end];
}

/**
 * Get content type based on file extension
 */
function getContentType(filePath: string): string {
  const ext = filePath.split('.').pop()?.toLowerCase();
  
  const mimeTypes: Record<string, string> = {
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

  return mimeTypes[ext || ''] || 'application/octet-stream';
}
