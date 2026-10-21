/**
 * Cloudflare Worker for MV Face Recognition
 * Serves static frontend and provides API for metadata/videos
 */
import { EMBEDDED_ASSETS, BINARY_ASSETS } from '../embedded-assets.js';
import { logger } from './lib/logger';
import { AppError, InternalError, CorsHeaders } from './lib/errors';

/**
 * Environment bindings for the Cloudflare Worker
 */
interface Env {
  // The deployed Worker is read-only: it reads metadata from KV and streams video from R2, and
  // writes nothing (ADR 0003, ticket 016). `MODAL_JOBS`, `HF_TOKEN`, `MODAL_TOKEN` and the
  // Access pair are still bound in wrangler.toml but no code here reads them any more.
  METADATA_KV: KVNamespace;
  VIDEOS_BUCKET: R2Bucket;
  ENVIRONMENT?: string;
  ALLOWED_ORIGINS?: string;
  LOG_LEVEL?: string;
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
  reference_count: number;
  /**
   * Public crop of the contestant's face, served from R2 (`portraits/{id}.webp`).
   * Absent when no portrait has been published — the viewer shows its 缺相 state
   * rather than falling back to the Instagram originals, which are never served.
   */
  portrait_url?: string;
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

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    let url: URL;
    try {
      url = new URL(request.url);
    } catch (error) {
      logger.error('Malformed request URL', { message: (error as Error).message });
      return new Response('Bad request', { status: 400 });
    }
    const { pathname } = url;

    logger.info(`${request.method} ${pathname}`, {
      userAgent: request.headers.get('User-Agent')?.substring(0, 50),
      timestamp: new Date().toISOString(),
    });

    // CORS headers for all responses.
    // The Worker is read-only and serves public data (ADR 0003), so it carries no
    // credentials and no per-user state; the origin is still restricted to the
    // configured ALLOWED_ORIGINS so a browser on an unrelated site cannot read it.
    const origin = request.headers.get('Origin');
    const allowed = (env.ALLOWED_ORIGINS ?? '')
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);
    const corsHeaders: CorsHeaders = {
      'Access-Control-Allow-Origin':
        origin && allowed.includes(origin) ? origin : allowed.length ? '' : '*',
      // ADR 0003: this Worker serves reads only. Advertising write methods here
      // contradicted the handler surface and invited preflights that can never succeed.
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
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
  },
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
              server.send(
                JSON.stringify({
                  type: 'processing_started',
                  message: 'Video processing started',
                  video_name: data.video_name,
                }),
              );

              // Send periodic updates
              let frameCount = 0;
              const interval = setInterval(() => {
                frameCount += 5;
                if (frameCount > 100) {
                  clearInterval(interval);
                  server.send(
                    JSON.stringify({
                      type: 'processing_complete',
                      message: 'Processing completed',
                      video_name: data.video_name,
                    }),
                  );
                  return;
                }

                server.send(
                  JSON.stringify({
                    type: 'frame_update',
                    data: {
                      frame_number: frameCount,
                      timestamp: frameCount * 0.033,
                      faces: [
                        {
                          contestant_id: '1',
                          contestant_name: 'Ivy So',
                          contestant_nickname: 'Ivy',
                          match_score: 0.45 + Math.random() * 0.2,
                          det_score: 0.93,
                          bbox: [0.41, 0.08, 0.62, 0.75],
                          tracker_id: 3,
                          matched: true,
                        },
                      ],
                      stats: {
                        fps: 30,
                        total_faces: frameCount,
                        recognized: Math.floor(frameCount * 0.8),
                      },
                    },
                  }),
                );
              }, 100);

              break;

            case 'parameter_update':
              server.send(
                JSON.stringify({
                  type: 'parameter_updated',
                  parameter: data.parameter,
                  value: data.value,
                }),
              );
              break;

            default:
              server.send(
                JSON.stringify({
                  type: 'error',
                  message: `Unknown message type: ${data.type}`,
                }),
              );
          }
        } catch (error) {
          const err = error as Error;
          logger.error('WebSocket message processing error', { error: err.message });
          server.send(
            JSON.stringify({
              type: 'error',
              message: 'Failed to process message',
            }),
          );
        }
      });

      server.addEventListener('close', () => {
        logger.info('WebSocket connection closed');
      });

      // Send initial connection confirmation
      server.send(
        JSON.stringify({
          type: 'connected',
          message: 'WebSocket connection established',
        }),
      );

      return new Response(null, {
        status: 101,
        webSocket: client,
      });
    }

    default:
      return new Response('WebSocket endpoint not found', { status: 404 });
  }
}

// Complete 96 contestants from CSV data, served only when KV has no
// `contestants_structured` (local `wrangler dev`). `scripts/publish` writes the real
// `has_embedding` / `reference_count` / quality into KV; the fallback claims no embeddings
// because it cannot know them, and claiming 96 was the original bug (Workstream C).
const allContestants: Contestant[] = [
  {
    id: '1',
    number: 1,
    name: '蘇雅琳',
    nickname: 'Ivy So',
    age: 20,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '2',
    number: 2,
    name: '黃雅慧',
    nickname: '咖喱',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '3',
    number: 3,
    name: '邱彥筒',
    nickname: 'Marf',
    age: 19,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '4',
    number: 4,
    name: '穎蕎',
    nickname: '穎蕎',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '5',
    number: 5,
    name: '坂部佩莎',
    nickname: '莎莎',
    age: 20,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '6',
    number: 6,
    name: '陳玉幸',
    nickname: 'Hannah',
    age: 23,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '7',
    number: 7,
    name: '梁式昕',
    nickname: 'Catrina',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '8',
    number: 8,
    name: '陳玥伶',
    nickname: '小砂',
    age: 29,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '9',
    number: 9,
    name: '羅洛家',
    nickname: 'Carmina',
    age: 26,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '10',
    number: 10,
    name: '余潔瀅',
    nickname: 'Zoe',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '11',
    number: 11,
    name: '鍾君珩',
    nickname: 'Dru',
    age: 28,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '12',
    number: 12,
    name: '何洛瑤',
    nickname: 'Sica',
    age: 21,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '13',
    number: 13,
    name: '曾善婷',
    nickname: 'Ashi',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '14',
    number: 14,
    name: '鄭芷淇',
    nickname: 'Elka',
    age: 18,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '15',
    number: 15,
    name: '李晞彤',
    nickname: 'Carina',
    age: 19,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '16',
    number: 16,
    name: '夏子涓',
    nickname: '子涓',
    age: 26,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '17',
    number: 17,
    name: '黃詠霖',
    nickname: '阿蛋',
    age: 19,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '18',
    number: 18,
    name: '陳莉詩',
    nickname: '蘇菲',
    age: 26,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '19',
    number: 19,
    name: '黃筠兒',
    nickname: '筠兒',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '20',
    number: 20,
    name: '余嘉熙',
    nickname: 'Karen',
    age: 20,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '21',
    number: 21,
    name: '謝裕鈴',
    nickname: 'Ling',
    age: 39,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '22',
    number: 22,
    name: '林暐翹',
    nickname: '暐翹',
    age: 19,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '23',
    number: 23,
    name: '陳祖兒',
    nickname: '陳祖',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '24',
    number: 24,
    name: '曾家瑩',
    nickname: 'Ariel',
    age: 16,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '25',
    number: 25,
    name: '徐嘉蔚',
    nickname: 'Emiko',
    age: 19,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '26',
    number: 26,
    name: '陳泳伽',
    nickname: 'WINKA',
    age: 23,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '27',
    number: 27,
    name: '姜咏鑫',
    nickname: 'Ada 仔',
    age: 21,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '28',
    number: 28,
    name: '王家晴',
    nickname: 'Candy',
    age: 18,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '29',
    number: 29,
    name: '鄺采彤',
    nickname: 'Emi',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '30',
    number: 30,
    name: '羅思雅',
    nickname: 'Caca',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '31',
    number: 31,
    name: '周芷慧',
    nickname: '阿杰',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '32',
    number: 32,
    name: '李凱翹',
    nickname: 'Kay',
    age: 29,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '33',
    number: 33,
    name: '黃敏蕎',
    nickname: '阿妹',
    age: 16,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '34',
    number: 34,
    name: '黃斯琪',
    nickname: 'CK',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '35',
    number: 35,
    name: '羅安娜',
    nickname: 'Ana',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '36',
    number: 36,
    name: '陳曉藍',
    nickname: '精靈',
    age: 19,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '37',
    number: 37,
    name: '利佩佩',
    nickname: 'Puipui',
    age: 20,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '38',
    number: 38,
    name: '沈貞巧',
    nickname: 'Gao',
    age: 28,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '39',
    number: 39,
    name: '葉倩彤',
    nickname: 'Stella',
    age: 23,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '40',
    number: 40,
    name: '李芯駖',
    nickname: '芯駖',
    age: 35,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '41',
    number: 41,
    name: '林文思',
    nickname: 'Man C',
    age: 29,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '42',
    number: 42,
    name: '王綺玲',
    nickname: '2Ling',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '43',
    number: 43,
    name: '區廷筠',
    nickname: 'Tengie',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '44',
    number: 44,
    name: '曾美欣',
    nickname: 'Mei Mei',
    age: 29,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '45',
    number: 45,
    name: '陳景晴',
    nickname: 'Jade Chan',
    age: 20,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '46',
    number: 46,
    name: '歐穎芝',
    nickname: 'Chloe Au',
    age: 18,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '47',
    number: 47,
    name: '周曉欣',
    nickname: 'Ace',
    age: 23,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '48',
    number: 48,
    name: '劉綺婷',
    nickname: 'Yanny',
    age: 22,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '49',
    number: 49,
    name: '溫彩玲',
    nickname: 'Jolin',
    age: 26,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '50',
    number: 50,
    name: '歐卓瑩',
    nickname: '鐵鐵',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '51',
    number: 51,
    name: '歐陽巧霖',
    nickname: 'Bubu',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '52',
    number: 52,
    name: '吳倩怡',
    nickname: 'Sinnie',
    age: 23,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '53',
    number: 53,
    name: '房婷婷',
    nickname: '丁丁',
    age: 23,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '54',
    number: 54,
    name: '任佳慧',
    nickname: 'Miko',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '55',
    number: 55,
    name: '蔡舒文',
    nickname: '舒文',
    age: 22,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '56',
    number: 56,
    name: '鍾心悅',
    nickname: '米線',
    age: 22,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '57',
    number: 57,
    name: '張瑞芝',
    nickname: 'Ariels',
    age: 17,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '58',
    number: 58,
    name: '盧芷韻',
    nickname: 'Kinki',
    age: 17,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '59',
    number: 59,
    name: '張嘉慧',
    nickname: '嘉嘉',
    age: 17,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '60',
    number: 60,
    name: '楊安妮',
    nickname: 'Win Win',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '61',
    number: 61,
    name: '曾業喬',
    nickname: '燒賣',
    age: 16,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '62',
    number: 62,
    name: '何榛綦',
    nickname: '榛綦',
    age: 18,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '63',
    number: 63,
    name: '陳嘉瑤',
    nickname: '露髀',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '64',
    number: 64,
    name: '林泳怡',
    nickname: 'Vicky',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '65',
    number: 65,
    name: '余施熲',
    nickname: '阿 Wing',
    age: 19,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '66',
    number: 66,
    name: '賴泳騫',
    nickname: 'Sam',
    age: 22,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '67',
    number: 67,
    name: '楊芷程',
    nickname: 'Sarah',
    age: 22,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '68',
    number: 68,
    name: '傅奕思',
    nickname: '阿 J',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '69',
    number: 69,
    name: '黃鉦貽',
    nickname: '鉦貽',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '70',
    number: 70,
    name: '郭東彩',
    nickname: '東東',
    age: 21,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '71',
    number: 71,
    name: '莫家琪',
    nickname: '家琪',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '72',
    number: 72,
    name: '廖芷嘉',
    nickname: 'Ika',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '73',
    number: 73,
    name: '陳紀澄',
    nickname: 'Tania',
    age: 18,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '74',
    number: 74,
    name: '蘇芷晴',
    nickname: 'So Ching',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '75',
    number: 75,
    name: '譚羨桐',
    nickname: 'May May',
    age: 20,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '76',
    number: 76,
    name: '羅詠琪',
    nickname: 'Winkie',
    age: 22,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '77',
    number: 77,
    name: '吳秀明',
    nickname: 'TABI',
    age: 28,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '78',
    number: 78,
    name: '馬彩欣',
    nickname: '馬欣',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '79',
    number: 79,
    name: '陳昭煊',
    nickname: '超酸',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '80',
    number: 80,
    name: '方芷欣',
    nickname: '方方',
    age: 26,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '81',
    number: 81,
    name: '鍾卓穎',
    nickname: 'Ash',
    age: 23,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '82',
    number: 82,
    name: '周卓盈',
    nickname: '阿 Mic',
    age: 23,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '83',
    number: 83,
    name: '何佩婷',
    nickname: '何佩',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '84',
    number: 84,
    name: '趙展彤',
    nickname: 'VAL',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '85',
    number: 85,
    name: '蘇家欣',
    nickname: '阿 bee',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '86',
    number: 86,
    name: '黎美萱',
    nickname: 'Michelle',
    age: 25,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '87',
    number: 87,
    name: '葛綽瑤',
    nickname: 'Yoyo',
    age: 22,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '88',
    number: 88,
    name: '劉展翹',
    nickname: 'Jackie',
    age: 27,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '89',
    number: 89,
    name: '安希婷',
    nickname: '安希婷',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '90',
    number: 90,
    name: '鄭嘉欣',
    nickname: 'Christine',
    age: 28,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '91',
    number: 91,
    name: '許軼',
    nickname: 'Day',
    age: 19,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '92',
    number: 92,
    name: '郭曉妍',
    nickname: '阿 Yo',
    age: 16,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '93',
    number: 93,
    name: '廖雪蕎',
    nickname: 'Liu 哥',
    age: 24,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '94',
    number: 94,
    name: '吳欣諺',
    nickname: 'Yanis',
    age: 17,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '95',
    number: 95,
    name: '許寶恆',
    nickname: 'Alice',
    age: 22,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
  {
    id: '96',
    number: 96,
    name: '郭嘉盈',
    nickname: '3 妹',
    age: 26,
    has_photos: true,
    has_embedding: false,
    reference_count: 0,
  },
];

// Fallback video data
const fallbackVideos: VideoData[] = [
  {
    id: '1',
    name: '《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅',
    filename: '1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4',
    path: '/source/videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4',
    size: 234567890,
    duration_seconds: 240,
    fps: 30,
    width: 1920,
    height: 1080,
    frame_count: 7200,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: '2',
    name: '《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅',
    filename: '2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4',
    path: '/source/videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4',
    size: 345678901,
    duration_seconds: 180,
    fps: 30,
    width: 1920,
    height: 1080,
    frame_count: 5400,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: '3',
    name: '《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅',
    filename: '3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4',
    path: '/source/videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4',
    size: 456789012,
    duration_seconds: 200,
    fps: 30,
    width: 1920,
    height: 1080,
    frame_count: 6000,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: '4',
    name: '《全民造星IV》極限拍MV',
    filename: '4-《全民造星IV》極限拍MV.mp4',
    path: '/source/videos/4-《全民造星IV》極限拍MV.mp4',
    size: 567890123,
    duration_seconds: 220,
    fps: 30,
    width: 1920,
    height: 1080,
    frame_count: 6600,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: '5',
    name: '《全民造星IV》播前熱身！率先表演《前傳》',
    filename: '5-《全民造星IV》播前熱身！率先表演《前傳》.mp4',
    path: '/source/videos/5-《全民造星IV》播前熱身！率先表演《前傳》.mp4',
    size: 678901234,
    duration_seconds: 190,
    fps: 30,
    width: 1920,
    height: 1080,
    frame_count: 5700,
    created_at: '2024-01-01T00:00:00Z',
  },
];

/**
 * Handle API requests
 */
async function handleApiRequest(
  pathname: string,
  request: Request,
  env: Env,
  corsHeaders: CorsHeaders,
): Promise<Response> {
  const path = pathname.replace('/api', '');

  // Public face crop for the cast sheet: /api/contestants/{id}/thumb/face
  // The object is immutable (content-addressed by the publish step), so it is
  // safe to cache hard at the edge. Handled before the switch: it is a
  // distinct resource, not another case of the same shape.
  const portrait = path.match(/^\/contestants\/(\d+)\/thumb\/(face|320|640)$/);
  if (portrait) {
    const key = `portraits/${portrait[1]}.webp`;
    const object = await env.VIDEOS_BUCKET.get(key);
    if (!object) {
      return new Response('Portrait not found', {
        status: 404,
        headers: corsHeaders,
      });
    }
    return new Response(object.body, {
      headers: {
        ...corsHeaders,
        'Content-Type': 'image/webp',
        'Content-Length': String(object.size),
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    });
  }

  switch (path) {
    case '/system/status/':
    case '/system/status':
      return new Response(
        JSON.stringify({
          chromadb_connected: true,
          model_loaded: true,
          services_running: true,
          contestant_count: 96,
          video_count: 5,
          processing_jobs: 0,
        }),
        {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        },
      );

    case '/contestants':
    case '/contestants/':
    case '/videos/contestants':
    case '/videos/contestants/': {
      const contestants = await env.METADATA_KV?.get('contestants_structured');
      return new Response(contestants || JSON.stringify(allContestants), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    case '/videos':
    case '/videos/':
      return await handleVideosEndpoint(env, corsHeaders);

    case '/videos/processed/list':
    case '/videos/processed/list/':
      return await handleProcessedVideosEndpoint(env, corsHeaders);

    case '/faces/detect':
    case '/faces/detect/':
      if (request.method === 'GET') {
        return await handleFaceDetection(request, env, corsHeaders);
      }
      break;

    case '/recognition/results':
    case '/recognition/results/':
      return await handleRecognitionResults(request, env, corsHeaders);

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
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }
  }

  // Deliberately 404, not 405: ADR 0003 removed the write routes, and a 405 would tell a
  // caller that a route exists but is gated. Gone must look gone.

  return new Response(JSON.stringify({ error: 'API endpoint not found' }), {
    status: 404,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
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
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // Fallback: Try to get full metadata collection
  const videoMetadataCollection = await env.METADATA_KV?.get('video_metadata_collection');

  if (videoMetadataCollection) {
    logger.debug('Creating optimized response from full metadata collection');
    let parsedData: Record<
      string,
      {
        video_info?: unknown;
        processing_date?: string;
        recognition_summary?: unknown;
      }
    >;
    try {
      parsedData = JSON.parse(videoMetadataCollection) as Record<
        string,
        {
          video_info?: unknown;
          processing_date?: string;
          recognition_summary?: unknown;
        }
      >;
    } catch (error) {
      logger.error('Malformed video metadata collection in KV', {
        message: (error as Error).message,
      });
      return new Response(JSON.stringify({ error: 'metadata unavailable' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    const optimizedVideos: Record<string, unknown> = {};
    for (const [videoId, videoData] of Object.entries(parsedData)) {
      optimizedVideos[videoId] = {
        video_info: videoData.video_info,
        processing_date: videoData.processing_date,
        recognition_summary: videoData.recognition_summary,
        has_detailed_metadata: true,
        metadata_endpoints: {
          basic: `/api/videos/metadata/${encodeURIComponent(videoId)}`,
          detailed: `/api/videos/metadata/dense/${encodeURIComponent(videoId)}`,
        },
      };
    }

    return new Response(JSON.stringify({ videos: optimizedVideos }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  logger.info('Using fallback video data');
  return new Response(JSON.stringify({ videos: fallbackVideos }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

async function handleProcessedVideosEndpoint(
  env: Env,
  corsHeaders: CorsHeaders,
): Promise<Response> {
  const processedVideos = [
    {
      id: '1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅',
      name: '《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅',
      filename: '1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4',
      size: 768000000,
      created_at: 1672531200,
      has_metadata: true,
      stream_url:
        '/videos/processed_videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4',
    },
    {
      id: '2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅',
      name: '《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅',
      filename: '2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4',
      size: 693000000,
      created_at: 1672531200,
      has_metadata: true,
      stream_url:
        '/videos/processed_videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4',
    },
    {
      id: '3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅',
      name: '《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅',
      filename: '3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4',
      size: 690000000,
      created_at: 1672531200,
      has_metadata: true,
      stream_url:
        '/videos/processed_videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4',
    },
    {
      id: '4-《全民造星IV》極限拍MV',
      name: '《全民造星IV》極限拍MV',
      filename: '4-《全民造星IV》極限拍MV_annotated.mp4',
      size: 521000000,
      created_at: 1672531200,
      has_metadata: true,
      stream_url: '/videos/processed_videos/4-《全民造星IV》極限拍MV_annotated.mp4',
    },
    {
      id: '5-《全民造星IV》播前熱身！率先表演《前傳》',
      name: '《全民造星IV》播前熱身！率先表演《前傳》',
      filename: '5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4',
      size: 538000000,
      created_at: 1672531200,
      has_metadata: true,
      stream_url:
        '/videos/processed_videos/5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4',
    },
  ];

  const storedProcessedVideos = await env.METADATA_KV?.get('processed_videos_list');
  return new Response(storedProcessedVideos || JSON.stringify(processedVideos), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

async function handleFaceDetection(
  request: Request,
  env: Env,
  corsHeaders: CorsHeaders,
): Promise<Response> {
  let url: URL;
  try {
    url = new URL(request.url);
  } catch (error) {
    logger.error('Malformed request URL', { message: (error as Error).message });
    return new Response(JSON.stringify({ error: 'malformed request url' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
  const videoId = url.searchParams.get('video_id');
  const timestamp = parseFloat(url.searchParams.get('timestamp') || '0');

  if (!videoId) {
    return new Response(JSON.stringify({ error: 'video_id required' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // Ticket 007 Q1: keys are full video ids.
  const denseMetadata = await env.METADATA_KV.get(`metadata_${videoId}`);

  if (denseMetadata) {
    let parsed: {
      frame_data?: Array<{
        timestamp: number;
        frame_number?: number;
        detections?: Array<{
          contestant_id?: string | null;
          contestant_name?: string | null;
          contestant_nickname?: string | null;
          /** Raw cosine similarity to the contestant's best reference embedding, null when unmatched */
          match_score?: number | null;
          /** Detector's own face score, present on every detection */
          det_score?: number;
          /** Frame fractions, canonical [x1, y1, x2, y2] */
          bbox?: number[];
          tracker_id?: number | null;
        }>;
      }>;
    };
    try {
      parsed = JSON.parse(denseMetadata) as typeof parsed;
    } catch (error) {
      logger.error('Malformed dense metadata in KV', {
        message: (error as Error).message,
        videoId,
      });
      return new Response(JSON.stringify({ error: 'metadata unavailable' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Floor match: most recent frame at or before the timestamp, so boxes
    // never appear ahead of the face (same convention as local_api.py).
    const frames = (parsed.frame_data || [])
      .filter((fd) => typeof fd.timestamp === 'number')
      .sort((a, b) => a.timestamp - b.timestamp);
    let frame: (typeof frames)[number] | null = null;
    for (const fd of frames) {
      if (fd.timestamp <= timestamp) frame = fd;
      else break;
    }

    // Stored bboxes are frame fractions in canonical [x1, y1, x2, y2] order and are
    // served verbatim: never reordered, never scaled by any width or height.
    const faces = (frame?.detections || [])
      .filter((d) => Array.isArray(d.bbox) && d.bbox.length === 4)
      .map((d) => ({
        bbox: d.bbox as [number, number, number, number],
        match_score: d.match_score ?? null,
        det_score: d.det_score ?? 0,
        contestant_id: d.contestant_id ?? null,
        contestant_name: d.contestant_name ?? null,
        contestant_nickname: d.contestant_nickname ?? null,
        tracker_id: d.tracker_id ?? null,
        matched: d.contestant_id != null,
      }));

    return new Response(
      JSON.stringify({
        video_id: videoId,
        timestamp: timestamp,
        frame: frame?.frame_number ?? null,
        faces: faces,
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      },
    );
  }

  return new Response(
    JSON.stringify({
      video_id: videoId,
      timestamp: timestamp,
      faces: [],
      message: 'No detection metadata available for this video',
    }),
    {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    },
  );
}

async function handleRecognitionResults(
  request: Request,
  env: Env,
  corsHeaders: CorsHeaders,
): Promise<Response> {
  let url: URL;
  try {
    url = new URL(request.url);
  } catch (error) {
    logger.error('Malformed request URL', { message: (error as Error).message });
    return new Response(JSON.stringify({ error: 'malformed request url' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
  const videoIdFilter = url.searchParams.get('video_id');
  const contestantIdFilter = url.searchParams.get('contestant_id');

  if (!contestantIdFilter) {
    return new Response(JSON.stringify({ error: 'contestant_id required' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // Ticket 007 Q1: keys are full video ids.
  let metadataKeys: string[];
  if (videoIdFilter) {
    metadataKeys = [`metadata_${videoIdFilter}`];
  } else {
    const listing = await env.METADATA_KV.list({ prefix: 'metadata_' });
    metadataKeys = listing.keys.map((k) => k.name);
  }

  type Appearance = { timestamp?: number; match_score?: number; frame_number?: number };
  const results: Array<{
    video_id: string;
    timestamp: number;
    match_score: number;
    frame_number?: number;
  }> = [];

  for (const key of metadataKeys) {
    const stored = await env.METADATA_KV.get(key);
    if (!stored) continue;
    try {
      const parsed = JSON.parse(stored) as {
        contestant_timeline?: Record<string, { appearances?: Appearance[] }>;
      };
      const entry = parsed.contestant_timeline?.[contestantIdFilter];
      if (!entry?.appearances) continue;
      const videoId = videoIdFilter || key.replace('metadata_', '');
      for (const appearance of entry.appearances) {
        results.push({
          video_id: videoId,
          timestamp: appearance.timestamp ?? 0,
          match_score: appearance.match_score ?? 0,
          frame_number: appearance.frame_number,
        });
      }
    } catch {
      continue;
    }
  }

  results.sort((a, b) => a.video_id.localeCompare(b.video_id) || a.timestamp - b.timestamp);

  return new Response(
    JSON.stringify({
      results: results,
      total: results.length,
      filters: { video_id: videoIdFilter, contestant_id: contestantIdFilter },
    }),
    {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    },
  );
}

// Admin Endpoints

async function handleDenseMetadata(
  path: string,
  env: Env,
  corsHeaders: CorsHeaders,
): Promise<Response> {
  let videoId = path.replace('/videos/metadata/dense/', '');

  try {
    videoId = decodeURIComponent(videoId);
  } catch {
    // If decoding fails, use as-is
  }

  // Ticket 007 Q1: the key is the full video id from processed_videos_list, so a
  // numeric prefix can never serve another reel's metadata.
  const key = `metadata_${videoId}`;
  const storedDenseMetadata = await env.METADATA_KV?.get(key);

  if (storedDenseMetadata) {
    return new Response(storedDenseMetadata, {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // No mock, no dead key fallback (ticket 007 Q2): a missing reel fails loudly.
  return new Response(JSON.stringify({ error: 'metadata not found', key }), {
    status: 404,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

async function handleVideoMetadata(
  path: string,
  env: Env,
  corsHeaders: CorsHeaders,
): Promise<Response> {
  let videoId = path.replace('/videos/metadata/', '');

  try {
    videoId = decodeURIComponent(videoId);
  } catch {
    // If decoding fails, use as-is
  }

  const key = `metadata_${videoId}`;
  const storedVideoMetadata = await env.METADATA_KV?.get(key);

  if (storedVideoMetadata) {
    return new Response(storedVideoMetadata, {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  return new Response(JSON.stringify({ error: 'metadata not found', key }), {
    status: 404,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

/**
 * Handle video file requests from R2
 */
async function handleVideoRequest(
  pathname: string,
  request: Request,
  env: Env,
  corsHeaders: CorsHeaders,
): Promise<Response> {
  const videoPath = pathname.replace('/videos/', '');

  try {
    if (!env.VIDEOS_BUCKET) {
      return new Response(
        JSON.stringify({
          error: 'Video storage not configured. Please enable R2 in your Cloudflare dashboard.',
        }),
        {
          status: 503,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        },
      );
    }

    const object = await env.VIDEOS_BUCKET.get(videoPath);

    if (!object) {
      return new Response('Video not found', {
        status: 404,
        headers: corsHeaders,
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
        range: { offset: start, length: end - start + 1 },
      });

      if (!rangeObject) {
        return new Response('Video not found', { status: 404, headers: corsHeaders });
      }

      return new Response(rangeObject.body, {
        status: 206,
        headers,
      });
    }

    return new Response(object.body, { headers });
  } catch (error) {
    const err = error as Error;
    logger.error('Error serving video', { error: err.message, stack: err.stack });
    return new Response('Error serving video', {
      status: 500,
      headers: corsHeaders,
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
    const cacheControl = finalPath.includes('assets/')
      ? 'public, max-age=31536000'
      : 'public, max-age=3600';

    // Binary assets are stored base64-encoded by scripts/update-worker-assets.js
    const body = BINARY_ASSETS.has(assetKey)
      ? Uint8Array.from(atob(embeddedAssets[assetKey]), (c) => c.charCodeAt(0))
      : embeddedAssets[assetKey];

    return new Response(body, {
      headers: {
        ...corsHeaders,
        'Content-Type': contentType,
        'Cache-Control': cacheControl,
      },
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
          'Cache-Control': 'public, max-age=3600',
        },
      });
    }

    logger.debug(`SPA route detected, serving index.html for: ${finalPath}`);
    return new Response(embeddedAssets['index.html'], {
      headers: {
        ...corsHeaders,
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=3600',
      },
    });
  }

  logger.warn(`Asset not found in embedded assets`, { assetKey });

  return new Response('File not found', {
    status: 404,
    headers: corsHeaders,
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
    html: 'text/html; charset=utf-8',
    js: 'application/javascript',
    css: 'text/css',
    json: 'application/json',
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    gif: 'image/gif',
    svg: 'image/svg+xml',
    ico: 'image/x-icon',
    woff: 'font/woff',
    woff2: 'font/woff2',
    ttf: 'font/ttf',
    eot: 'application/vnd.ms-fontobject',
  };

  return mimeTypes[ext || ''] || 'application/octet-stream';
}
