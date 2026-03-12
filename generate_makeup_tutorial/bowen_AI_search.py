# BoCha AI Search Python SDK
import requests, json
from typing import Iterator

from fontTools.misc.cython import returns


def bocha_ai_search(
    query: str,
    api_key: str,
    api_url: str = "https://api.bochaai.com/v1/ai-search",
    freshness: str = "noLimit",
    count:int=50,
    answer: bool = False,
    stream: bool = False
):
    """ 博查AI搜索 """
    data = {
        "query": query,
        "freshness": freshness,
        "answer": answer,
        "count":count,
        "stream": stream
    }

    resp = requests.post(
        api_url,
        headers={"Authorization": f"Bearer {api_key}"},
        json=data,
        stream=stream
    )

    if stream:
        return (json.loads(line) for line in parse_response_stream(resp.iter_lines()))
    else:
        if resp.status_code == 200:
            return resp.json()
        else:
            return { "code": resp.code, "msg": "bocha ai search api error." }

def parse_response_stream(resp: Iterator[bytes]) -> Iterator[str]:
    """将stream的sse event bytes数据解析成line格式"""
    for line in resp:
        if line:
            if line.startswith(b"data:"):
                _line = line[len(b"data:"):]
                _line = _line.decode("utf-8")
            else:
                _line = line.decode("utf-8")
            yield _line



def bocha_search(context):
    BOCHA_API_KEY = "sk-d0b57c90a4b04bdea54919ba5ac5b2a6"
    BOCHA_API_URL = "https://api.bochaai.com/v1/ai-search"

    response = bocha_ai_search(
        api_url=BOCHA_API_URL,
        api_key=BOCHA_API_KEY,
        query=context,
        count=50,
        freshness="noLimit",
        answer=False,
        stream=False
    )

    return json.dumps(response,indent=4,ensure_ascii=False,sort_keys=True)


