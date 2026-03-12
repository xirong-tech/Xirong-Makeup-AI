import requests
import json
import logging

logger = logging.getLogger(__name__)
from fontTools.misc.cython import returns


def generate_makeup_tutorial_describe():
    try:
        # 构建Prompt
        prompt_1 = f"""

            以下是嘴唇颜色数据：

<嘴唇颜色数据>

唇色名称：{{indianred}}

RGB值：{{ 207, 91, 103}}

</嘴唇颜色数据>

以下是眼影颜色数据：

<眼影颜色数据>

打底色：{{dimgray}}（RGB：{{79, 59, 57}}）

过渡色：{{sienna}}（RGB：{{135, 101, 82}}）

强调色：{{peru}}（RGB：{{187, 129, 88}}）

</眼影颜色数据>

以下是肤色适配数据：

<肤色适配数据>

肤色：{{tan}}（RGB：{{224, 187, 157}}）

发色：{{midnightblue}}（RGB：{{19, 36, 52}}

</肤色适配数据>

以下是眼睛颜色数据：

<眼睛颜色数据>

基色：{{midnightblue}}（RGB：{{36, 47, 59}}）

</眼睛颜色数据>


            """

        # API 请求配置
        url = 'http://152.136.96.241:8080/v1/workflows/run'
        api_key = "app-HWv0QARgeUkp2SAcjBC1u5wN"
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        payload = {
            "inputs": {"context_color": prompt_1},
            "response_mode": "blocking",  # 明确指定阻塞模式
            "user": "abc-123"
        }
        # 增加超时和异常处理
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # 检查 HTTP 状态码

        # 解析 Dify 响应
        result = response.json()
        if result.get("data", {}).get("status") != "succeeded":
            raise ValueError(f"Dify 工作流执行失败: {result.get('data', {}).get('error')}")

        # 提取最终输出文本
        output_text = result["data"]["outputs"].get("makeup_describe")
        return output_text,result

    except Exception as e:
        logger.error(f"生成描述失败: {str(e)}")
        return f"描述生成失败: {str(e)}"


if __name__ == "__main__":
    output_text, result = generate_makeup_tutorial_describe()
    print("\n生成结果：")
    print(output_text)
    print(result)