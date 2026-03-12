
import requests
import json

# API请求的URL，注意替换为你的实际端口号（如未修改端口，默认不需要加端口号）
url = 'https://api.dify.ai/v1'

# 应用密钥
api_key = "app-a1jMzfr0TrVOGUcHROEH1IPl"

# 请求头
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json',
}

# 请求数据
data = {
    "inputs": {},
    "query": "",
    "response_mode": "blocking",
    "conversation_id": "",
    "user": "abc-123"
}

# 发送POST请求
response = requests.post(url, headers=headers, data=json.dumps(data))

# 处理响应
if response.status_code == 200:
    print(response.json())
else:
    print(f"Error: {response.status_code}, {response.text}")
