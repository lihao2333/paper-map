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
        # 从环境变量读取，开源部署时配置 PAPER_MAP_API_KEY + PAPER_MAP_BASE_URL + PAPER_MAP_MODEL
        api_key = os.environ.get("PAPER_MAP_API_KEY", "")
        base_url = os.environ.get("PAPER_MAP_BASE_URL") or None
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,  # None 时使用 OpenAI 默认
        )
        self._model_name = os.environ.get("PAPER_MAP_MODEL", "gpt-4o-mini")


    def query_company_university_names(self, paper_text):
        # 截断文本，确保不超过模型限制
        truncated_text = self._truncate_text(paper_text)
        
        response = self._client.chat.completions.create(
            model=self._model_name,
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

    def summary(self, paper_text):
        # 截断文本，确保不超过模型限制
        truncated_text = self._truncate_text(paper_text)
        
        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": "你是一个 AI 专家， 善于总结论文"},
                {
                    "role": "user",
                    "content": """
                    请根据以下 abstract 精炼地总结出论文的核心价值。
                    
                    要求：
                    1. 用1-2句话概括论文的本质和创新点，从技术角度出发，避免被论文中的包装词汇迷惑
                    2. 说明相比同期工作的主要创新点和收益体现在哪里
                    3. 整体表达要简洁精炼，不要结构性展开，不要占用过多篇幅
                    4. 重点关注技术贡献和实际价值，而非表面描述

                abstract 内容：

                """
                    + truncated_text,
                },
            ],
            stream=False,
        )
        content = response.choices[0].message.content
        return content

    def extract_alias(self, paper_text):
        # 截断文本，确保不超过模型限制
        truncated_text = self._truncate_text(paper_text)
        
        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": "你是一个 AI 专家， 善于总结论文"},
                {
                    "role": "user",
                    "content": """
请从论文内容中提取论文的简称（alias）。

要求：
1. 简称通常是论文标题中出现的简短名称，例如：ViT、BERT、GPT、CLIP、SAM 等
3. 如果论文中没有简称，返回论文的完整标题（full_name）
4. 只返回简称或标题本身，不要添加任何解释、标点符号或其他文字
6. 注意不要返回引用的论文的简称
7. 如果没有简称就返回标题就可以了，不用强行返回一个不合适的简称
8. 认真阅读论文，确保理解了在输出简称。

示例：
- 论文提到 "BERT: Pre-training of Deep Bidirectional Transformers" → 返回：BERT
- 论文没有简称，标题是 "A Novel Approach to Machine Learning" → 返回：A Novel Approach to Machine Learning

论文内容：

"""
                    + truncated_text,
                },
            ],
            stream=False,
        )
        content = response.choices[0].message.content
        return content
    
    def extract_title(self, paper_text):
        """
        从论文文本中提取标题
        """
        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": "你是一个 AI 专家，善于从论文文本中提取标题"},
                {
                    "role": "user",
                    "content": """
请从论文内容中提取论文的完整标题（title）。

要求：
1. 标题通常在论文的开头部分
2. 只返回标题本身，不要添加任何解释、标点符号或其他文字
3. 保持标题的原始格式和大小写
4. 如果找不到标题，返回 "Unknown Title"

论文内容：

"""
                    + paper_text[:2000],  # 只使用前2000个字符
                },
            ],
            stream=False,
        )
        content = response.choices[0].message.content.strip()
        # 清理可能的引号
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        if content.startswith("'") and content.endswith("'"):
            content = content[1:-1]
        return content

    def _truncate_text(self, text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
        """
        截断文本，确保不超过最大长度限制
        优先保留论文开头部分（通常包含标题、摘要、作者信息等关键信息）
        
        Args:
            text: 原始文本
            max_length: 最大字符数限制
        
        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text
        
        # 如果文本过长，截取前面的部分
        # 论文的关键信息（标题、摘要、作者等）通常在开头
        truncated = text[:max_length]
        
        # 尝试在句子边界截断，避免截断单词
        # 查找最后一个句号、换行符或段落分隔符
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        last_double_newline = truncated.rfind('\n\n')
        
        # 优先在段落边界截断
        if last_double_newline > max_length * 0.8:  # 如果段落边界在80%位置之后
            truncated = truncated[:last_double_newline]
        elif last_newline > max_length * 0.8:  # 其次在换行符处截断
            truncated = truncated[:last_newline]
        elif last_period > max_length * 0.8:  # 最后在句号处截断
            truncated = truncated[:last_period + 1]
        
        return truncated + "\n\n[文本已截断，仅保留前部分内容]"
    
    def quyer_paper_info(self, paper_text):
        """
        从 paper 中提取所有关键信息
        """
        # 截断文本，确保不超过模型限制
        truncated_text = self._truncate_text(paper_text)
        
        if len(paper_text) > MAX_TEXT_LENGTH:
            print(f"Warning: Paper text too long ({len(paper_text)} chars), truncated to {len(truncated_text)} chars")
        
        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": "你是一个 AI 专家，善于从论文文本中提取结构化信息"},
                {
                    "role": "user",
                    "content": """
请从论文内容中提取以下所有关键信息，并以 JSON 格式返回。

输出格式（必须是合法的 JSON，可以直接被 json.loads() 解析）：
{
    "title": "论文完整标题",
    "alias": "论文简称",
    "abstract": "论文摘要",
    "summary": "论文总结",
    "company_names": ["公司1", "公司2"],
    "university_names": ["大学1", "大学2"]
}

字段提取要求：

1. title（标题）：
   - 提取论文的完整标题，通常在论文开头
   - 保持原始格式和大小写
   - 如果找不到，返回空字符串 ""

2. alias（简称）：
   - 优先提取论文的简称，通常是标题中出现的简短名称（如：ViT、BERT、GPT、CLIP、SAM）
   - 如果论文标题中没有简称，检查论文中是否包含 GitHub 链接（github.com/...）
   - 如果找到 GitHub 链接，可以从仓库名称（repository name）中提取可能的 alias
   - 例如：如果 GitHub 链接是 github.com/username/nerf-project，可以考虑使用 "nerf-project" 或其中的关键词作为 alias
   - 注意不要返回引用的其他论文的简称或 GitHub 仓库
   - 如果论文中没有简称且没有合适的 GitHub 仓库名，返回完整标题（与 title 相同）
   - 如果没有合适的简称，就返回标题，不要强行生成

3. abstract（摘要）：
   - 提取论文的 Abstract 部分
   - 保持原始格式，但去除多余的空行
   - 如果找不到，返回空字符串 ""

4. summary（总结）：
   - 用 1-2 句话精炼地概括论文的核心价值和技术创新点
   - 从技术角度出发，避免被论文中的包装词汇迷惑
   - 说明相比同期工作的主要创新点和收益
   - 重点关注技术贡献和实际价值，而非表面描述
   - 如果无法总结，返回空字符串 ""

5. company_names（公司名称）：
   - 仔细阅读论文的 Author Affiliation（作者单位）部分
   - 识别所有提到的公司（Company/Corporation/Inc./Ltd. 等）
   - 使用完整的机构名称，保持原始拼写
   - 如果找不到，返回空数组 []

6. university_names（大学名称）：
   - 仔细阅读论文的 Author Affiliation（作者单位）部分
   - 识别所有提到的大学（University/College/Institute 等）
   - 使用完整的机构名称，保持原始拼写
   - 如果找不到，返回空数组 []

JSON 格式要求：
- 必须是合法的 JSON 格式，可以直接被 json.loads() 解析
- 只返回 JSON 对象，不要有任何其他文字说明、代码块标记（如 ```json）或解释
- 使用双引号（"）而不是单引号（'）
- 字符串字段如果找不到，返回空字符串 ""
- 数组字段如果找不到，返回空数组 []
- 确保 JSON 格式正确，没有语法错误
- **重要**：如果字符串中包含反斜杠（\），必须进行转义。例如：
  * LaTeX 符号 `\Delta` 应该写成 `\\Delta`
  * LaTeX 符号 `\alpha` 应该写成 `\\alpha`
  * 其他包含反斜杠的内容也需要转义为 `\\`
- JSON 中有效的转义序列只有：`\"` `\\` `\/` `\b` `\f` `\n` `\r` `\t` `\\uXXXX`（其中 XXXX 是4位十六进制数）
- 所有其他反斜杠后跟字符的情况都必须转义反斜杠（写成 `\\`）

正确格式示例：
{"title": "Vision Transformer", "alias": "ViT", "abstract": "We present...", "summary": "提出了将 Transformer 应用于图像分类的方法...", "company_names": ["Google"], "university_names": []}

包含 LaTeX 符号的示例：
{"title": "$\\Delta$-NeRF: Incremental Refinement", "alias": "$\\Delta$-NeRF", "abstract": "...", "summary": "...", "company_names": [], "university_names": []}

从 GitHub 链接提取 alias 的示例：
- 如果论文标题是 "A Novel Approach to 3D Reconstruction"，GitHub 链接是 github.com/author/gsplat，alias 可以是 "gsplat"
- 如果论文标题中没有简称，但 GitHub 仓库名是 "nerfstudio"，alias 可以是 "nerfstudio"

论文内容：

"""
                    + truncated_text,
                },
            ],
            stream=False,
        )
        content = response.choices[0].message.content.strip()
        # 清理可能的代码块标记
        if content.startswith('```'):
            # 移除开头的 ```json 或 ```
            lines = content.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            content = '\n'.join(lines).strip()
        # 清理可能的引号（如果整个内容被引号包裹）
        if len(content) > 2 and content.startswith('"') and content.endswith('"'):
            # 检查是否是 JSON 对象（以 { 开头）
            if not content.strip().startswith('{'):
                content = content[1:-1]
        if len(content) > 2 and content.startswith("'") and content.endswith("'"):
            if not content.strip().startswith('{'):
                content = content[1:-1]
        
        # 修复 JSON 中的无效转义序列（如 LaTeX 符号 \Delta, \alpha 等）
        # JSON 中有效的转义序列：\" \\ \/ \b \f \n \r \t \uXXXX
        def fix_json_escapes(text):
            """修复字符串值中的无效转义序列"""
            result = []
            i = 0
            in_string = False
            escape_next = False
            
            while i < len(text):
                char = text[i]
                
                # 检查是否进入或退出字符串
                if char == '"' and not escape_next:
                    in_string = not in_string
                    result.append(char)
                    escape_next = False
                elif in_string and char == '\\' and not escape_next:
                    # 在字符串中遇到反斜杠
                    escape_next = True
                    if i + 1 < len(text):
                        next_char = text[i + 1]
                        # 检查是否是有效的转义序列
                        if next_char in ['"', '\\', '/', 'b', 'f', 'n', 'r', 't']:
                            # 有效转义，保留原样
                            result.append(char)
                            result.append(next_char)
                            i += 1
                            escape_next = False
                        elif next_char == 'u' and i + 6 <= len(text):
                            # \uXXXX 格式，检查是否是有效的十六进制
                            hex_chars = text[i+2:i+6]
                            if len(hex_chars) == 4 and all(c in '0123456789abcdefABCDEF' for c in hex_chars):
                                # 有效的 \uXXXX，保留原样
                                result.append(char)
                                result.append(next_char)
                                result.append(hex_chars)
                                i += 5  # 跳过 \uXXXX（已经处理了 \ 和 u，还需要跳过4个十六进制字符）
                                escape_next = False
                            else:
                                # 无效的 \u，转义反斜杠
                                result.append('\\\\')
                                result.append(next_char)
                                i += 1
                                escape_next = False
                        elif next_char == 'u':
                            # \u 后面字符不足，转义反斜杠
                            result.append('\\\\')
                            result.append(next_char)
                            i += 1
                            escape_next = False
                        else:
                            # 无效的转义序列，转义反斜杠
                            result.append('\\\\')
                            result.append(next_char)
                            i += 1
                            escape_next = False
                    else:
                        # 反斜杠在字符串末尾，转义它
                        result.append('\\\\')
                        escape_next = False
                else:
                    result.append(char)
                    escape_next = False
                i += 1
            
            return ''.join(result)
        
        # 尝试解析 JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # 如果失败，尝试修复转义序列后重新解析
            try:
                fixed_content = fix_json_escapes(content)
                return json.loads(fixed_content)
            except Exception as e2:
                print(f"Error parsing JSON from quyer_paper_info: {e}")
                print(f"After fix attempt: {e2}")
                print(f"Content: {content[:500]}...")  # 只打印前500个字符
                import traceback
                traceback.print_exc()
                return None
        except Exception as e:
            print(f"Error parsing JSON from quyer_paper_info: {e}")
            print(f"Content: {content[:500]}...")  # 只打印前500个字符
            import traceback
            traceback.print_exc()
            return None



if __name__ == "__main__":
    import sys
    ai_api = AiApi()
    # 用法: python ai_api.py <paper.txt 路径>
    path = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"
    paper_text = open(path, encoding="utf-8").read()
    #result = ai_api.query_company_university_names(paper_text)
    #print(result)
    #result = ai_api.summary(paper_text)
    #print(result)
    #result = ai_api.extract_alias(paper_text)
    result = ai_api.quyer_paper_info(paper_text)
    print(result)
