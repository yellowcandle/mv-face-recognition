#!/usr/bin/env node

/**
 * Backend Testing Agent
 * 
 * This script orchestrates automated testing of the Cloudflare Worker backend.
 * It handles:
 * - Starting the worker in development mode
 * - Running comprehensive API tests
 * - Monitoring worker health and performance
 * - Logging test results for tracking
 */

import { spawn } from 'child_process';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, '..');
const logsDir = join(projectRoot, 'logs');
const testResultsDir = join(logsDir, 'test-results');

// Ensure log directories exist
if (!existsSync(logsDir)) mkdirSync(logsDir, { recursive: true });
if (!existsSync(testResultsDir)) mkdirSync(testResultsDir, { recursive: true });

class BackendTestingAgent {
    constructor() {
        this.workerProcess = null;
        this.testResults = {
            timestamp: new Date().toISOString(),
            agent: 'backend',
            status: 'starting',
            tests: [],
            performance: {},
            errors: []
        };
        this.workerUrl = 'http://localhost:8787';
        this.healthCheckInterval = null;
        this.testLogFile = join(testResultsDir, `backend-${Date.now()}.json`);
    }

    async start() {
        console.log('🚀 Backend Testing Agent starting...');
        
        try {
            await this.startWorker();
            await this.waitForWorkerReady();
            await this.runTests();
            await this.generateReport();
        } catch (error) {
            console.error('❌ Backend Testing Agent failed:', error);
            this.testResults.status = 'failed';
            this.testResults.errors.push({
                type: 'agent_error',
                message: error.message,
                stack: error.stack,
                timestamp: new Date().toISOString()
            });
        } finally {
            await this.cleanup();
        }
    }

    async startWorker() {
        console.log('⚡ Starting Cloudflare Worker in dev mode...');
        
        return new Promise((resolve, reject) => {
            const workerDir = join(projectRoot, 'worker');
            
            this.workerProcess = spawn('npm', ['run', 'dev'], {
                cwd: workerDir,
                stdio: ['ignore', 'pipe', 'pipe']
            });

            let output = '';
            let started = false;

            this.workerProcess.stdout.on('data', (data) => {
                output += data.toString();
                console.log(`[Worker] ${data.toString().trim()}`);
                
                // Look for success indicators
                if (output.includes('Ready on') || output.includes('listening on')) {
                    if (!started) {
                        started = true;
                        resolve();
                    }
                }
            });

            this.workerProcess.stderr.on('data', (data) => {
                console.error(`[Worker Error] ${data.toString().trim()}`);
                this.testResults.errors.push({
                    type: 'worker_startup_error',
                    message: data.toString(),
                    timestamp: new Date().toISOString()
                });
            });

            this.workerProcess.on('exit', (code, signal) => {
                console.log(`Worker process exited with code ${code} and signal ${signal}`);
                if (!started) {
                    reject(new Error(`Worker failed to start. Exit code: ${code}`));
                }
            });

            // Timeout after 30 seconds
            setTimeout(() => {
                if (!started) {
                    reject(new Error('Worker startup timeout'));
                }
            }, 30000);
        });
    }

    async waitForWorkerReady() {
        console.log('⏳ Waiting for worker to be ready...');
        
        const maxAttempts = 30;
        const delay = 1000;
        
        for (let i = 0; i < maxAttempts; i++) {
            try {
                const response = await fetch(`${this.workerUrl}/api/system/status`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.status === 'healthy') {
                        console.log('✅ Worker is ready and healthy');
                        return;
                    }
                }
            } catch (error) {
                // Continue retrying
            }
            
            await new Promise(resolve => setTimeout(resolve, delay));
        }
        
        throw new Error('Worker health check timeout');
    }

    async runTests() {
        console.log('🧪 Running comprehensive API tests...');
        
        const testSuites = [
            { name: 'System Status', endpoint: '/api/system/status', method: 'GET' },
            { name: 'Videos List', endpoint: '/api/videos', method: 'GET' },
            { name: 'Contestants', endpoint: '/api/contestants', method: 'GET' },
            { name: 'Recognition Results', endpoint: '/api/recognition/results', method: 'GET' },
            { name: 'Analytics Overview', endpoint: '/api/analytics/overview', method: 'GET' },
            { name: 'Settings', endpoint: '/api/settings', method: 'GET' }
        ];

        const testResults = [];
        
        for (const suite of testSuites) {
            try {
                const result = await this.runTestSuite(suite);
                testResults.push(result);
                console.log(`${result.passed ? '✅' : '❌'} ${suite.name}: ${result.passed ? 'PASSED' : 'FAILED'}`);
            } catch (error) {
                console.error(`❌ ${suite.name}: ERROR - ${error.message}`);
                testResults.push({
                    name: suite.name,
                    passed: false,
                    error: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        }

        this.testResults.tests = testResults;
        this.testResults.status = testResults.every(t => t.passed) ? 'passed' : 'failed';
        
        // Run performance tests
        await this.runPerformanceTests();
    }

    async runTestSuite(suite) {
        const startTime = Date.now();
        
        try {
            const response = await fetch(`${this.workerUrl}${suite.endpoint}`, {
                method: suite.method,
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const endTime = Date.now();
            const responseTime = endTime - startTime;
            
            const result = {
                name: suite.name,
                endpoint: suite.endpoint,
                method: suite.method,
                status: response.status,
                responseTime,
                passed: response.ok,
                timestamp: new Date().toISOString()
            };

            // Additional validations based on endpoint
            if (response.ok) {
                const data = await response.json();
                result.responseData = data;
                
                // Validate response structure
                switch (suite.endpoint) {
                    case '/api/system/status':
                        result.passed = data.status === 'healthy' && data.features && data.stats;
                        break;
                    case '/api/videos':
                        result.passed = Array.isArray(data.videos);
                        break;
                    case '/api/contestants':
                        result.passed = Array.isArray(data.contestants);
                        break;
                    case '/api/recognition/results':
                        result.passed = data.results && data.pagination;
                        break;
                    case '/api/analytics/overview':
                        result.passed = data.overview && data.performance;
                        break;
                    case '/api/settings':
                        result.passed = data.processing && data.display;
                        break;
                }
            }

            return result;
        } catch (error) {
            const endTime = Date.now();
            return {
                name: suite.name,
                endpoint: suite.endpoint,
                method: suite.method,
                passed: false,
                error: error.message,
                responseTime: endTime - startTime,
                timestamp: new Date().toISOString()
            };
        }
    }

    async runPerformanceTests() {
        console.log('⚡ Running performance tests...');
        
        const performanceTests = [
            { name: 'Status Endpoint Load', endpoint: '/api/system/status', requests: 50 },
            { name: 'Videos Endpoint Load', endpoint: '/api/videos', requests: 20 },
            { name: 'Recognition Results Load', endpoint: '/api/recognition/results', requests: 30 }
        ];

        const performanceResults = {};
        
        for (const test of performanceTests) {
            try {
                const result = await this.runLoadTest(test);
                performanceResults[test.name] = result;
                console.log(`⚡ ${test.name}: avg ${result.averageResponseTime}ms, max ${result.maxResponseTime}ms`);
            } catch (error) {
                performanceResults[test.name] = { error: error.message };
                console.error(`❌ ${test.name}: ${error.message}`);
            }
        }

        this.testResults.performance = performanceResults;
    }

    async runLoadTest(test) {
        const promises = [];
        const results = [];
        
        for (let i = 0; i < test.requests; i++) {
            promises.push(
                (async () => {
                    const startTime = Date.now();
                    try {
                        const response = await fetch(`${this.workerUrl}${test.endpoint}`);
                        const endTime = Date.now();
                        return {
                            status: response.status,
                            responseTime: endTime - startTime,
                            success: response.ok
                        };
                    } catch (error) {
                        return {
                            error: error.message,
                            success: false,
                            responseTime: Date.now() - startTime
                        };
                    }
                })()
            );
        }
        
        const responses = await Promise.all(promises);
        const successfulResponses = responses.filter(r => r.success);
        const responseTimes = successfulResponses.map(r => r.responseTime);
        
        return {
            totalRequests: test.requests,
            successfulRequests: successfulResponses.length,
            failedRequests: responses.length - successfulResponses.length,
            averageResponseTime: responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length,
            maxResponseTime: Math.max(...responseTimes),
            minResponseTime: Math.min(...responseTimes),
            successRate: (successfulResponses.length / responses.length) * 100
        };
    }

    async generateReport() {
        console.log('📊 Generating test report...');
        
        // Write detailed results to file
        writeFileSync(this.testLogFile, JSON.stringify(this.testResults, null, 2));
        
        // Generate summary
        const summary = {
            timestamp: this.testResults.timestamp,
            agent: 'backend',
            status: this.testResults.status,
            totalTests: this.testResults.tests.length,
            passedTests: this.testResults.tests.filter(t => t.passed).length,
            failedTests: this.testResults.tests.filter(t => !t.passed).length,
            averageResponseTime: this.testResults.tests.reduce((sum, t) => sum + (t.responseTime || 0), 0) / this.testResults.tests.length,
            errors: this.testResults.errors.length,
            logFile: this.testLogFile
        };
        
        // Write summary for parallel test runner
        const summaryFile = join(testResultsDir, 'backend-summary.json');
        writeFileSync(summaryFile, JSON.stringify(summary, null, 2));
        
        console.log('\n📊 Backend Test Summary:');
        console.log(`Status: ${summary.status.toUpperCase()}`);
        console.log(`Tests: ${summary.passedTests}/${summary.totalTests} passed`);
        console.log(`Average Response Time: ${summary.averageResponseTime.toFixed(2)}ms`);
        console.log(`Errors: ${summary.errors}`);
        console.log(`Log file: ${this.testLogFile}`);
    }

    async cleanup() {
        console.log('🧹 Cleaning up...');
        
        if (this.healthCheckInterval) {
            clearInterval(this.healthCheckInterval);
        }
        
        if (this.workerProcess) {
            this.workerProcess.kill('SIGTERM');
            
            // Wait for graceful shutdown
            await new Promise(resolve => {
                this.workerProcess.on('exit', resolve);
                setTimeout(() => {
                    this.workerProcess.kill('SIGKILL');
                    resolve();
                }, 5000);
            });
        }
        
        console.log('✅ Backend Testing Agent completed');
    }
}

// Handle process signals
process.on('SIGINT', () => {
    console.log('\n🛑 Received SIGINT, shutting down gracefully...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('\n🛑 Received SIGTERM, shutting down gracefully...');
    process.exit(0);
});

// Run the agent
if (import.meta.url === `file://${process.argv[1]}`) {
    const agent = new BackendTestingAgent();
    agent.start().catch(console.error);
}

export default BackendTestingAgent;
