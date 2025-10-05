#!/usr/bin/env node

/**
 * Test script for ADK integration
 * Run this to verify that the ADK embedding works correctly
 */

const http = require('http');

const ADK_PORT = 8000;
const NEXTJS_PORT = 3000;

console.log('🔧 ADK Integration Test Suite');
console.log('=' .repeat(50));

// Test 1: Check if ADK server is running
function testAdkServer() {
  return new Promise((resolve) => {
    const req = http.request({
      hostname: 'localhost',
      port: ADK_PORT,
      path: '/health',
      method: 'GET',
      timeout: 3000
    }, (res) => {
      if (res.statusCode === 200) {
        console.log('✅ ADK server is running on port', ADK_PORT);
        resolve(true);
      } else {
        console.log('❌ ADK server responded with status:', res.statusCode);
        resolve(false);
      }
    });

    req.on('error', (err) => {
      console.log('❌ ADK server not reachable:', err.message);
      console.log('   Make sure to run: adk web');
      resolve(false);
    });

    req.on('timeout', () => {
      console.log('❌ ADK server timeout');
      req.destroy();
      resolve(false);
    });

    req.end();
  });
}

// Test 2: Check if Next.js app is running
function testNextjsApp() {
  return new Promise((resolve) => {
    const req = http.request({
      hostname: 'localhost',
      port: NEXTJS_PORT,
      path: '/',
      method: 'GET',
      timeout: 3000
    }, (res) => {
      if (res.statusCode === 200) {
        console.log('✅ Next.js app is running on port', NEXTJS_PORT);
        resolve(true);
      } else {
        console.log('❌ Next.js app responded with status:', res.statusCode);
        resolve(false);
      }
    });

    req.on('error', (err) => {
      console.log('❌ Next.js app not reachable:', err.message);
      console.log('   Make sure to run: npm run dev');
      resolve(false);
    });

    req.on('timeout', () => {
      console.log('❌ Next.js app timeout');
      req.destroy();
      resolve(false);
    });

    req.end();
  });
}

// Test 3: Test ADK proxy route
function testAdkProxy() {
  return new Promise((resolve) => {
    const req = http.request({
      hostname: 'localhost',
      port: NEXTJS_PORT,
      path: '/adk/health',
      method: 'GET',
      timeout: 5000
    }, (res) => {
      if (res.statusCode === 200) {
        console.log('✅ ADK proxy route is working');
        resolve(true);
      } else {
        console.log('❌ ADK proxy route failed with status:', res.statusCode);
        resolve(false);
      }
    });

    req.on('error', (err) => {
      console.log('❌ ADK proxy not reachable:', err.message);
      resolve(false);
    });

    req.on('timeout', () => {
      console.log('❌ ADK proxy timeout');
      req.destroy();
      resolve(false);
    });

    req.end();
  });
}

// Test 4: Test agent UI route
function testAgentUIRoute() {
  return new Promise((resolve) => {
    const req = http.request({
      hostname: 'localhost',
      port: NEXTJS_PORT,
      path: '/agent-ui',
      method: 'GET',
      timeout: 5000
    }, (res) => {
      if (res.statusCode === 200) {
        console.log('✅ Agent UI route is accessible');
        resolve(true);
      } else {
        console.log('❌ Agent UI route failed with status:', res.statusCode);
        resolve(false);
      }
    });

    req.on('error', (err) => {
      console.log('❌ Agent UI route not reachable:', err.message);
      resolve(false);
    });

    req.on('timeout', () => {
      console.log('❌ Agent UI route timeout');
      req.destroy();
      resolve(false);
    });

    req.end();
  });
}

// Main test runner
async function runTests() {
  console.log('\n📋 Running integration tests...\n');

  const results = {
    adkServer: await testAdkServer(),
    nextjsApp: await testNextjsApp(),
    adkProxy: await testAdkProxy(),
    agentUI: await testAgentUIRoute()
  };

  console.log('\n📊 Test Results:');
  console.log('=' .repeat(30));

  const passed = Object.values(results).filter(Boolean).length;
  const total = Object.keys(results).length;

  Object.entries(results).forEach(([test, passed]) => {
    const status = passed ? '✅ PASS' : '❌ FAIL';
    console.log(`${status} - ${test}`);
  });

  console.log('\n📈 Summary:');
  console.log(`${passed}/${total} tests passed`);

  if (passed === total) {
    console.log('\n🎉 All tests passed! ADK integration is ready.');
    console.log('\n🚀 Next steps:');
    console.log('1. Open http://localhost:3000/agent-ui in your browser');
    console.log('2. Verify that the ADK UI is embedded correctly');
    console.log('3. Test the postMessage communication');
    console.log('4. Try different controls and applications');
  } else {
    console.log('\n⚠️  Some tests failed. Please fix the issues above before proceeding.');
    console.log('\n🔧 Common fixes:');
    console.log('- Start ADK server: adk web');
    console.log('- Start Next.js app: npm run dev');
    console.log('- Check firewall/network settings');
  }

  process.exit(passed === total ? 0 : 1);
}

// Run tests
if (require.main === module) {
  runTests().catch(console.error);
}

module.exports = { runTests, testAdkServer, testNextjsApp, testAdkProxy, testAgentUIRoute };
