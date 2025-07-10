#!/usr/bin/env node

/**
 * Comprehensive Test Suite for MV Face Recognition Cloudflare Workers Deployment
 * Tests all endpoints, WebSocket functionality, and integration scenarios
 */

const https = require('https');
const WebSocket = require('ws');

const BASE_URL = 'https://mv-face-recognition-api.herballemon.workers.dev';
const WS_URL = 'wss://mv-face-recognition-api.herballemon.workers.dev';

class DeploymentTester {
  constructor() {
    this.results = {
      passed: 0,
      failed: 0,
      errors: []
    };
  }

  async runAllTests() {
    console.log('🧪 Starting Comprehensive Deployment Test Suite');
    console.log('='.repeat(60));

    try {
      // Basic connectivity tests
      await this.testBasicConnectivity();
      
      // API endpoint tests
      await this.testApiEndpoints();
      
      // Frontend tests
      await this.testFrontendAssets();
      
      // WebSocket tests
      await this.testWebSocketFunctionality();
      
      // Integration tests
      await this.testIntegrationScenarios();
      
      // Performance tests
      await this.testPerformance();

    } catch (error) {
      this.logError('Test suite execution failed', error);
    }

    this.printSummary();
  }

  async testBasicConnectivity() {
    this.logSection('Basic Connectivity Tests');

    await this.test('Root URL responds', async () => {
      const response = await this.fetch('/');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const text = await response.text();
      this.assert(text.includes('<!DOCTYPE html>'), 'Response should be HTML');
      this.assert(text.includes('MV Face Recognition'), 'Should contain app title');
    });

    await this.test('CORS headers present', async () => {
      const response = await this.fetch('/', { method: 'OPTIONS' });
      this.assert(response.status === 200, 'OPTIONS request should succeed');
      this.assert(response.headers.get('Access-Control-Allow-Origin'), 'Should have CORS origin header');
      this.assert(response.headers.get('Access-Control-Allow-Methods'), 'Should have CORS methods header');
    });

    await this.test('API base path responds', async () => {
      const response = await this.fetch('/api/system/status');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const data = await response.json();
      this.assert(typeof data === 'object', 'Should return JSON object');
    });
  }

  async testApiEndpoints() {
    this.logSection('API Endpoint Tests');

    // System status
    await this.test('/api/system/status', async () => {
      const response = await this.fetch('/api/system/status');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const data = await response.json();
      this.assert(data.chromadb_connected !== undefined, 'Should have chromadb_connected field');
      this.assert(data.model_loaded !== undefined, 'Should have model_loaded field');
      this.assert(typeof data.contestant_count === 'number', 'Should have contestant_count as number');
    });

    // Contestants endpoint
    await this.test('/api/contestants', async () => {
      const response = await this.fetch('/api/contestants');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const data = await response.json();
      this.assert(Array.isArray(data), 'Should return array of contestants');
      this.assert(data.length > 0, 'Should have contestants');
      if (data.length > 0) {
        const contestant = data[0];
        this.assert(contestant.id !== undefined, 'Contestant should have id');
        this.assert(contestant.name !== undefined, 'Contestant should have name');
        this.assert(contestant.nickname !== undefined, 'Contestant should have nickname');
      }
    });

    // Videos endpoint (main app format)
    await this.test('/api/videos', async () => {
      const response = await this.fetch('/api/videos');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const data = await response.json();
      this.assert(data.videos !== undefined, 'Should have videos property');
      this.assert(Array.isArray(data.videos), 'Videos should be array');
      this.assert(data.videos.length > 0, 'Should have videos');
      if (data.videos.length > 0) {
        const video = data.videos[0];
        this.assert(video.id !== undefined, 'Video should have id');
        this.assert(video.name !== undefined, 'Video should have name');
      }
    });

    // Processed videos endpoint (video player format)
    await this.test('/api/videos/processed/list', async () => {
      const response = await this.fetch('/api/videos/processed/list');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const data = await response.json();
      this.assert(Array.isArray(data), 'Should return array of processed videos');
      this.assert(data.length > 0, 'Should have processed videos');
      if (data.length > 0) {
        const video = data[0];
        this.assert(video.id !== undefined, 'Video should have id');
        this.assert(video.stream_url !== undefined, 'Video should have stream_url');
        this.assert(video.has_metadata !== undefined, 'Video should have has_metadata');
      }
    });

    // Video metadata endpoint
    await this.test('/api/videos/metadata/1', async () => {
      const response = await this.fetch('/api/videos/metadata/1');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const data = await response.json();
      this.assert(data.video_id !== undefined, 'Should have video_id');
      this.assert(data.recognition_summary !== undefined, 'Should have recognition_summary');
    });

    // Dense metadata endpoint
    await this.test('/api/videos/metadata/dense/1', async () => {
      const response = await this.fetch('/api/videos/metadata/dense/1');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const data = await response.json();
      this.assert(data.video_id !== undefined, 'Should have video_id');
      this.assert(data.contestant_timeline !== undefined, 'Should have contestant_timeline');
    });

    // Settings endpoint
    await this.test('/api/settings GET', async () => {
      const response = await this.fetch('/api/settings');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const data = await response.json();
      this.assert(typeof data === 'object', 'Should return settings object');
    });
  }

  async testFrontendAssets() {
    this.logSection('Frontend Asset Tests');

    await this.test('Main HTML loads', async () => {
      const response = await this.fetch('/');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const html = await response.text();
      this.assert(html.includes('<!DOCTYPE html>'), 'Should be valid HTML');
      this.assert(html.includes('index-'), 'Should reference compiled assets');
    });

    await this.test('CSS assets load', async () => {
      // First get the HTML to find asset names
      const htmlResponse = await this.fetch('/');
      const html = await htmlResponse.text();
      const cssMatch = html.match(/assets\/(index-[^"]+\.css)/);
      
      if (cssMatch) {
        const cssPath = `/assets/${cssMatch[1]}`;
        const response = await this.fetch(cssPath);
        this.assert(response.status === 200, `CSS asset ${cssPath} should load`);
        this.assert(response.headers.get('content-type').includes('text/css'), 'Should have CSS content type');
      } else {
        throw new Error('Could not find CSS asset reference in HTML');
      }
    });

    await this.test('JS assets load', async () => {
      // First get the HTML to find asset names
      const htmlResponse = await this.fetch('/');
      const html = await htmlResponse.text();
      const jsMatch = html.match(/assets\/(index-[^"]+\.js)/);
      
      if (jsMatch) {
        const jsPath = `/assets/${jsMatch[1]}`;
        const response = await this.fetch(jsPath);
        this.assert(response.status === 200, `JS asset ${jsPath} should load`);
        this.assert(response.headers.get('content-type').includes('javascript'), 'Should have JS content type');
      } else {
        throw new Error('Could not find JS asset reference in HTML');
      }
    });

    await this.test('SPA routing works', async () => {
      const response = await this.fetch('/video-player');
      this.assert(response.status === 200, `Expected 200, got ${response.status}`);
      const html = await response.text();
      this.assert(html.includes('<!DOCTYPE html>'), 'Should return HTML for SPA routes');
    });
  }

  async testWebSocketFunctionality() {
    this.logSection('WebSocket Tests');

    await this.test('WebSocket connection establishes', () => {
      return new Promise((resolve, reject) => {
        const ws = new WebSocket(`${WS_URL}/ws/realtime-processing`);
        
        const timeout = setTimeout(() => {
          ws.close();
          reject(new Error('WebSocket connection timeout'));
        }, 10000);

        ws.on('open', () => {
          clearTimeout(timeout);
          ws.close();
          resolve();
        });

        ws.on('error', (error) => {
          clearTimeout(timeout);
          reject(error);
        });
      });
    });

    await this.test('WebSocket receives connection confirmation', () => {
      return new Promise((resolve, reject) => {
        const ws = new WebSocket(`${WS_URL}/ws/realtime-processing`);
        
        const timeout = setTimeout(() => {
          ws.close();
          reject(new Error('No connection confirmation received'));
        }, 10000);

        ws.on('message', (data) => {
          try {
            const message = JSON.parse(data.toString());
            if (message.type === 'connected') {
              clearTimeout(timeout);
              ws.close();
              resolve();
            }
          } catch (error) {
            clearTimeout(timeout);
            ws.close();
            reject(error);
          }
        });

        ws.on('error', (error) => {
          clearTimeout(timeout);
          reject(error);
        });
      });
    });

    await this.test('WebSocket processing simulation works', () => {
      return new Promise((resolve, reject) => {
        const ws = new WebSocket(`${WS_URL}/ws/realtime-processing`);
        let receivedFrameUpdate = false;
        
        const timeout = setTimeout(() => {
          ws.close();
          if (!receivedFrameUpdate) {
            reject(new Error('No frame updates received'));
          }
        }, 15000);

        ws.on('open', () => {
          // Start processing simulation
          ws.send(JSON.stringify({
            type: 'start_processing',
            video_name: 'test-video'
          }));
        });

        ws.on('message', (data) => {
          try {
            const message = JSON.parse(data.toString());
            
            if (message.type === 'frame_update') {
              receivedFrameUpdate = true;
              this.assert(message.data !== undefined, 'Frame update should have data');
              this.assert(message.data.frame_number !== undefined, 'Should have frame_number');
              this.assert(message.data.faces !== undefined, 'Should have faces array');
              clearTimeout(timeout);
              ws.close();
              resolve();
            }
          } catch (error) {
            clearTimeout(timeout);
            ws.close();
            reject(error);
          }
        });

        ws.on('error', (error) => {
          clearTimeout(timeout);
          reject(error);
        });
      });
    });
  }

  async testIntegrationScenarios() {
    this.logSection('Integration Scenario Tests');

    await this.test('Video player workflow', async () => {
      // 1. Load processed videos
      const videosResponse = await this.fetch('/api/videos/processed/list');
      const videos = await videosResponse.json();
      this.assert(videos.length > 0, 'Should have processed videos');

      // 2. Load video metadata
      const firstVideo = videos[0];
      const metadataResponse = await this.fetch(`/api/videos/metadata/${firstVideo.id}`);
      const metadata = await metadataResponse.json();
      
      // The metadata should have a numeric video_id extracted from the full video ID
      const expectedVideoId = firstVideo.id.match(/^(\d+)-/)?.[1] || firstVideo.id;
      this.assert(metadata.video_id === expectedVideoId, `Metadata video_id should be "${expectedVideoId}", got "${metadata.video_id}"`);

      // 3. Load contestants
      const contestantsResponse = await this.fetch('/api/contestants');
      const contestants = await contestantsResponse.json();
      this.assert(contestants.length > 0, 'Should have contestants data');
    });

    await this.test('Main app workflow', async () => {
      // 1. Load videos in main app format
      const videosResponse = await this.fetch('/api/videos');
      const videosData = await videosResponse.json();
      this.assert(videosData.videos !== undefined, 'Should have videos wrapper');
      this.assert(Array.isArray(videosData.videos), 'Videos should be array');

      // 2. Check system status
      const statusResponse = await this.fetch('/api/system/status');
      const status = await statusResponse.json();
      this.assert(status.chromadb_connected !== undefined, 'Should have system status');
    });
  }

  async testPerformance() {
    this.logSection('Performance Tests');

    await this.test('Response times are reasonable', async () => {
      const endpoints = [
        '/',
        '/api/system/status',
        '/api/contestants',
        '/api/videos'
      ];

      for (const endpoint of endpoints) {
        const start = Date.now();
        const response = await this.fetch(endpoint);
        const duration = Date.now() - start;
        
        this.assert(response.status === 200, `${endpoint} should respond successfully`);
        this.assert(duration < 5000, `${endpoint} should respond within 5s (took ${duration}ms)`);
        
        if (duration > 1000) {
          console.log(`⚠️  ${endpoint} took ${duration}ms (slow)`);
        }
      }
    });

    await this.test('Concurrent requests handled', async () => {
      const promises = [];
      const endpoint = '/api/system/status';
      
      // Make 5 concurrent requests
      for (let i = 0; i < 5; i++) {
        promises.push(this.fetch(endpoint));
      }

      const responses = await Promise.all(promises);
      
      for (let i = 0; i < responses.length; i++) {
        this.assert(responses[i].status === 200, `Concurrent request ${i + 1} should succeed`);
      }
    });
  }

  // Helper methods
  async fetch(path, options = {}) {
    const url = `${BASE_URL}${path}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'User-Agent': 'MV-Face-Recognition-Test-Suite/1.0',
        ...options.headers
      }
    });
    return response;
  }

  async test(name, testFunction) {
    process.stdout.write(`  Testing: ${name}... `);
    
    try {
      await testFunction();
      console.log('✅ PASS');
      this.results.passed++;
    } catch (error) {
      console.log('❌ FAIL');
      console.log(`    Error: ${error.message}`);
      this.results.failed++;
      this.results.errors.push({ test: name, error: error.message });
    }
  }

  assert(condition, message) {
    if (!condition) {
      throw new Error(message);
    }
  }

  logSection(title) {
    console.log(`\n📋 ${title}`);
    console.log('-'.repeat(title.length + 4));
  }

  logError(message, error) {
    console.log(`\n❌ ${message}`);
    console.log(`Error: ${error.message}`);
    this.results.failed++;
    this.results.errors.push({ test: message, error: error.message });
  }

  printSummary() {
    console.log('\n' + '='.repeat(60));
    console.log('📊 Test Summary');
    console.log('='.repeat(60));
    console.log(`✅ Passed: ${this.results.passed}`);
    console.log(`❌ Failed: ${this.results.failed}`);
    console.log(`📈 Total:  ${this.results.passed + this.results.failed}`);

    if (this.results.failed > 0) {
      console.log('\n🔍 Failed Tests:');
      this.results.errors.forEach(({ test, error }) => {
        console.log(`  • ${test}: ${error}`);
      });
      
      console.log('\n🚨 DEPLOYMENT HAS ISSUES - See failed tests above');
      process.exit(1);
    } else {
      console.log('\n🎉 ALL TESTS PASSED - Deployment is working correctly!');
      process.exit(0);
    }
  }
}

// Run the test suite
if (require.main === module) {
  const tester = new DeploymentTester();
  tester.runAllTests().catch(error => {
    console.error('Test suite failed to run:', error);
    process.exit(1);
  });
}

module.exports = DeploymentTester; 