#!/usr/bin/env python3
"""
Comprehensive frontend testing script for MV Face Recognition Svelte deployment
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, Any

class FrontendTester:
    def __init__(self, frontend_url: str, backend_url: str):
        self.frontend_url = frontend_url.rstrip('/')
        self.backend_url = backend_url.rstrip('/')
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'frontend_url': frontend_url,
            'backend_url': backend_url,
            'tests': {}
        }
        
    async def test_page_load(self, session: aiohttp.ClientSession, path: str = '/') -> Dict[str, Any]:
        """Test page load time and response"""
        url = f"{self.frontend_url}{path}"
        start_time = time.time()
        
        try:
            async with session.get(url) as response:
                load_time = time.time() - start_time
                content = await response.text()
                
                return {
                    'url': url,
                    'status_code': response.status,
                    'load_time_ms': round(load_time * 1000, 2),
                    'content_length': len(content),
                    'content_type': response.headers.get('content-type', 'unknown'),
                    'headers': dict(response.headers),
                    'success': response.status == 200,
                    'has_svelte_content': 'svelte' in content.lower(),
                    'has_navigation': 'nav' in content.lower() or 'menu' in content.lower(),
                    'has_error': 'error' in content.lower(),
                    'content_preview': content[:500] if len(content) > 500 else content
                }
        except Exception as e:
            return {
                'url': url,
                'status_code': 0,
                'load_time_ms': round((time.time() - start_time) * 1000, 2),
                'success': False,
                'error': str(e)
            }
    
    async def test_api_endpoints(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Test API endpoints through frontend proxy"""
        endpoints = [
            '/api/system/info',
            '/api/videos/',
            '/api/contestants/',
            '/api/settings/',
            '/api/health/',
            '/api/system/status/'
        ]
        
        results = {}
        for endpoint in endpoints:
            url = f"{self.frontend_url}{endpoint}"
            start_time = time.time()
            
            try:
                async with session.get(url) as response:
                    load_time = time.time() - start_time
                    content = await response.text()
                    
                    results[endpoint] = {
                        'url': url,
                        'status_code': response.status,
                        'load_time_ms': round(load_time * 1000, 2),
                        'success': response.status == 200,
                        'content_type': response.headers.get('content-type', 'unknown'),
                        'response_preview': content[:200] if len(content) > 200 else content
                    }
            except Exception as e:
                results[endpoint] = {
                    'url': url,
                    'success': False,
                    'error': str(e)
                }
        
        return results
    
    async def test_backend_direct(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Test backend API directly"""
        endpoints = [
            '/',
            '/health',
            '/api/system/info'
        ]
        
        results = {}
        for endpoint in endpoints:
            url = f"{self.backend_url}{endpoint}"
            start_time = time.time()
            
            try:
                async with session.get(url) as response:
                    load_time = time.time() - start_time
                    content = await response.text()
                    
                    results[endpoint] = {
                        'url': url,
                        'status_code': response.status,
                        'load_time_ms': round(load_time * 1000, 2),
                        'success': response.status == 200,
                        'content_type': response.headers.get('content-type', 'unknown'),
                        'response_preview': content[:200] if len(content) > 200 else content
                    }
            except Exception as e:
                results[endpoint] = {
                    'url': url,
                    'success': False,
                    'error': str(e)
                }
        
        return results
    
    async def test_frontend_routes(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Test all frontend routes"""
        routes = [
            '/',
            '/video-player',
            '/face-recognition',
            '/analytics',
            '/settings',
            '/video-processing'
        ]
        
        results = {}
        for route in routes:
            results[route] = await self.test_page_load(session, route)
        
        return results
    
    async def test_static_assets(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Test static asset loading"""
        assets = [
            '/_app/version.json',
            '/_app/immutable/entry/start.Cn5ve7iq.js',
            '/_app/immutable/entry/app.DbilSMmc.js',
            '/favicon.ico'
        ]
        
        results = {}
        for asset in assets:
            url = f"{self.frontend_url}{asset}"
            start_time = time.time()
            
            try:
                async with session.get(url) as response:
                    load_time = time.time() - start_time
                    
                    results[asset] = {
                        'url': url,
                        'status_code': response.status,
                        'load_time_ms': round(load_time * 1000, 2),
                        'success': response.status == 200,
                        'content_type': response.headers.get('content-type', 'unknown'),
                        'cache_control': response.headers.get('cache-control', 'none')
                    }
            except Exception as e:
                results[asset] = {
                    'url': url,
                    'success': False,
                    'error': str(e)
                }
        
        return results
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests"""
        async with aiohttp.ClientSession() as session:
            print("Testing frontend routes...")
            self.results['tests']['frontend_routes'] = await self.test_frontend_routes(session)
            
            print("Testing API endpoints through frontend...")
            self.results['tests']['api_endpoints'] = await self.test_api_endpoints(session)
            
            print("Testing backend API directly...")
            self.results['tests']['backend_direct'] = await self.test_backend_direct(session)
            
            print("Testing static assets...")
            self.results['tests']['static_assets'] = await self.test_static_assets(session)
            
        return self.results
    
    def generate_report(self) -> str:
        """Generate a comprehensive test report"""
        report = []
        report.append("# MV Face Recognition Frontend Deployment Test Report")
        report.append(f"**Test Date:** {self.results['timestamp']}")
        report.append(f"**Frontend URL:** {self.results['frontend_url']}")
        report.append(f"**Backend URL:** {self.results['backend_url']}")
        report.append("")
        
        # Frontend Routes Report
        report.append("## Frontend Routes Test Results")
        frontend_routes = self.results['tests']['frontend_routes']
        for route, result in frontend_routes.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            load_time = result.get('load_time_ms', 0)
            report.append(f"- **{route}**: {status} ({load_time}ms)")
            if not result['success']:
                report.append(f"  - Error: {result.get('error', 'Unknown error')}")
        report.append("")
        
        # API Endpoints Report
        report.append("## API Endpoints Test Results")
        api_endpoints = self.results['tests']['api_endpoints']
        for endpoint, result in api_endpoints.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            load_time = result.get('load_time_ms', 0)
            report.append(f"- **{endpoint}**: {status} ({load_time}ms)")
            if not result['success']:
                report.append(f"  - Error: {result.get('error', 'Unknown error')}")
        report.append("")
        
        # Backend Direct Test Report
        report.append("## Backend API Direct Test Results")
        backend_direct = self.results['tests']['backend_direct']
        for endpoint, result in backend_direct.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            load_time = result.get('load_time_ms', 0)
            report.append(f"- **{endpoint}**: {status} ({load_time}ms)")
            if not result['success']:
                report.append(f"  - Error: {result.get('error', 'Unknown error')}")
        report.append("")
        
        # Static Assets Report
        report.append("## Static Assets Test Results")
        static_assets = self.results['tests']['static_assets']
        for asset, result in static_assets.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            load_time = result.get('load_time_ms', 0)
            report.append(f"- **{asset}**: {status} ({load_time}ms)")
            if not result['success']:
                report.append(f"  - Error: {result.get('error', 'Unknown error')}")
        report.append("")
        
        # Performance Summary
        report.append("## Performance Summary")
        total_routes = len(frontend_routes)
        successful_routes = sum(1 for r in frontend_routes.values() if r['success'])
        avg_load_time = sum(r.get('load_time_ms', 0) for r in frontend_routes.values()) / total_routes
        
        report.append(f"- **Routes Tested**: {total_routes}")
        report.append(f"- **Successful Routes**: {successful_routes}")
        report.append(f"- **Success Rate**: {(successful_routes/total_routes)*100:.1f}%")
        report.append(f"- **Average Load Time**: {avg_load_time:.2f}ms")
        report.append("")
        
        # Issues and Recommendations
        report.append("## Issues and Recommendations")
        issues = []
        
        # Check for failed routes
        failed_routes = [route for route, result in frontend_routes.items() if not result['success']]
        if failed_routes:
            issues.append(f"**Failed Routes**: {', '.join(failed_routes)}")
        
        # Check for slow load times
        slow_routes = [route for route, result in frontend_routes.items() if result.get('load_time_ms', 0) > 5000]
        if slow_routes:
            issues.append(f"**Slow Loading Routes** (>5s): {', '.join(slow_routes)}")
        
        # Check API connectivity
        failed_apis = [endpoint for endpoint, result in api_endpoints.items() if not result['success']]
        if failed_apis:
            issues.append(f"**Failed API Endpoints**: {', '.join(failed_apis)}")
        
        if issues:
            for issue in issues:
                report.append(f"- {issue}")
        else:
            report.append("- No critical issues detected")
        
        return "\n".join(report)

async def main():
    """Main function to run tests"""
    frontend_url = "https://mv-face-recognition-svelte.fly.dev"
    backend_url = "https://mv-face-recognition-backend.fly.dev"
    
    tester = FrontendTester(frontend_url, backend_url)
    
    print("Starting comprehensive frontend testing...")
    print(f"Frontend URL: {frontend_url}")
    print(f"Backend URL: {backend_url}")
    print("-" * 50)
    
    results = await tester.run_all_tests()
    
    # Save results to JSON file
    with open('/Users/swong/dev/mv-face-recognition/frontend_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate and save report
    report = tester.generate_report()
    with open('/Users/swong/dev/mv-face-recognition/frontend_test_report.md', 'w') as f:
        f.write(report)
    
    print("\n" + "=" * 50)
    print("TEST REPORT")
    print("=" * 50)
    print(report)
    print("\n" + "=" * 50)
    print("Results saved to:")
    print("- frontend_test_results.json")
    print("- frontend_test_report.md")

if __name__ == "__main__":
    asyncio.run(main())