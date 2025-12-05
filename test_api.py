# Please install OpenAI SDK first: `pip3 install openai`
import os
from openai import OpenAI
import json
import re

# Token 估算：通常 1 token ≈ 4 个字符（保守估计）
# 模型最大上下文长度：131072 tokens
# 预留一些空间给 prompt 和响应，实际文本限制设为 100000 tokens ≈ 400000 字符
MAX_TEXT_LENGTH = 400000  # 字符数限制


class AiApi:
    def __init__(self):
        # 从环境变量读取，避免泄露。配置 PAPER_MAP_API_KEY、PAPER_MAP_BASE_URL、PAPER_MAP_MODEL
        api_key = os.environ.get("PAPER_MAP_API_KEY", "")
        base_url = os.environ.get("PAPER_MAP_BASE_URL") or None
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def test(self):
        response = self._client.chat.completions.create(
            model="glm-4.6",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {
                    "role": "user",
                    "content": "Hello, how are you?",
                },
            ],
        )
        print(response.choices[0].message.content)


    def query_company_university_names(self, paper_text):
        # 截断文本，确保不超过模型限制
        truncated_text = self._truncate_text(paper_text)
        
        response = self._client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {
                    "role": "user",
                    "content": """
请根据论文内容提取作者所属的公司和大学信息。

要求：
1. 仔细阅读论文的 Author Affiliation（作者单位）部分，通常在论文开头或作者列表附近
2. 识别所有提到的公司（Company/Corporation/Inc.等）和大学（University/College/Institute等）
3. 使用完整的机构名称，保持原始拼写
4. 如果论文中没有相关信息，返回空列表

返回格式要求：
- 必须是合法的 JSON 格式，可以直接被 json.loads() 解析
- 只返回 JSON 对象，不要有任何其他文字说明、代码块标记或解释
- 使用双引号（"）而不是单引号（'）
- 如果某个类别没有找到，返回空列表 []

正确格式示例：
{"company_names": ["Google", "Microsoft Corporation"], "university_names": ["Stanford University", "MIT"]}

论文内容：

"""
                    + truncated_text,
                },
            ],
            stream=False,
        )
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            print(f"Content: {content}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    ai_api = AiApi()
    ai_api.test()