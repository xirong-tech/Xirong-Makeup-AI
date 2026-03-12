import requests
import json
import logging

logger = logging.getLogger(__name__)
from click import prompt


def generate_makeup_tutorial():
    try:
        # 色卡数据库示例

        prompt_2 = f"""
        你是一位专业AI化妆师，你的任务是根据用户提供的色彩数据生成定制化妆教程。请仔细阅读以下数据，并按照给定的创作规范和输出结构要求进行处理。

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

    创作规范如下：

    1. 以指定开头语启动教程："小可爱准备好变身了吗？(≧∀≦)ゞ 小歖AI化妆师根据你的肤色帮你定制专属妆容啦"

    2. 创作流程包含：

       a. 总体流程导览（4 - 5步科学上妆顺序）

       b. 分步骤指导（每步包含：工具选择、手法演示、颜色应用技巧）

       c. 产品推荐（每个大类步骤结尾提供1 - 2个的官网产品链接）

    3. 色彩处理原则：

       - 将RGB值转换为通俗中文描述（如"珊瑚橘"代替RGB(255,127,80)）

       - 发色仅用于整体协调性判断，不在步骤中直接使用

       - 颜色描述需注明「参考色」+中文名称（如「参考色：蜜桃粉」）

    4. 交互要素：

       - 尽量以通俗易懂的、适合广大中国女性用户的中文语言描述，以亲切可爱同时又不失认真态度的歖容AI化妆师口吻叙述

       - 适当添加添加鼓励性话语（如"这一步完成得好棒！(๑ᴗ<๑)"）

       - 插入可爱灵动的emoji，同时维持排版简介明了

       - 使用「小贴士：」标注注意事项

       - 结尾处对用户表达一些鼓励性、提高用户自信的、勇敢去追求美的话语。

       -减少“**”、“###”等非常规书写的符号

    5. 质量控制：

    -给出的所有链接都要经过审核检查，确保链接的可信度，避免出现虚假链接和错误连接的出现

       - 确保色差说明，表达上述妆容仅供参考请用户以实际为主的提醒（如"实物颜色可能因光线略有不同"）

       - 减少专业术语的使用，必要时用括号解释（如"晕染（轻轻涂抹开）"）


        """

        #####################################################################################dify的api调用#####################################################
        # API请求的URL，注意替换为你的实际端口号（如未修改端口，默认不需要加端口号）
        url = 'http://152.136.96.241:8080/v1/workflows/run'

        # 应用密钥
        api_key_2_makeuptext = "app-t8Cea7aF4B5ErUGVAvFTJUJC"

        # 请求头

        headers_2 = {'Authorization': f'Bearer {api_key_2_makeuptext}', 'Content-Type': 'application/json', }

        # 请求数据

        data_2 = {
            "inputs": {"content": prompt_2},
            "response_mode": "streaming",
            "user": "abc-123"
        }

        # 发送POST请求
        response_2 = requests.post(url, headers=headers_2, data=json.dumps(data_2))

        if response_2.status_code != 200:
            logger.error(f"API请求失败: {response_2.status_code} - {response_2.text[:200]}")
            return "服务暂时不可用，请稍后重试"  # 确保始终返回字符串

        # 处理响应
        full_response = []
        try:
            for line in response_2.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8').strip()
                    if decoded_line.startswith('data:'):
                        event_data = json.loads(decoded_line[5:])

                        # 核心事件处理逻辑
                        if event_data.get('event') == 'workflow_started':
                            print(f"🚀 工作流已启动 | ID: {event_data['data']['id']}")

                        elif event_data.get('event') == 'node_finished':
                            node_data = event_data['data']
                            # 提取节点输出内容
                            if node_data.get('outputs'):
                                content = node_data['outputs'].get('text', '')
                                if content.strip() and content not in full_response:
                                    full_response.append(content.strip())
                                    print(f"📥 收到节点输出: {content[:50]}...")  # 显示前50字符

                        elif event_data.get('event') == 'workflow_finished':
                            print(f"✅ 工作流完成 | 状态: {event_data['data']['status']}")
                            print(f"消耗token: {event_data['data']['total_tokens']}")

                        elif event_data.get('event') == 'message_end':
                            print("🏁 收到结束信号")
                            return ''.join(full_response)


        except Exception as e:

            logger.error(f"流处理异常: {str(e)}")

            return "响应处理异常"

            # 确保最终返回字符串

        return ''.join(full_response) or "无有效内容返回"
    except Exception as e:
        logger.error(f"全局异常: {str(e)}")
        return "生成过程发生错误"

if __name__ == "__main__":
    result=generate_makeup_tutorial()
    print("\n生成结果：")
    print(result)