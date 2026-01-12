import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ request, platform }) => {
	try {
		const params = await request.json();
		
		// Validate required parameters
		const { mode, video_names, similarity_threshold, force_reprocess, sync_from_hf, upload_results } = params;
		
		if (!mode || !['full', 'initial', 'embedding-update'].includes(mode)) {
			return json(
				{ error: 'Invalid or missing mode parameter' },
				{ status: 400 }
			);
		}
		
		// Generate unique job ID
		const jobId = `modal-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
		
		// Store job in KV with initial status
		const job = {
			id: jobId,
			status: 'queued',
			mode,
			params: {
				video_names: video_names || [],
				similarity_threshold: similarity_threshold || 0.25,
				force_reprocess: force_reprocess || false,
				sync_from_hf: sync_from_hf !== false, // default true
				upload_results: upload_results !== false // default true
			},
			created_at: Date.now(),
			progress: 0,
			webhooks: [] // WebSocket client IDs
		};
		
		// Store in KV if available
		if (platform?.env?.MODAL_JOBS) {
			await platform.env.MODAL_JOBS.put(jobId, JSON.stringify(job));
		}
		
		// Trigger the Modal job asynchronously (don't await)
		// In production, this would call Modal API or queue a worker
		triggerModalJobAsync(job, platform?.env).catch(console.error);
		
		return json({
			success: true,
			job_id: jobId,
			status: 'queued',
			estimated_time_minutes: estimateProcessingTime(params)
		});
	} catch (error) {
		console.error('Error triggering Modal job:', error);
		return json(
			{ error: 'Failed to trigger processing job' },
			{ status: 500 }
		);
	}
};

// Estimate processing time based on parameters
function estimateProcessingTime(params: any): number {
	const videoCount = params.video_names?.length || 5; // Assume 5 if not specified
	const baseTimePerVideo = 3; // minutes
	const embeddingUpdateTime = 10; // minutes
	
	if (params.mode === 'embedding-update') {
		return embeddingUpdateTime;
	}
	
	return Math.ceil(videoCount * baseTimePerVideo);
}

// Async function to trigger Modal job (simulated for now)
async function triggerModalJobAsync(job: any, env: any) {
	// In production, this would:
	// 1. Call Modal API directly using modal client
	// 2. Or queue a Cloudflare Queue message
	// 3. Or spawn a Durable Object to manage the job
	
	console.log(`Triggering Modal job: ${job.id}`, job.params);
	
	// Simulate job progress updates
	let progress = 0;
	const interval = setInterval(async () => {
		progress += Math.random() * 15;
		if (progress >= 100) {
			progress = 100;
			clearInterval(interval);
		}
		
		// Update job status in KV
		if (env?.MODAL_JOBS) {
			const updatedJob = {
				...job,
				status: progress >= 100 ? 'completed' : 'running',
				progress: Math.floor(progress)
			};
			await env.MODAL_JOBS.put(job.id, JSON.stringify(updatedJob));
		}
	}, 2000);
}