/**
 * Cloudflare Worker for MV Face Recognition
 * Serves static frontend and provides API for metadata/videos
 */
import { EMBEDDED_ASSETS } from './embedded-assets.js';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const { pathname } = url;

    console.log(`[${new Date().toISOString()}] ${request.method} ${pathname} - User-Agent: ${request.headers.get('User-Agent')?.substring(0, 50)}...`);

    // CORS headers for all responses
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      console.log(`CORS preflight for ${pathname}`);
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // API routes
      if (pathname.startsWith('/api/')) {
        console.log(`Routing to API handler: ${pathname}`);
        return await handleApiRequest(pathname, request, env, corsHeaders);
      }

      // Video files from R2
      if (pathname.startsWith('/videos/')) {
        console.log(`Routing to video handler: ${pathname}`);
        return await handleVideoRequest(pathname, request, env, corsHeaders);
      }

      // Static frontend files
      console.log(`Routing to static handler: ${pathname}`);
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
    case '/videos/contestants':
      // Complete 96 contestants from CSV data
      const allContestants = [
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
      
      const contestants = await env.METADATA_KV?.get('contestants_structured');
      return new Response(contestants || JSON.stringify(allContestants), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });

    case '/videos':
      const allVideos = [
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
      
      const videos = await env.METADATA_KV.get('videos_list');
      return new Response(videos || JSON.stringify(allVideos), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });

    case '/videos/processed/list':
      // Return processed videos in the format expected by the VideoPlayer frontend
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
      
      // Try to get from KV storage first, fallback to hardcoded data
      const storedProcessedVideos = await env.METADATA_KV?.get('processed_videos_list');
      return new Response(storedProcessedVideos || JSON.stringify(processedVideos), {
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
      // Handle /videos/metadata/dense/{video_id}
      if (path.startsWith('/videos/metadata/dense/')) {
        const videoId = path.replace('/videos/metadata/dense/', '');
        
        // Mock dense metadata structure
        const denseMetadata = {
          "video_id": videoId,
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
                {
                  "frame": 262,
                  "timestamp": 10.48,
                  "confidence": 0.87,
                  "bbox": [100, 150, 200, 300]
                }
              ]
            }
          }
        };
        
        // Try to get from KV storage first, fallback to mock data
        const storedMetadata = await env.METADATA_KV?.get(`video_metadata_dense_${videoId}`);
        return new Response(storedMetadata || JSON.stringify(denseMetadata), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
      
      // Handle /videos/metadata/{video_id}
      if (path.startsWith('/videos/metadata/') && !path.includes('/dense/')) {
        const videoId = path.replace('/videos/metadata/', '');
        
        // Mock regular metadata structure
        const metadata = {
          "video_id": videoId,
          "video_info": {
            "filename": `${videoId}.mp4`,
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
        
        // Try to get from KV storage first, fallback to mock data
        const storedMetadata = await env.METADATA_KV?.get(`video_metadata_${videoId}`);
        return new Response(storedMetadata || JSON.stringify(metadata), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
      
      // Legacy metadata endpoint handling
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
  console.log(`Static request for: ${pathname}`);
  
  // Handle root path
  if (pathname === '/') {
    pathname = 'index.html';
  }
  
  // Remove leading slash for asset lookup
  const assetKey = pathname.startsWith('/') ? pathname.substring(1) : pathname;
  
  // Check if we have the asset in our embedded assets
  if (EMBEDDED_ASSETS[assetKey]) {
    console.log(`Successfully serving embedded asset: ${assetKey}`);
    
    const contentType = getContentType(pathname);
    const cacheControl = pathname.includes('assets/') ? 'public, max-age=31536000' : 'public, max-age=3600';
    
    return new Response(EMBEDDED_ASSETS[assetKey], {
      headers: {
        ...corsHeaders,
        'Content-Type': contentType,
        'Cache-Control': cacheControl
      }
    });
  }
  
  // For SPA routing, serve index.html for unknown routes
  if (!pathname.includes('.')) {
    console.log(`SPA route detected, serving index.html for: ${pathname}`);
    return new Response(EMBEDDED_ASSETS['index.html'], {
      headers: {
        ...corsHeaders,
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=3600'
      }
    });
  }
  
  console.log(`Asset not found in embedded assets: ${assetKey}`);
  
  // Asset not found - return 404
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