from openai import OpenAI

def generate_tutorial_with_deepseek(prompt, api_key):
    import requests
    url = "https://api.deepseek.com/v1/chat/completions"  # 需要确认官方最新API路径
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "max_tokens": 2000,
        "stream": False
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error: {response.text}"