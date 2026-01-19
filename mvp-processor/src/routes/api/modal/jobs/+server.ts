import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ platform }) => {
	try {
		// Check KV store availability
		if (!platform?.env?.MODAL_JOBS) {
			// Return empty list if KV not configured
			return json({ jobs: [] });
		}
		
		// List all jobs from KV
		const jobs = [];
		const list = await platform.env.MODAL_JOBS.list();
		
		for (const key of list.keys) {
			const jobData = await platform.env.MODAL_JOBS.get(key.name);
			if (jobData) {
				const job = JSON.parse(jobData);
				jobs.push({
					job_id: job.id,
					status: job.status,
					progress: job.progress || 0,
					mode: job.mode,
					created_at: job.created_at,
					current_video: job.current_video,
					error: job.error
				});
			}
		}
		
		// Sort by creation time (newest first)
		jobs.sort((a, b) => b.created_at - a.created_at);
		
		return json({ jobs });
	} catch (error) {
		console.error('Error listing jobs:', error);
		return json({ jobs: [] });
	}
};