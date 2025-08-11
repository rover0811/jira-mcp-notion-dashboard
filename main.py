import os
import json
import anthropic
import boto3
import requests

ssm_client = boto3.client('ssm')
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def get_ssm_param(name):
    if os.getenv("AWS_SAM_LOCAL") == "true":
        print(f"LOCAL: Getting param '{name}' from env.json")
        with open('env.json', 'r') as f:
            config = json.load(f)
            if name in config.get('CreateJiraTicketFunction', {}):
                return config['CreateJiraTicketFunction'][name]
            if name in config.get('AuthFunctions', {}):
                return config['AuthFunctions'][name]
        raise KeyError(f"'{name}' not found in local env.json")
    else:
        path = os.getenv("ATLASSIAN_SSM_PATH") + name
        response = ssm_client.get_parameter(
            Name=path,
            WithDecryption=True
        )
        return response['Parameter']['Value']


def put_ssm_param(name, value):
    if os.getenv("AWS_SAM_LOCAL") == "true":
        print(f"LOCAL: Skipping SSM put_parameter for '{name}'.")
        return
    else:
        path = os.getenv("ATLASSIAN_SSM_PATH") + name
        ssm_client.put_parameter(
            Name=path,
            Value=value,
            Type='SecureString',
            Overwrite=True
        )


def refresh_jira_token(refresh_token):
    # 토큰 갱신 로직
    client_id = get_ssm_param('atlassian_client_id')
    client_secret = get_ssm_param('atlassian_client_secret')
    token_url = get_ssm_param('atlassian_token_url')

    response = requests.post(
        token_url,
        data={
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token
        }
    )
    new_token_data = response.json()
    if 'access_token' in new_token_data:
        # Store the new access token securely
        put_ssm_param('JIRA_ACCESS_TOKEN', new_token_data['access_token'])
        return jsonify(new_token_data)
    else:
        raise Exception("Failed to refresh token.")


def lambda_handler(event, context):
    try:
        access_token = get_ssm_param('JIRA_ACCESS_TOKEN')
        refresh_token = get_ssm_param('jira_refresh_token')

        # 토큰 유효성 검사 및 갱신 (만료 시)
        # 실제로는 토큰 만료 시간을 확인하는 로직이 필요하지만, 여기서는 간략화합니다.
        if not access_token:
            access_token = refresh_jira_token(refresh_token)

        # HTTP 요청 본문 파싱
        body = json.loads(event.get('body', '{}'))
        user_query = body.get("userQuery")

        if not user_query:
            return {'statusCode': 400, 'body': '{"error": "userQuery is required."}'}

        # Anthropic API 호출
        response = anthropic_client.beta.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": user_query}],
            mcp_servers=[{
                "type": "url",
                "url": os.getenv("ATLASSIAN_MCP_SERVER_URL"),
                "name": "atlassian-mcp",
                "authorization_token": access_token
            }],
            betas=["mcp-client-2025-04-04"]
        )
        return {'statusCode': 200, 'body': response.model_dump_json()}
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({"error": str(e)})}