#!/usr/bin/env node

/**
 * Parallel Test Runner
 * 
 * This script orchestrates both backend and frontend testing agents
 * to run simultaneously. It provides:
 * - Parallel execution of both testing agents
 * - Coordination and communication between agents
 * - Unified test reporting and status tracking
 * - Automatic backend startup before frontend tests
 * - Coordinated shutdown and cleanup
 * - Aggregated test results and summary generation
 */

import { spawn } from 'child_process';
import { readFileSync, writeFileSync, existsSync, mkdirSync, rmSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, '..');
const logsDir = join(projectRoot, 'logs');
const testResultsDir = join(logsDir, 'test-results');

// Ensure log directories exist
if (!existsSync(logsDir)) mkdirSync(logsDir, { recursive: true });
if (!existsSync(testResultsDir)) mkdirSync(testResultsDir, { recursive: true });

class ParallelTestRunner {
    constructor() {
        this.backendAgent = null;
        this.frontendAgent = null;
        this.testResults = {
            timestamp: new Date().toISOString(),
            runner: 'parallel',
            status: 'starting',
            agents: {},
            summary: {},
            errors: []
        };
        this.logFile = join(testResultsDir, `parallel-${Date.now()}.json`);
        this.cleanup = this.cleanup.bind(this);
    }

    async start() {
        console.log('🚀 Parallel Test Runner starting...');
        console.log('📋 Running backend and frontend tests simultaneously');
        
        // Setup signal handlers
        process.on('SIGINT', this.cleanup);
        process.on('SIGTERM', this.cleanup);
        
        try {
            // Clean up previous test results
            await this.cleanupPreviousResults();
            
            // Start both agents in parallel
            const results = await Promise.allSettled([
                this.runBackendAgent(),
                this.runFrontendAgent()
            ]);
            
            // Process results
            await this.processResults(results);
            await this.generateFinalReport();
            
        } catch (error) {
            console.error('❌ Parallel Test Runner failed:', error);
            this.testResults.status = 'failed';
            this.testResults.errors.push({
                type: 'runner_error',
                message: error.message,
                stack: error.stack,
                timestamp: new Date().toISOString()
            });
        } finally {
            await this.cleanup();
        }
    }

    async cleanupPreviousResults() {
        console.log('🧹 Cleaning up previous test results...');
        
        const summaryFiles = [
            join(testResultsDir, 'backend-summary.json'),
            join(testResultsDir, 'frontend-summary.json')
        ];
        
        for (const file of summaryFiles) {
            if (existsSync(file)) {
                rmSync(file);
            }
        }
    }

    async runBackendAgent() {
        console.log('🔧 Starting Backend Testing Agent...');
        
        return new Promise((resolve, reject) => {
            const backendScript = join(__dirname, 'test-backend-agent.js');
            
            this.backendAgent = spawn('node', [backendScript], {
                stdio: ['ignore', 'pipe', 'pipe'],
                env: {
                    ...process.env,
                    NODE_ENV: 'test'
                }
            });

            let output = '';
            let errorOutput = '';

            this.backendAgent.stdout.on('data', (data) => {
                const message = data.toString();
                output += message;
                console.log(`[Backend Agent] ${message.trim()}`);
            });

            this.backendAgent.stderr.on('data', (data) => {
                const message = data.toString();
                errorOutput += message;
                console.error(`[Backend Agent Error] ${message.trim()}`);
            });

            this.backendAgent.on('exit', (code, signal) => {
                console.log(`Backend Agent exited with code ${code} and signal ${signal}`);
                
                const result = {
                    agent: 'backend',
                    exitCode: code,
                    signal: signal,
                    success: code === 0,
                    output: output,
                    errorOutput: errorOutput,
                    timestamp: new Date().toISOString()
                };

                if (code === 0) {
                    console.log('✅ Backend Testing Agent completed successfully');
                    resolve(result);
                } else {
                    console.error('❌ Backend Testing Agent failed');
                    reject(new Error(`Backend agent failed with exit code ${code}`));
                }
            });

            this.backendAgent.on('error', (error) => {
                console.error('❌ Backend Agent process error:', error);
                reject(error);
            });
        });
    }

    async runFrontendAgent() {
        console.log('🎨 Starting Frontend Testing Agent...');
        
        return new Promise((resolve, reject) => {
            const frontendScript = join(__dirname, 'test-frontend-agent.js');
            
            this.frontendAgent = spawn('node', [frontendScript], {
                stdio: ['ignore', 'pipe', 'pipe'],
                env: {
                    ...process.env,
                    NODE_ENV: 'test'
                }
            });

            let output = '';
            let errorOutput = '';

            this.frontendAgent.stdout.on('data', (data) => {
                const message = data.toString();
                output += message;
                console.log(`[Frontend Agent] ${message.trim()}`);
            });

            this.frontendAgent.stderr.on('data', (data) => {
                const message = data.toString();
                errorOutput += message;
                console.error(`[Frontend Agent Error] ${message.trim()}`);
            });

            this.frontendAgent.on('exit', (code, signal) => {
                console.log(`Frontend Agent exited with code ${code} and signal ${signal}`);
                
                const result = {
                    agent: 'frontend',
                    exitCode: code,
                    signal: signal,
                    success: code === 0,
                    output: output,
                    errorOutput: errorOutput,
                    timestamp: new Date().toISOString()
                };

                if (code === 0) {
                    console.log('✅ Frontend Testing Agent completed successfully');
                    resolve(result);
                } else {
                    console.error('❌ Frontend Testing Agent failed');
                    reject(new Error(`Frontend agent failed with exit code ${code}`));
                }
            });

            this.frontendAgent.on('error', (error) => {
                console.error('❌ Frontend Agent process error:', error);
                reject(error);
            });
        });
    }

    async processResults(results) {
        console.log('📊 Processing test results...');
        
        this.testResults.agents = {
            backend: results[0],
            frontend: results[1]
        };

        // Determine overall status
        const backendSuccess = results[0].status === 'fulfilled';
        const frontendSuccess = results[1].status === 'fulfilled';
        
        this.testResults.status = backendSuccess && frontendSuccess ? 'passed' : 'failed';

        // Load detailed results from summary files
        await this.loadAgentSummaries();
    }

    async loadAgentSummaries() {
        console.log('📋 Loading agent summaries...');
        
        const summaryFiles = {
            backend: join(testResultsDir, 'backend-summary.json'),
            frontend: join(testResultsDir, 'frontend-summary.json')
        };

        for (const [agent, file] of Object.entries(summaryFiles)) {
            if (existsSync(file)) {
                try {
                    const summary = JSON.parse(readFileSync(file, 'utf8'));
                    this.testResults.summary[agent] = summary;
                    console.log(`✅ Loaded ${agent} summary: ${summary.status}`);
                } catch (error) {
                    console.error(`❌ Failed to load ${agent} summary:`, error);
                    this.testResults.errors.push({
                        type: 'summary_load_error',
                        agent: agent,
                        message: error.message,
                        timestamp: new Date().toISOString()
                    });
                }
            } else {
                console.warn(`⚠️ ${agent} summary file not found: ${file}`);
            }
        }
    }

    async generateFinalReport() {
        console.log('📊 Generating final test report...');
        
        // Write detailed results to file
        writeFileSync(this.logFile, JSON.stringify(this.testResults, null, 2));
        
        // Generate overall summary
        const overallSummary = this.generateOverallSummary();
        
        // Write overall summary
        const overallSummaryFile = join(testResultsDir, 'overall-summary.json');
        writeFileSync(overallSummaryFile, JSON.stringify(overallSummary, null, 2));
        
        // Display summary
        this.displaySummary(overallSummary);
        
        // Update backlog with results
        await this.updateBacklogTasks();
    }

    generateOverallSummary() {
        const backendSummary = this.testResults.summary.backend || {};
        const frontendSummary = this.testResults.summary.frontend || {};
        
        return {
            timestamp: this.testResults.timestamp,
            overallStatus: this.testResults.status,
            agents: {
                backend: {
                    status: backendSummary.status || 'unknown',
                    tests: {
                        total: backendSummary.totalTests || 0,
                        passed: backendSummary.passedTests || 0,
                        failed: backendSummary.failedTests || 0
                    },
                    performance: {
                        averageResponseTime: backendSummary.averageResponseTime || 0
                    },
                    errors: backendSummary.errors || 0
                },
                frontend: {
                    status: frontendSummary.status || 'unknown',
                    tests: {
                        total: frontendSummary.totalTests || 0,
                        passed: frontendSummary.passedTests || 0,
                        failed: frontendSummary.failedTests || 0
                    },
                    e2eStatus: frontendSummary.e2eStatus || 'unknown',
                    performance: {
                        averageResponseTime: frontendSummary.averageResponseTime || 0
                    },
                    errors: frontendSummary.errors || 0,
                    backendReady: frontendSummary.backendReady || false
                }
            },
            totals: {
                tests: (backendSummary.totalTests || 0) + (frontendSummary.totalTests || 0),
                passed: (backendSummary.passedTests || 0) + (frontendSummary.passedTests || 0),
                failed: (backendSummary.failedTests || 0) + (frontendSummary.failedTests || 0),
                errors: (backendSummary.errors || 0) + (frontendSummary.errors || 0) + this.testResults.errors.length
            },
            logFiles: {
                parallel: this.logFile,
                backend: backendSummary.logFile,
                frontend: frontendSummary.logFile
            }
        };
    }

    displaySummary(summary) {
        console.log('\n' + '='.repeat(80));
        console.log('📊 PARALLEL TEST RESULTS SUMMARY');
        console.log('='.repeat(80));
        
        console.log(`\n🎯 Overall Status: ${summary.overallStatus.toUpperCase()}`);
        console.log(`📅 Timestamp: ${summary.timestamp}`);
        
        console.log('\n🔧 Backend Agent Results:');
        console.log(`   Status: ${summary.agents.backend.status.toUpperCase()}`);
        console.log(`   Tests: ${summary.agents.backend.tests.passed}/${summary.agents.backend.tests.total} passed`);
        console.log(`   Average Response Time: ${summary.agents.backend.performance.averageResponseTime.toFixed(2)}ms`);
        console.log(`   Errors: ${summary.agents.backend.errors}`);
        
        console.log('\n🎨 Frontend Agent Results:');
        console.log(`   Status: ${summary.agents.frontend.status.toUpperCase()}`);
        console.log(`   Integration Tests: ${summary.agents.frontend.tests.passed}/${summary.agents.frontend.tests.total} passed`);
        console.log(`   E2E Tests: ${summary.agents.frontend.e2eStatus.toUpperCase()}`);
        console.log(`   Average Response Time: ${summary.agents.frontend.performance.averageResponseTime.toFixed(2)}ms`);
        console.log(`   Backend Ready: ${summary.agents.frontend.backendReady ? 'Yes' : 'No'}`);
        console.log(`   Errors: ${summary.agents.frontend.errors}`);
        
        console.log('\n📈 Overall Totals:');
        console.log(`   Total Tests: ${summary.totals.tests}`);
        console.log(`   Passed: ${summary.totals.passed}`);
        console.log(`   Failed: ${summary.totals.failed}`);
        console.log(`   Total Errors: ${summary.totals.errors}`);
        console.log(`   Success Rate: ${((summary.totals.passed / summary.totals.tests) * 100).toFixed(1)}%`);
        
        console.log('\n📁 Log Files:');
        console.log(`   Parallel Runner: ${summary.logFiles.parallel}`);
        if (summary.logFiles.backend) console.log(`   Backend Agent: ${summary.logFiles.backend}`);
        if (summary.logFiles.frontend) console.log(`   Frontend Agent: ${summary.logFiles.frontend}`);
        
        console.log('\n' + '='.repeat(80));
    }

    async updateBacklogTasks() {
        console.log('📋 Updating backlog tasks...');
        
        try {
            const backendStatus = this.testResults.summary.backend?.status === 'passed' ? 'Done' : 'In Progress';
            const frontendStatus = this.testResults.summary.frontend?.status === 'passed' ? 'Done' : 'In Progress';
            const parallelStatus = this.testResults.status === 'passed' ? 'Done' : 'In Progress';
            
            // Update task statuses
            if (backendStatus === 'Done') {
                await this.updateBacklogTask('012', 'Done', 'Backend testing agent completed successfully with all tests passing');
            }
            
            if (frontendStatus === 'Done') {
                await this.updateBacklogTask('013', 'Done', 'Frontend testing agent completed successfully with integration and E2E tests passing');
            }
            
            if (parallelStatus === 'Done') {
                await this.updateBacklogTask('014', 'Done', 'Parallel test runner completed successfully with both agents running simultaneously');
            }
            
        } catch (error) {
            console.error('❌ Failed to update backlog tasks:', error);
        }
    }

    async updateBacklogTask(taskId, status, notes) {
        return new Promise((resolve, reject) => {
            const process = spawn('backlog', ['task', 'edit', taskId, '-s', status, '--notes', notes], {
                stdio: ['ignore', 'pipe', 'pipe']
            });

            process.on('exit', (code) => {
                if (code === 0) {
                    console.log(`✅ Updated task ${taskId} to ${status}`);
                    resolve();
                } else {
                    console.error(`❌ Failed to update task ${taskId}`);
                    reject(new Error(`Backlog update failed with exit code ${code}`));
                }
            });

            process.on('error', (error) => {
                console.error(`❌ Error updating task ${taskId}:`, error);
                reject(error);
            });
        });
    }

    async cleanup() {
        console.log('\n🧹 Cleaning up parallel test runner...');
        
        // Kill agents if still running
        if (this.backendAgent && !this.backendAgent.killed) {
            console.log('🔧 Terminating backend agent...');
            this.backendAgent.kill('SIGTERM');
            
            // Force kill after 5 seconds
            setTimeout(() => {
                if (!this.backendAgent.killed) {
                    this.backendAgent.kill('SIGKILL');
                }
            }, 5000);
        }
        
        if (this.frontendAgent && !this.frontendAgent.killed) {
            console.log('🎨 Terminating frontend agent...');
            this.frontendAgent.kill('SIGTERM');
            
            // Force kill after 5 seconds
            setTimeout(() => {
                if (!this.frontendAgent.killed) {
                    this.frontendAgent.kill('SIGKILL');
                }
            }, 5000);
        }
        
        console.log('✅ Parallel Test Runner cleanup completed');
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

// Run the parallel test runner
if (import.meta.url === `file://${process.argv[1]}`) {
    const runner = new ParallelTestRunner();
    runner.start().catch(console.error);
}

export default ParallelTestRunner;
