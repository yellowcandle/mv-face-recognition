import { Router } from 'itty-router';
import { 
  createModalJob, 
  getModalJob, 
  listModalJobs, 
  cancelModalJob,
  clearCompletedJobs
} from '../api/modal';

const router = Router();

/**
 * POST /api/modal/trigger-processing
 * Trigger a new Modal processing job
 */
router.post('/api/modal/trigger-processing', async (request, env) => {
  try {
    const params = await request.json();
    const result = await createModalJob(env, params);
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error in trigger-processing:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: error.status || 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
});

/**
 * GET /api/modal/job/:id
 * Get status of a specific job
 */
router.get('/api/modal/job/:id', async (request, env) => {
  try {
    const { id } = request.params;
    const result = await getModalJob(env, id);
    
    if (result.error) {
      return new Response(JSON.stringify(result), {
        status: result.status || 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error in get job:', error);
    return new Response(JSON.stringify({ error: 'Failed to fetch job' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
});

/**
 * DELETE /api/modal/job/:id
 * Cancel a job
 */
router.delete('/api/modal/job/:id', async (request, env) => {
  try {
    const { id } = request.params;
    const result = await cancelModalJob(env, id);
    
    if (result.error) {
      return new Response(JSON.stringify(result), {
        status: result.status || 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error in cancel job:', error);
    return new Response(JSON.stringify({ error: 'Failed to cancel job' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
});

/**
 * GET /api/modal/jobs
 * List all jobs
 */
router.get('/api/modal/jobs', async (request, env) => {
  try {
    const result = await listModalJobs(env);
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error listing jobs:', error);
    return new Response(JSON.stringify({ error: 'Failed to list jobs' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
});

/**
 * POST /api/modal/jobs/clear-completed
 * Clear completed jobs
 */
router.post('/api/modal/jobs/clear-completed', async (request, env) => {
  try {
    const result = await clearCompletedJobs(env);
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error clearing completed jobs:', error);
    return new Response(JSON.stringify({ error: 'Failed to clear completed jobs' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
});

export default router;