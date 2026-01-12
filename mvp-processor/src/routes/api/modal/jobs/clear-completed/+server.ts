import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ platform }) => {
	try {
		if (!platform?.env?.MODAL_JOBS) {
			return json({ success: true, cleared: 0 });
		}
		
		// List all jobs
		const list = await platform.env.MODAL_JOBS.list();
		let cleared = 0;
		
		for (const key of list.keys) {
			const jobData = await platform.env.MODAL_JOBS.get(key.name);
			if (jobData) {
				const job = JSON.parse(jobData);
				// Remove completed/failed/cancelled jobs
				if (['completed', 'failed', 'cancelled'].includes(job.status)) {
					await platform.env.MODAL_JOBS.delete(key.name);
					cleared++;
				}
			}
		}
		
		return json({ success: true, cleared });
	} catch (error) {
		console.error('Error clearing completed jobs:', error);
		return json({ error: 'Failed to clear completed jobs' }, { status: 500 });
	}
};