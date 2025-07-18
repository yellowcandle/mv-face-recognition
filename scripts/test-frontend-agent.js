#!/usr/bin/env node

/**
 * Frontend Integration Testing Agent
 * 
 * This script orchestrates automated testing of the SvelteKit frontend
 * with real backend integration. It handles:
 * - Starting the frontend dev server
 * - Connecting to the backend testing agent
 * - Running integration tests against real APIs
 * - Executing E2E tests for user workflows
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

class FrontendTestingAgent {
    constructor() {
        this.frontendProcess = null;
        this.testResults = {
            timestamp: new Date().toISOString(),
            agent: 'frontend',
            status: 'starting',
            tests: [],
            e2eResults: [],
            performance: {},
            errors: []
        };
        this.frontendUrl = 'http://localhost:5173';
        this.backendUrl = 'http://localhost:8787';
        this.testLogFile = join(testResultsDir, `frontend-${Date.now()}.json`);
        this.backendReady = false;
    }

    async start() {
        console.log('🚀 Frontend Testing Agent starting...');
        
        try {
            await this.waitForBackend();
            await this.startFrontend();
            await this.waitForFrontendReady();
            await this.runIntegrationTests();
            await this.runE2ETests();
            await this.generateReport();
        } catch (error) {
            console.error('❌ Frontend Testing Agent failed:', error);
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

    async waitForBackend() {
        console.log('⏳ Waiting for backend to be ready...');
        
        const maxAttempts = 60;
        const delay = 1000;
        
        for (let i = 0; i < maxAttempts; i++) {
            try {
                // Check if backend summary exists
                const summaryFile = join(testResultsDir, 'backend-summary.json');
                if (existsSync(summaryFile)) {
                    const summary = JSON.parse(readFileSync(summaryFile, 'utf8'));
                    if (summary.status === 'passed') {
                        console.log('✅ Backend is ready and healthy');
                        this.backendReady = true;
                        return;
                    }
                }
                
                // Direct backend health check
                const response = await fetch(`${this.backendUrl}/api/system/status`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.status === 'healthy') {
                        console.log('✅ Backend is ready and healthy');
                        this.backendReady = true;
                        return;
                    }
                }
            } catch (error) {
                // Continue retrying
            }
            
            await new Promise(resolve => setTimeout(resolve, delay));
        }
        
        throw new Error('Backend not ready - frontend tests cannot proceed');
    }

    async startFrontend() {
        console.log('⚡ Starting SvelteKit frontend dev server...');
        
        return new Promise((resolve, reject) => {
            const frontendDir = join(projectRoot, 'frontend');
            
            this.frontendProcess = spawn('npm', ['run', 'dev'], {
                cwd: frontendDir,
                stdio: ['ignore', 'pipe', 'pipe'],
                env: {
                    ...process.env,
                    NODE_ENV: 'test',
                    BACKEND_URL: this.backendUrl,
                    VITE_BACKEND_URL: this.backendUrl
                }
            });

            let output = '';
            let started = false;

            this.frontendProcess.stdout.on('data', (data) => {
                output += data.toString();
                console.log(`[Frontend] ${data.toString().trim()}`);
                
                // Look for success indicators
                if (output.includes('Local:') || output.includes('ready in')) {
                    if (!started) {
                        started = true;
                        resolve();
                    }
                }
            });

            this.frontendProcess.stderr.on('data', (data) => {
                const message = data.toString();
                console.error(`[Frontend Error] ${message.trim()}`);
                
                // Don't treat warnings as errors
                if (!message.includes('warning') && !message.includes('deprecated')) {
                    this.testResults.errors.push({
                        type: 'frontend_startup_error',
                        message: message,
                        timestamp: new Date().toISOString()
                    });
                }
            });

            this.frontendProcess.on('exit', (code, signal) => {
                console.log(`Frontend process exited with code ${code} and signal ${signal}`);
                if (!started) {
                    reject(new Error(`Frontend failed to start. Exit code: ${code}`));
                }
            });

            // Timeout after 45 seconds
            setTimeout(() => {
                if (!started) {
                    reject(new Error('Frontend startup timeout'));
                }
            }, 45000);
        });
    }

    async waitForFrontendReady() {
        console.log('⏳ Waiting for frontend to be ready...');
        
        const maxAttempts = 30;
        const delay = 1000;
        
        for (let i = 0; i < maxAttempts; i++) {
            try {
                const response = await fetch(this.frontendUrl);
                if (response.ok) {
                    console.log('✅ Frontend is ready');
                    return;
                }
            } catch (error) {
                // Continue retrying
            }
            
            await new Promise(resolve => setTimeout(resolve, delay));
        }
        
        throw new Error('Frontend health check timeout');
    }

    async runIntegrationTests() {
        console.log('🧪 Running integration tests...');
        
        const integrationTests = [
            {
                name: 'Frontend-Backend Connection',
                test: () => this.testBackendConnection()
            },
            {
                name: 'Video Data Loading',
                test: () => this.testVideoDataLoading()
            },
            {
                name: 'Contestant Data Integration',
                test: () => this.testContestantDataIntegration()
            },
            {
                name: 'Recognition Results Display',
                test: () => this.testRecognitionResultsDisplay()
            },
            {
                name: 'Analytics Data Integration',
                test: () => this.testAnalyticsDataIntegration()
            }
        ];

        const testResults = [];
        
        for (const testCase of integrationTests) {
            try {
                const result = await testCase.test();
                testResults.push({
                    name: testCase.name,
                    passed: result.passed,
                    details: result.details,
                    responseTime: result.responseTime,
                    timestamp: new Date().toISOString()
                });
                console.log(`${result.passed ? '✅' : '❌'} ${testCase.name}: ${result.passed ? 'PASSED' : 'FAILED'}`);
                if (!result.passed) {
                    console.log(`   Details: ${result.details}`);
                }
            } catch (error) {
                console.error(`❌ ${testCase.name}: ERROR - ${error.message}`);
                testResults.push({
                    name: testCase.name,
                    passed: false,
                    error: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        }

        this.testResults.tests = testResults;
        this.testResults.status = testResults.every(t => t.passed) ? 'passed' : 'failed';
    }

    async testBackendConnection() {
        const startTime = Date.now();
        
        try {
            // Test that frontend can reach backend
            const response = await fetch(`${this.frontendUrl}/api/system/status`);
            const responseTime = Date.now() - startTime;
            
            if (response.ok) {
                const data = await response.json();
                return {
                    passed: data.status === 'healthy',
                    details: `Backend status: ${data.status}`,
                    responseTime
                };
            } else {
                return {
                    passed: false,
                    details: `HTTP ${response.status}: ${response.statusText}`,
                    responseTime
                };
            }
        } catch (error) {
            return {
                passed: false,
                details: `Connection error: ${error.message}`,
                responseTime: Date.now() - startTime
            };
        }
    }

    async testVideoDataLoading() {
        const startTime = Date.now();
        
        try {
            const response = await fetch(`${this.frontendUrl}/api/videos`);
            const responseTime = Date.now() - startTime;
            
            if (response.ok) {
                const data = await response.json();
                const hasVideos = Array.isArray(data.videos);
                
                return {
                    passed: hasVideos,
                    details: `Videos loaded: ${hasVideos ? data.videos.length : 0}`,
                    responseTime
                };
            } else {
                return {
                    passed: false,
                    details: `HTTP ${response.status}: ${response.statusText}`,
                    responseTime
                };
            }
        } catch (error) {
            return {
                passed: false,
                details: `Video loading error: ${error.message}`,
                responseTime: Date.now() - startTime
            };
        }
    }

    async testContestantDataIntegration() {
        const startTime = Date.now();
        
        try {
            const response = await fetch(`${this.frontendUrl}/api/contestants`);
            const responseTime = Date.now() - startTime;
            
            if (response.ok) {
                const data = await response.json();
                const hasContestants = Array.isArray(data.contestants);
                
                return {
                    passed: hasContestants,
                    details: `Contestants loaded: ${hasContestants ? data.contestants.length : 0}`,
                    responseTime
                };
            } else {
                return {
                    passed: false,
                    details: `HTTP ${response.status}: ${response.statusText}`,
                    responseTime
                };
            }
        } catch (error) {
            return {
                passed: false,
                details: `Contestant loading error: ${error.message}`,
                responseTime: Date.now() - startTime
            };
        }
    }

    async testRecognitionResultsDisplay() {
        const startTime = Date.now();
        
        try {
            const response = await fetch(`${this.frontendUrl}/api/recognition/results`);
            const responseTime = Date.now() - startTime;
            
            if (response.ok) {
                const data = await response.json();
                const hasResults = data.results && data.pagination;
                
                return {
                    passed: hasResults,
                    details: `Recognition results structure valid: ${hasResults}`,
                    responseTime
                };
            } else {
                return {
                    passed: false,
                    details: `HTTP ${response.status}: ${response.statusText}`,
                    responseTime
                };
            }
        } catch (error) {
            return {
                passed: false,
                details: `Recognition results error: ${error.message}`,
                responseTime: Date.now() - startTime
            };
        }
    }

    async testAnalyticsDataIntegration() {
        const startTime = Date.now();
        
        try {
            const response = await fetch(`${this.frontendUrl}/api/analytics/overview`);
            const responseTime = Date.now() - startTime;
            
            if (response.ok) {
                const data = await response.json();
                const hasAnalytics = data.overview && data.performance;
                
                return {
                    passed: hasAnalytics,
                    details: `Analytics data structure valid: ${hasAnalytics}`,
                    responseTime
                };
            } else {
                return {
                    passed: false,
                    details: `HTTP ${response.status}: ${response.statusText}`,
                    responseTime
                };
            }
        } catch (error) {
            return {
                passed: false,
                details: `Analytics loading error: ${error.message}`,
                responseTime: Date.now() - startTime
            };
        }
    }

    async runE2ETests() {
        console.log('🎭 Running E2E tests...');
        
        return new Promise((resolve, reject) => {
            const frontendDir = join(projectRoot, 'frontend');
            
            const e2eProcess = spawn('npm', ['run', 'test:e2e'], {
                cwd: frontendDir,
                stdio: ['ignore', 'pipe', 'pipe'],
                env: {
                    ...process.env,
                    BASE_URL: this.frontendUrl,
                    BACKEND_URL: this.backendUrl
                }
            });

            let output = '';
            let errorOutput = '';

            e2eProcess.stdout.on('data', (data) => {
                output += data.toString();
                console.log(`[E2E] ${data.toString().trim()}`);
            });

            e2eProcess.stderr.on('data', (data) => {
                errorOutput += data.toString();
                console.error(`[E2E Error] ${data.toString().trim()}`);
            });

            e2eProcess.on('exit', (code, signal) => {
                const e2eResults = {
                    exitCode: code,
                    passed: code === 0,
                    output: output,
                    errorOutput: errorOutput,
                    timestamp: new Date().toISOString()
                };

                this.testResults.e2eResults = e2eResults;
                
                if (code === 0) {
                    console.log('✅ E2E tests passed');
                } else {
                    console.log(`❌ E2E tests failed with exit code ${code}`);
                    this.testResults.status = 'failed';
                }
                
                resolve(e2eResults);
            });

            // Timeout after 5 minutes
            setTimeout(() => {
                e2eProcess.kill('SIGTERM');
                reject(new Error('E2E tests timeout'));
            }, 300000);
        });
    }

    async generateReport() {
        console.log('📊 Generating frontend test report...');
        
        // Write detailed results to file
        writeFileSync(this.testLogFile, JSON.stringify(this.testResults, null, 2));
        
        // Generate summary
        const summary = {
            timestamp: this.testResults.timestamp,
            agent: 'frontend',
            status: this.testResults.status,
            totalTests: this.testResults.tests.length,
            passedTests: this.testResults.tests.filter(t => t.passed).length,
            failedTests: this.testResults.tests.filter(t => !t.passed).length,
            e2eStatus: this.testResults.e2eResults.passed ? 'passed' : 'failed',
            averageResponseTime: this.testResults.tests.reduce((sum, t) => sum + (t.responseTime || 0), 0) / this.testResults.tests.length,
            errors: this.testResults.errors.length,
            backendReady: this.backendReady,
            logFile: this.testLogFile
        };
        
        // Write summary for parallel test runner
        const summaryFile = join(testResultsDir, 'frontend-summary.json');
        writeFileSync(summaryFile, JSON.stringify(summary, null, 2));
        
        console.log('\n📊 Frontend Test Summary:');
        console.log(`Status: ${summary.status.toUpperCase()}`);
        console.log(`Integration Tests: ${summary.passedTests}/${summary.totalTests} passed`);
        console.log(`E2E Tests: ${summary.e2eStatus.toUpperCase()}`);
        console.log(`Average Response Time: ${summary.averageResponseTime.toFixed(2)}ms`);
        console.log(`Errors: ${summary.errors}`);
        console.log(`Backend Ready: ${summary.backendReady ? 'Yes' : 'No'}`);
        console.log(`Log file: ${this.testLogFile}`);
    }

    async cleanup() {
        console.log('🧹 Cleaning up...');
        
        if (this.frontendProcess) {
            this.frontendProcess.kill('SIGTERM');
            
            // Wait for graceful shutdown
            await new Promise(resolve => {
                this.frontendProcess.on('exit', resolve);
                setTimeout(() => {
                    this.frontendProcess.kill('SIGKILL');
                    resolve();
                }, 5000);
            });
        }
        
        console.log('✅ Frontend Testing Agent completed');
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
    const agent = new FrontendTestingAgent();
    agent.start().catch(console.error);
}

export default FrontendTestingAgent;
