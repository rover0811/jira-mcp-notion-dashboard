#!/bin/bash

# 필수 환경 변수가 설정되었는지 확인
if [[ -z "$ANTHROPIC_API_KEY" || -z "$JIRA_ACCESS_TOKEN" ]]; then
  echo "Error: ANTHROPIC_API_KEY and JIRA_ACCESS_TOKEN must be set as environment variables."
  exit 1
fi

STACK_NAME="jira-ticket-creator-stack"
REGION="ap-northeast-2" # 원하는 리전으로 변경

echo "Deploying to AWS stack: $STACK_NAME in region: $REGION"

sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --parameter-overrides \
    AnthropicApiKey="$ANTHROPIC_API_KEY" \
    JiraAccessToken="$JIRA_ACCESS_TOKEN" \
  --capabilities CAPABILITY_IAM