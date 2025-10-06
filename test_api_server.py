#!/usr/bin/env python3
"""
Test script for the Flask API Server
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:5000"

def test_health_endpoint():
    """Test the health endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Health check passed")
            print(f"   Status: {data.get('status')}")
            print(f"   Agent Available: {data.get('agent_available')}")
            print(f"   Control: {data.get('control', 'None')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_chat_endpoint():
    """Test the chat endpoint with a sample message"""
    print("\n💬 Testing chat endpoint...")
    try:
        payload = {
            "message": "Does this application have non-human accounts for C-305377 compliance?",
            "context": {
                "applicationId": "CustomerPortal",
                "controlId": "C-305377"
            }
        }

        response = requests.post(
            f"{API_BASE_URL}/chat",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ Chat endpoint working")
            print(f"   Success: {data.get('success')}")
            print(f"   Agent: {data.get('agent_name')}")
            print(f"   Response length: {len(data.get('message', ''))}")
            return True
        else:
            print(f"❌ Chat endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Chat endpoint error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 API Server Test Suite")
    print("=" * 40)

    # Wait a moment for server to start
    print("⏳ Waiting for API server to start...")
    time.sleep(2)

    tests = [
        ("Health Check", test_health_endpoint),
        ("Chat Endpoint", test_chat_endpoint),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        result = test_func()
        results.append((test_name, result))

    # Summary
    print("\n📊 Test Results:")
    print("=" * 40)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n🎯 Summary: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! API server is working correctly.")
        print("\n🚀 Next steps:")
        print("1. Start your React frontend: npm run dev")
        print("2. Open http://localhost:3000/agent-ui")
        print("3. Test the full integration")
    else:
        print("\n⚠️  Some tests failed. Please check:")
        print("1. Is the API server running on port 5000?")
        print("2. Is agent.py properly configured?")
        print("3. Are MCP servers running?")
        print("4. Check the API server logs for errors")

    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
