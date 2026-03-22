import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, platform }) => {
	try {
		const { id } = params;
		
		if (!id) {
			return json({ error: 'Job ID is required' }, { status: 400 });
		}
		
		// Get job from KV store
		if (!platform?.env?.MODAL_JOBS) {
			return json({ error: 'Job storage not available' }, { status: 500 });
		}
		
		const jobData = await platform.env.MODAL_JOBS.get(id);
		
		if (!jobData) {
			return json({ error: 'Job not found' }, { status: 404 });
		}
		
		const job = JSON.parse(jobData);
		
		return json({
			job_id: job.id,
			status: job.status,
			progress: job.progress || 0,
			current_video: job.current_video,
			videos_processed: job.videos_processed || 0,
			total_videos: job.total_videos || job.params.video_names?.length || 1,
			created_at: job.created_at,
			started_at: job.started_at,
			completed_at: job.completed_at,
			results: job.results,
			error: job.error,
			mode: job.mode
		});
	} catch (error) {
		console.error(`Error fetching job ${params.id}:`, error);
		return json({ error: 'Failed to fetch job status' }, { status: 500 });
	}
};

export const DELETE: RequestHandler = async ({ params, platform }) => {
	try {
		const { id } = params;
		
		if (!id) {
			return json({ error: 'Job ID is required' }, { status: 400 });
		}
		
		// Get current job
		if (!platform?.env?.MODAL_JOBS) {
			return json({ error: 'Job storage not available' }, { status: 500 });
		}
		
		const jobData = await platform.env.MODAL_JOBS.get(id);
		if (!jobData) {
			return json({ error: 'Job not found' }, { status: 404 });
		}
		
		const job = JSON.parse(jobData);
		
		// Only allow cancelling queued or running jobs
		if (!['queued', 'running'].includes(job.status)) {
			return json({ error: 'Job cannot be cancelled in current state' }, { status: 400 });
		}
		
		// Update job status to cancelled
		job.status = 'cancelled';
		job.completed_at = Date.now();
		
		await platform.env.MODAL_JOBS.put(id, JSON.stringify(job));
		
		return json({
			success: true,
			job_id: id,
			status: 'cancelled'
		});
	} catch (error) {
		console.error(`Error cancelling job ${params.id}:`, error);
		return json({ error: 'Failed to cancel job' }, { status: 500 });
	}
};