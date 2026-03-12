import requests
import json
import logging

logger = logging.getLogger(__name__)
from fontTools.misc.cython import returns


def generate_makeup_tutorial_describe(data):
    try:
        # 构建Prompt
        prompt_1 = f"""
    
            以下是嘴唇颜色数据：
        <嘴唇颜色数据>
        唇色名称：{data['color']['lips_color_name']} (RGB: {data['color']['lips_color_rgb']})
        </嘴唇颜色数据>
    
        以下是眼影颜色数据：
        <眼影颜色数据>
        打底色：{data['features']['eyeshadow0_color_name']}(RGB: {data['features']['eyeshadow0_color_rgb']})
        过渡色：{data['features']['eyeshadow1_color_name']}(RGB: {data['features']['eyeshadow1_color_rgb']})
        强调色：{data['features']['eyeshadow2_color_name']}(RGB: {data['features']['eyeshadow2_color_rgb']})
        </眼影颜色数据>
    
        以下是肤色适配数据：
        <肤色适配数据>
        肤色：{data['color']['skin_color_name']}(RGB: {data['color']['skin_color_rgb']})
        发色：{data['color']['hair_color_name']}(RGB: {data['color']['hair_color_rgb']})
        </肤色适配数据>
    
        以下是眼睛颜色数据：
        <眼睛颜色数据>
        基色：{data['color']['eyes_color_name']}(RGB: {data['color']['eyes_color_rgb']})
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

        # 先检查响应内容是否有效
        if not response.text.strip().startswith('{'):
            logger.error(f"无效响应内容: {response.text[:200]}")
            return "服务响应格式异常"

        # 解析 Dify 响应
        result = response.json()
        if result.get("data", {}).get("status") != "succeeded":
            raise ValueError(f"Dify 工作流执行失败: {result.get('data', {}).get('error')}")

        # 提取最终输出文本
        output_text = result["data"]["outputs"].get("makeup_describe", "无有效描述内容")
        return output_text

    except Exception as e:
        logger.error(f"生成描述失败: {str(e)}")
        return f"描述生成失败: {str(e)}"


