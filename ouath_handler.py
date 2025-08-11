import os
import urllib.parse
import boto3
import requests
import json

ssm_client = boto3.client('ssm')


def get_ssm_params():
    # Check if running locally via SAM CLI
    if os.getenv("AWS_SAM_LOCAL") == "true":
        print("Running in local environment, loading params from env.json")
        try:
            with open('env.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("ERROR: env.json not found. Please create it for local development.")
            return {}
        except json.JSONDecodeError:
            print("ERROR: Could not decode env.json. Please ensure it is valid JSON.")
            return {}
    else:
        print("Running in AWS environment, loading params from SSM")
        path = os.getenv("ATLASSIAN_SSM_PATH")
        if not path:
            raise ValueError("ATLASSIAN_SSM_PATH environment variable not set.")
        response = ssm_client.get_parameters_by_path(
            Path=path,
            WithDecryption=True
        )
        return {param['Name'].split('/')[-1]: param['Value'] for param in response['Parameters']}


def put_ssm_param(name, value):
    # Check if running locally via SAM CLI
    if os.getenv("AWS_SAM_LOCAL") == "true":
        print(f"Running in local environment. Skipping SSM put_parameter for '{name}'.")
        return
    else:
        print(f"Running in AWS environment, putting param '{name}' to SSM.")
        path = os.getenv("ATLASSIAN_SSM_PATH")
        if not path:
            raise ValueError("ATLASSIAN_SSM_PATH environment variable not set.")

        ssm_client.put_parameter(
            Name=path + name,
            Value=value,
            Type='SecureString',
            Overwrite=True
        )


def start(event, context):
    params = get_ssm_params()
    auth_params = params.get("AuthFunctions", {})
    redirect_uri = os.getenv("ATLASSIAN_REDIRECT_URI")
    auth_url = (
        f"{auth_params['atlassian_auth_url']}?audience=api.atlassian.com"
        f"&client_id={auth_params['atlassian_client_id']}&scope=read%3Ajira-work%20write%3Ajira-work%20offline_access"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}&response_type=code"
    )
    return {
        'statusCode': 302,
        'headers': {
            'Location': auth_url
        }
    }


def callback(event, context):
    params = get_ssm_params()
    auth_params = params.get("AuthFunctions", {})
    code = event['queryStringParameters'].get('code')
    if not code:
        return {'statusCode': 400, 'body': 'Authorization code not found.'}

    redirect_uri = os.getenv("ATLASSIAN_REDIRECT_URI")

    response = requests.post(
        auth_params['atlassian_token_url'],
        data={
            'grant_type': 'authorization_code',
            'client_id': auth_params['atlassian_client_id'],
            'client_secret': auth_params['atlassian_client_secret'],
            'code': code,
            'redirect_uri': redirect_uri
        }
    )
    token_data = response.json()

    if 'access_token' in token_data:
        put_ssm_param('JIRA_ACCESS_TOKEN', token_data['access_token'])
        put_ssm_param('jira_refresh_token', token_data['refresh_token'])
        return {'statusCode': 200, 'body': 'Token saved successfully!'}
    else:
        return {'statusCode': 500, 'body': json.dumps(token_data)}