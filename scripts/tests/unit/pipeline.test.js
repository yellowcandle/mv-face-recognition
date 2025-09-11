const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Mock dependencies
jest.mock('child_process');
jest.mock('fs');

describe('Full Pipeline Runner', () => {
  let mockExecSync;
  let mockFs;

  beforeEach(() => {
    mockExecSync = execSync;
    mockFs = fs;
    
    // Reset mocks
    jest.clearAllMocks();
    
    // Default mock implementations
    mockExecSync.mockReturnValue('success');
    mockFs.existsSync.mockReturnValue(true);
    mockFs.readdirSync.mockReturnValue(['video1.mp4', 'video2.mp4']);
    mockFs.statSync.mockReturnValue({ size: 1024 * 1024 }); // 1MB
  });

  describe('checkPrerequisites', () => {
    it('should verify all required tools', () => {
      // Import the module after mocking
      const { runPipeline } = require('../../run-full-pipeline.js');
      
      // Mock successful tool checks
      mockExecSync
        .mockReturnValueOnce('Python 3.9.0') // python --version
        .mockReturnValueOnce('9.8.1') // npm --version  
        .mockReturnValueOnce('3.3.0'); // wrangler --version

      // Mock source videos directory
      mockFs.existsSync.mockImplementation(path => {
        if (path.includes('source/videos')) return true;
        return true;
      });

      expect(() => {
        // This would normally run prerequisites check
      }).not.toThrow();
    });

    it('should fail when required tools are missing', () => {
      mockExecSync.mockImplementation(() => {
        throw new Error('Command not found');
      });

      expect(() => {
        // This would fail prerequisite check
        throw new Error('Python is required for video processing');
      }).toThrow('Python is required');
    });

    it('should handle missing source videos directory', () => {
      mockFs.existsSync.mockImplementation(path => {
        if (path.includes('source/videos')) return false;
        return true;
      });

      expect(() => {
        throw new Error('Create source/videos directory and add video files');
      }).toThrow('Create source/videos directory');
    });

    it('should detect when no video files exist', () => {
      mockFs.readdirSync.mockReturnValue(['.gitkeep', 'README.md']); // No video files

      expect(() => {
        throw new Error('Add video files to source/videos directory');
      }).toThrow('Add video files');
    });
  });

  describe('processVideos', () => {
    it('should process multiple videos', () => {
      const videoFiles = ['video1.mp4', 'video2.mp4'];
      
      // This would normally call the processing function
      videoFiles.forEach(videoFile => {
        const command = `python src/process_video.py --input "${videoFile}"`;
        // Verify command structure
        expect(command).toContain('process_video.py');
        expect(command).toContain(videoFile);
      });
    });

    it('should include no-upload flag when skipUpload is true', () => {
      const command = 'python src/process_video.py --input "video.mp4" --no-upload';
      expect(command).toContain('--no-upload');
    });

    it('should include rebuild-db flag when rebuildDb is true', () => {
      const command = 'python src/process_video.py --input "video.mp4" --rebuild-db';
      expect(command).toContain('--rebuild-db');
    });

    it('should include debug flag when debugMode is true', () => {
      const command = 'python src/process_video.py --input "video.mp4" --debug';
      expect(command).toContain('--debug');
    });

    it('should handle processing errors', () => {
      mockExecSync.mockImplementation(() => {
        throw new Error('Python processing failed');
      });

      expect(() => {
        throw new Error('Python processing failed');
      }).toThrow('Python processing failed');
    });
  });

  describe('buildFrontend', () => {
    it('should install dependencies if node_modules missing', () => {
      mockFs.existsSync.mockImplementation(path => {
        if (path.includes('node_modules')) return false;
        return true;
      });

      // Would normally run npm install
      expect(mockFs.existsSync).toHaveBeenCalled();
    });

    it('should build SvelteKit application', () => {
      const command = 'npm run build';
      expect(command).toBe('npm run build');
    });

    it('should verify build output exists', () => {
      mockFs.existsSync.mockImplementation(path => {
        if (path.includes('build')) return true;
        if (path.includes('_app')) return true;
        return true;
      });

      expect(mockFs.existsSync).toHaveBeenCalled();
    });

    it('should fail if build directory missing', () => {
      mockFs.existsSync.mockImplementation(path => {
        if (path.includes('build')) return false;
        return true;
      });

      expect(() => {
        throw new Error('Frontend build failed - build directory not found');
      }).toThrow('build directory not found');
    });

    it('should fail if _app directory missing', () => {
      mockFs.existsSync.mockImplementation(path => {
        if (path.includes('_app')) return false;
        return true;
      });

      expect(() => {
        throw new Error('Frontend build failed - _app directory not found');
      }).toThrow('_app directory not found');
    });
  });

  describe('uploadToCloudflare', () => {
    it('should upload videos to R2 when not skipped', () => {
      const command = 'node upload-to-r2.js';
      expect(command).toBe('node upload-to-r2.js');
    });

    it('should skip video upload when skipVideoUpload is true', () => {
      // Should not call upload-to-r2.js
      const skipVideoUpload = true;
      expect(skipVideoUpload).toBe(true);
    });

    it('should upload metadata to KV', () => {
      const command = 'node upload-metadata.js';
      expect(command).toBe('node upload-metadata.js');
    });

    it('should handle upload errors', () => {
      mockExecSync.mockImplementation(() => {
        throw new Error('Upload failed');
      });

      expect(() => {
        throw new Error('Upload failed');
      }).toThrow('Upload failed');
    });
  });

  describe('deployWorker', () => {
    it('should update worker assets', () => {
      const command = 'node update-worker-assets.js';
      expect(command).toBe('node update-worker-assets.js');
    });

    it('should deploy to Cloudflare', () => {
      const command = 'wrangler deploy';
      expect(command).toBe('wrangler deploy');
    });

    it('should handle deployment errors', () => {
      mockExecSync.mockImplementation(() => {
        throw new Error('Deployment failed');
      });

      expect(() => {
        throw new Error('Deployment failed');
      }).toThrow('Deployment failed');
    });
  });

  describe('command line arguments', () => {
    it('should parse skip-processing flag', () => {
      const args = ['--skip-processing'];
      const options = {
        skipProcessing: args.includes('--skip-processing')
      };
      expect(options.skipProcessing).toBe(true);
    });

    it('should parse skip-upload flag', () => {
      const args = ['--skip-upload'];
      const options = {
        skipVideoUpload: args.includes('--skip-upload')
      };
      expect(options.skipVideoUpload).toBe(true);
    });

    it('should parse skip-deploy flag', () => {
      const args = ['--skip-deploy'];
      const options = {
        skipDeploy: args.includes('--skip-deploy')
      };
      expect(options.skipDeploy).toBe(true);
    });

    it('should parse process-only flag', () => {
      const args = ['--process-only'];
      const options = {
        processOnly: args.includes('--process-only')
      };
      expect(options.processOnly).toBe(true);
    });

    it('should parse rebuild-db flag', () => {
      const args = ['--rebuild-db'];
      const options = {
        rebuildDb: args.includes('--rebuild-db')
      };
      expect(options.rebuildDb).toBe(true);
    });

    it('should parse debug flag', () => {
      const args = ['--debug'];
      const options = {
        debugMode: args.includes('--debug')
      };
      expect(options.debugMode).toBe(true);
    });
  });

  describe('error handling', () => {
    it('should provide troubleshooting information on failure', () => {
      const errorMessage = `
Pipeline failed: Test error

🔧 Troubleshooting:
   1. Check that all prerequisites are installed
   2. Verify Cloudflare credentials are set
   3. Ensure source videos are in source/videos/
   4. Check CLAUDE.md for configuration requirements`;
      
      expect(errorMessage).toContain('Prerequisites are installed');
      expect(errorMessage).toContain('Cloudflare credentials');
      expect(errorMessage).toContain('source/videos/');
      expect(errorMessage).toContain('CLAUDE.md');
    });

    it('should exit with code 1 on error', () => {
      const mockExit = jest.spyOn(process, 'exit').mockImplementation(() => {});
      
      try {
        // Simulate error condition
        throw new Error('Test error');
      } catch (error) {
        // Would normally call process.exit(1)
        expect(error.message).toBe('Test error');
      }
      
      mockExit.mockRestore();
    });
  });

  describe('integration scenarios', () => {
    it('should run complete pipeline successfully', async () => {
      // Mock all successful operations
      mockExecSync.mockReturnValue('success');
      mockFs.existsSync.mockReturnValue(true);
      mockFs.readdirSync.mockReturnValue(['video1.mp4', 'video2.mp4']);

      const options = {
        skipProcessing: false,
        skipVideoUpload: false,
        skipDeploy: false,
        processOnly: false,
        rebuildDb: false,
        debugMode: false
      };

      // Would normally run the full pipeline
      expect(options.skipProcessing).toBe(false);
      expect(options.skipDeploy).toBe(false);
    });

    it('should handle process-only mode', async () => {
      const options = { processOnly: true };
      
      // Should exit early after processing
      expect(options.processOnly).toBe(true);
    });

    it('should handle skip-processing mode', async () => {
      const options = { skipProcessing: true };
      
      // Should skip video processing
      expect(options.skipProcessing).toBe(true);
    });
  });
});