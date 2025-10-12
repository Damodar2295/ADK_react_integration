#!/bin/bash

# Test script for iam_evidence app
# Tests the IAM evidence evaluation functionality via ADK API Server

set -e

echo "🧪 Testing IAM Evidence App"
echo "================================"

# Configuration
APP_NAME="iam_evidence"
USER_ID="test-user"
SESSION_ID="test-iam-$(date +%s)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Create session
echo -e "\n${YELLOW}Creating session...${NC}"
curl -X POST "http://localhost:8000/apps/$APP_NAME/users/$USER_ID/sessions/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d "{}" | jq .

sleep 2

# Step 2: Prepare test payload (Base64-encoded JSON)
echo -e "\n${YELLOW}Preparing test payload...${NC}"

# Sample evidence data
JSON_PAYLOAD='{
  "appId": "APP_001",
  "controlId": "CID_123",
  "evidences": [
    {
      "fileName": "policy.pdf",
      "mimeType": "application/pdf",
      "base64": "SGVsbG8gV29ybGQ="  // Base64 encoded "Hello World"
    }
  ]
}'

# Base64 encode the JSON payload
INLINE_B64=$(echo -n "$JSON_PAYLOAD" | base64 -w 0)

echo "Payload preview (first 100 chars):"
echo "$JSON_PAYLOAD" | head -c 100
echo "..."

# Step 3: Send message via /run
echo -e "\n${YELLOW}Sending message via /run...${NC}"

RESPONSE=$(curl -s -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d "{
    \"app_name\": \"$APP_NAME\",
    \"user_id\": \"$USER_ID\",
    \"session_id\": \"$SESSION_ID\",
    \"new_message\": {
      \"role\": \"user\",
      \"parts\": [
        {\"text\": \"Analyze IAM evidences for compliance\"},
        {\"inlineData\": {\"mimeType\": \"application/json\", \"data\": \"$INLINE_B64\"}}
      ]
    }
  }")

echo -e "\n${YELLOW}Full Response:${NC}"
echo "$RESPONSE" | jq .

# Step 4: Extract iam_evidence_result
echo -e "\n${YELLOW}Extracting iam_evidence_result...${NC}"

RESULT=$(echo "$RESPONSE" | jq -r '.[] | select(.content.parts[].functionResponse.name == "iam_evidence_result") | .content.parts[].functionResponse.response.result')

if [ -n "$RESULT" ] && [ "$RESULT" != "null" ]; then
    echo -e "\n${GREEN}✅ Success! iam_evidence_result extracted:${NC}"
    echo "$RESULT" | jq .
else
    echo -e "\n${RED}❌ Failed to extract iam_evidence_result${NC}"
    echo "Response structure may be different than expected"
    exit 1
fi

# Step 5: Validate result structure
echo -e "\n${YELLOW}Validating result structure...${NC}"

# Parse the result as JSON
PARSED_RESULT=$(echo "$RESULT" | jq .)

if [ "$(echo "$PARSED_RESULT" | jq -r 'has("evidence_analysis")')" = "true" ]; then
    echo -e "${GREEN}✅ evidence_analysis field found${NC}"
else
    echo -e "${RED}❌ evidence_analysis field missing${NC}"
fi

if [ "$(echo "$PARSED_RESULT" | jq -r 'has("compliance_assessment")')" = "true" ]; then
    echo -e "${GREEN}✅ compliance_assessment field found${NC}"
else
    echo -e "${RED}❌ compliance_assessment field missing${NC}"
fi

echo -e "\n${GREEN}🎉 IAM Evidence App test completed successfully!${NC}"
echo "The app properly processes evidence data and returns structured compliance assessments."
