#!/usr/bin/env node
/**
 * Process YouTube Queue
 *
 * This script polls the YouTube queue in Cloudflare KV and triggers
 * Modal processing for queued videos.
 *
 * Usage:
 *   node scripts/process-youtube-queue.js [--queue-id <id>] [--continuous]
 *
 * Options:
 *   --queue-id <id>  Process a specific queue entry
 *   --continuous     Keep running and poll queue every 30 seconds
 *   --dry-run        Show what would be processed without actually processing
 */

const { execFile } = require('child_process');
const { promisify } = require('util');

const execFileAsync = promisify(execFile);

// Configuration
const API_BASE_URL = process.env.API_URL || 'https://mv-face-recognition-api.herballemon.workers.dev';
const POLL_INTERVAL = 30000; // 30 seconds
const CLOUDFLARE_ACCOUNT_ID = process.env.CLOUDFLARE_ACCOUNT_ID;
const KV_NAMESPACE_ID = process.env.KV_NAMESPACE_ID || '890d77e11bfc4623ac4ef56db6b9a4ab';
const CLOUDFLARE_API_TOKEN = process.env.CLOUDFLARE_API_TOKEN;

// Parse command line arguments
const args = process.argv.slice(2);
const options = {
  queueId: null,
  continuous: args.includes('--continuous'),
  dryRun: args.includes('--dry-run')
};

const queueIdIndex = args.indexOf('--queue-id');
if (queueIdIndex !== -1 && args[queueIdIndex + 1]) {
  options.queueId = args[queueIdIndex + 1];
}

/**
 * Fetch queue entries from Cloudflare KV
 */
async function fetchQueueEntries() {
  if (!CLOUDFLARE_API_TOKEN || !CLOUDFLARE_ACCOUNT_ID) {
    console.error('Error: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID must be set');
    process.exit(1);
  }

  try {
    // Fetch queue index
    const indexResponse = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/storage/kv/namespaces/${KV_NAMESPACE_ID}/values/youtube_queue_index`,
      {
        headers: {
          'Authorization': `Bearer ${CLOUDFLARE_API_TOKEN}`,
        }
      }
    );

    if (!indexResponse.ok) {
      console.error('Failed to fetch queue index:', indexResponse.statusText);
      return [];
    }

    const queueIndex = await indexResponse.json();

    // Fetch each queue entry
    const entries = [];
    for (const queueId of queueIndex) {
      try {
        const entryResponse = await fetch(
          `https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/storage/kv/namespaces/${KV_NAMESPACE_ID}/values/youtube_queue_${queueId}`,
          {
            headers: {
              'Authorization': `Bearer ${CLOUDFLARE_API_TOKEN}`,
            }
          }
        );

        if (entryResponse.ok) {
          const entry = await entryResponse.json();
          entries.push(entry);
        }
      } catch (error) {
        console.error(`Failed to fetch entry ${queueId}:`, error.message);
      }
    }

    return entries;
  } catch (error) {
    console.error('Error fetching queue:', error.message);
    return [];
  }
}

/**
 * Update queue entry status
 */
async function updateQueueStatus(queueId, status, errorMsg = null) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/admin/youtube/status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        queue_id: queueId,
        status,
        error: errorMsg
      })
    });

    if (!response.ok) {
      console.error(`Failed to update status for ${queueId}:`, response.statusText);
    }
  } catch (error) {
    console.error(`Error updating status for ${queueId}:`, error.message);
  }
}

/**
 * Process a single queue entry using Modal
 */
async function processQueueEntry(entry) {
  const { id, youtube_url, status } = entry;

  console.log(`\n${'='.repeat(60)}`);
  console.log(`Processing: ${id}`);
  console.log(`URL: ${youtube_url}`);
  console.log(`Status: ${status}`);
  console.log(`${'='.repeat(60)}\n`);

  if (options.dryRun) {
    console.log('[DRY RUN] Would process this entry');
    return;
  }

  try {
    // Update status to processing
    await updateQueueStatus(id, 'processing');

    // Run Modal processing using execFile (secure)
    console.log('Starting Modal processing...');

    const modalArgs = [
      'run',
      'scripts/modal_youtube_processor.py',
      '--queue-id',
      id,
      '--url',
      youtube_url
    ];

    console.log(`Executing: modal ${modalArgs.join(' ')}`);

    const { stdout, stderr } = await execFileAsync('modal', modalArgs, {
      cwd: '/Users/yellowcandle/dev/mv-face-recognition',
      maxBuffer: 10 * 1024 * 1024 // 10MB buffer
    });

    if (stdout) {
      console.log(stdout);
    }
    if (stderr) {
      console.error(stderr);
    }

    console.log('\n✓ Modal processing completed successfully');

    // Update status to completed
    await updateQueueStatus(id, 'completed');

  } catch (error) {
    console.error('\n✗ Modal processing failed:', error.message);
    if (error.stderr) {
      console.error('Error output:', error.stderr);
    }

    // Update status to failed
    await updateQueueStatus(id, 'failed', error.message);

    if (!options.continuous) {
      process.exit(1);
    }
  }
}

/**
 * Process queue
 */
async function processQueue() {
  console.log('Checking YouTube queue...');

  const entries = await fetchQueueEntries();

  if (entries.length === 0) {
    console.log('No entries in queue');
    return;
  }

  console.log(`Found ${entries.length} entries in queue`);

  // Filter for queued entries (not already processing/completed/failed)
  const queuedEntries = entries.filter(e => e.status === 'queued');

  if (queuedEntries.length === 0) {
    console.log('No queued entries to process');
    return;
  }

  console.log(`${queuedEntries.length} entries are queued for processing`);

  // Process one entry at a time
  for (const entry of queuedEntries) {
    // If specific queue ID requested, skip others
    if (options.queueId && entry.id !== options.queueId) {
      continue;
    }

    await processQueueEntry(entry);

    // If not continuous mode and specific queue ID, exit after processing
    if (options.queueId && !options.continuous) {
      return;
    }
  }
}

/**
 * Main execution
 */
async function main() {
  console.log('\n🎬 YouTube Queue Processor');
  console.log('='.repeat(60));
  console.log(`Mode: ${options.continuous ? 'Continuous' : 'One-time'}`);
  console.log(`Dry Run: ${options.dryRun ? 'Yes' : 'No'}`);
  if (options.queueId) {
    console.log(`Queue ID Filter: ${options.queueId}`);
  }
  console.log('='.repeat(60));

  if (!CLOUDFLARE_API_TOKEN || !CLOUDFLARE_ACCOUNT_ID) {
    console.log('\n⚠️  Missing environment variables:');
    console.log('   CLOUDFLARE_API_TOKEN');
    console.log('   CLOUDFLARE_ACCOUNT_ID');
    console.log('\nPlease set these variables and try again.');
    process.exit(1);
  }

  if (options.continuous) {
    console.log(`\nPolling every ${POLL_INTERVAL / 1000} seconds...`);
    console.log('Press Ctrl+C to stop\n');

    // Initial run
    await processQueue();

    // Set up interval
    setInterval(async () => {
      console.log(`\n--- Poll at ${new Date().toLocaleTimeString()} ---`);
      await processQueue();
    }, POLL_INTERVAL);

  } else {
    // One-time run
    await processQueue();
    console.log('\n✓ Queue processing complete');
  }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('\n\nShutting down gracefully...');
  process.exit(0);
});

// Run
main().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
