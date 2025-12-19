#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容生成模块
使用千问模型生成arXiv论文的中文资讯内容
"""

import json
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from dashscope import Generation
import asyncio
import re
import httpx
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

class ContentGenerator:
    """内容生成器"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "qwen-plus-2025-09-11"  # Qwen3
        
        # 提示词模板
        self.content_prompt_template_method = """
            你是一个学术资讯生成器, 请将论文总结为一篇第三人称视角面向科技兴趣读者的小红书中文资讯贴，确保内容简洁、专业、易懂，适合中文读者阅读，字数控制在 450–600 字。
            请注意：你**只能**使用给定的论文信息，**不得凭空捏造任何数据和信息**，所有提具体数值需要用【】标注原句。使用“首次”、“初次”这类词语时也需要用【】标注原句。如果某些信息在输入中不存在，请在对应字段返回"NOT_PROVIDED"。

            要求：
            1. 标题：简洁明了且吸睛的标题（20字以内）
            2. 候选标题：5个候选标题，不要过于相似
            3. 详细论文总结：保持专业严谨，保留一定的技术细节，像科研解读笔记，输出时需要保留所要求的大纲标题，大纲如下：
            研究背景与问题（约 80–100 字）：简洁介绍研究的背景和问题，说明现有方法的不足和当前研究的重要性。
            方法核心（约 180–220 字）：清楚描述论文的方法框架、创新技术或模型，可以使用用简易的比喻/例子帮助理解复杂概念，但保持关键术语。
            实验与结果（约 120–150 字）：概述主要实验和结果，提供关键数据或指标对比，突出论文的创新性或效果。
            主要贡献与启发（约 80–120 字）：总结论文的学术贡献，指出研究启发，特别对后续研究的意义，请勿过分夸大。
            4. 话题标签：6-8个话题，包括领域、应用方向及相关技术，确保标签多样化且相关性强
            5. 领域内难以翻译的术语可以保留英文，但要提供中文解释

            论文信息：
            标题：{title}
            作者：{authors}
            摘要：{summary}
            分类：{categories}
            引言：{introduction}
            方法：{method}
            结论：{conclusion}

            请按照以下格式输出：
            标题：[生成的标题]

            备选标题：[候选标题1, 候选标题2]

            详细内容总结：[详细总结内容]

            话题标签：[话题标签1, 话题标签2]
            """

        self.content_prompt_template_survey = """
            你是一个学术资讯生成器, 请将论文总结为一篇第三人称视角面向科技兴趣读者的小红书中文资讯贴，确保内容简洁、专业、易懂，适合中文读者阅读，字数控制在 450–600 字。
            请注意：你**只能**使用给定的论文信息，不得凭空捏造任何数据。如果某些信息在输入中不存在，请在对应字段返回"NOT_PROVIDED"。

            要求：
            1. 标题：简洁明了且吸睛的标题（20字以内）
            2. 候选标题：5个候选标题，不要过于相似
            3. 详细论文总结：保持专业严谨，保留一定的技术细节，像科研解读笔记，输出时需要保留所要求的大纲标题，大纲如下：
            - **研究背景与问题**（约80–100字）：简洁介绍该领域的研究背景，解释为什么对该领域的综述研究非常重要。
            - **综述核心内容**（约180–220字）：概述综述文章涵盖的主题，关键领域和研究进展，并着重分析研究中的难点或争议。
            - **主要发现与趋势**（约100–150字）：总结综述中的主要发现、现有研究成果和当前趋势，指出研究中的空白或未来发展方向。
            - **启发与展望**（约80–100字）：总结综述的学术意义和对未来研究的启示，指出未来可能的研究路径和挑战。
            4. 话题标签：6-8个话题，包括领域、应用方向及相关技术，确保标签多样化且相关性强
            5. 领域内难以翻译的术语可以保留英文，但要提供中文解释
            
            论文信息：
            标题：{title}
            作者：{authors}
            摘要：{summary}
            分类：{categories}
            引言：{introduction}
            方法：{method}
            结论：{conclusion}

            请按照以下格式输出：
            标题：[生成的标题]

            备选标题：[候选标题1, 候选标题2]

            详细内容总结：[详细总结内容]

            话题标签：[话题标签1, 话题标签2]
            """

   
    async def generate_news(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """生成单篇论文的资讯内容"""
        try:
            logger.info(f"开始生成论文 {paper.get('id', 'unknown')} 的资讯内容")
            
            paper_structured = await self.parse_arxiv_html_stream(paper['links']['html'])

            if paper_structured is None:
                logger.warning(f"论文 {paper.get('id', 'unknown')} 结构化失败")
                return {'content': None}

            # 生成正文内容
            content_method = await self._generate_content_method(paper, paper_structured)
            
            if content_method == "":
                logger.warning(f"论文 {paper.get('id', 'unknown')} 资讯内容生成失败")
                return {'content': None}

            # 组合结果
            news = {
                'content': content_method,
                # 'content_B': content_B,
                # 'content_C': content_C,
            }

            logger.info(f"论文 {paper.get('id', 'unknown')} 资讯内容生成完成")
            return news
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"生成资讯内容时出错: {str(e)}")
            logger.error(f"详细错误信息:\n{error_details}")
            return None
    
    async def parse_arxiv_html_stream(self, url: str) -> dict:
        """
        流式解析arXiv HTML内容
        
        Args:
            url: arXiv HTML页面URL
        
        Returns:
            解析后的论文数据结构
        """
        # 初始化论文数据结构
        html_paper = {
            "title": None,
            # "authors": [],
            # "abstract": None,
            "sections": []
        }
        
        # 收集所有HTML内容
        html_content = ""
        async for chunk in self.fetch_arxiv_html_stream(url):
            html_content += chunk
        
        # 使用BeautifulSoup解析完整的HTML
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 标题
        title_tag = soup.find("h1", class_="ltx_title")
        if title_tag:
            html_paper["title"] = title_tag.get_text(" ", strip=True)

        # 章节递归解析

        html_paper["sections"] = self.parse_arxiv_by_headings(
                soup,
                content_root_selector=("article", {"class": "ltx_document"})
            )
        
        return html_paper

    def _new_section(self, title=None):
        return {
            "title": title,
            "figures": [],
            "tables": [],
            "subsections": []
        }

    
    def parse_arxiv_by_headings(self, soup: BeautifulSoup, content_root_selector=None):  # 例如 ("div", {"class": "ltx_document"})
        """
        解析 arXiv HTML（无嵌套<section>的情况），基于 h2/h3/h4 构建层级树。

        - 段落<p> -> {"text": "..."} 追加到当前层的 subsections
        - figure.ltx_figure -> 当前层的 figures
        - figure.ltx_table  -> 当前层的 tables
        - 跳过 .ltx_abstract 内的内容
        返回: {"sections": [ ...h2-level sections... ]}
        """
        # 选择解析根节点 未指定回退到默认根节点
        if content_root_selector:
            nodes = soup.find_all(*content_root_selector) if isinstance(content_root_selector, tuple) else soup.select(content_root_selector)
            root = None
            for node in nodes:
                # 跳过警告框
                if "package-alerts" in node.get("class", []):
                    continue
                root = node
                break
            if root is None:
                root = soup.body or soup
        else:
            # 优先正文 <article>，再兜底
            root = (
                soup.select_one("article.ltx_document")
                or soup.select_one("div.ltx_document:not(.package-alerts)")
                or soup.select_one("main")
                or soup.body
                or soup
                )   

        # 用“虚拟根”承载最上层 sections
        virtual_root = self._new_section(title=None)
        paper = virtual_root["subsections"]

        # 层级映射
        max_heading_level = self.find_max_heading_level(soup)
        heading_tags = [f"h{i}" for i in range(2, max_heading_level + 1)]
        level_of = {tag: int(tag[1]) for tag in heading_tags}  # {"h2":2, "h3":3, "h4":4}

        # 栈：[(level, section_dict)]，初始化用虚拟根 level=1
        stack = [(1, virtual_root)]

        def in_abstract(node):
            return node.find_parent(class_="ltx_abstract") is not None

        # 顺序遍历：只拿我们关心的“块级节点”，避免抓到 figcaption 内的 p
        blocks = root.find_all(list(heading_tags) + ["p", "figure"], recursive=True)

        for node in blocks:
            # 跳过摘要
            if in_abstract(node):
                continue
            # 避免抓到 figure 内部的 p（只保留 figure 自身）
            if node.name == "p" and node.find_parent("figure") is not None:
                continue

            # 处理标题：开新层
            if node.name in heading_tags:
                title = node.get_text(" ", strip=True)
                level = level_of[node.name]

                # 退栈到比当前 level 小的层
                while stack and stack[-1][0] >= level:
                    stack.pop()

                parent_level, parent_sec = stack[-1]
                new_sec = self._new_section(title=title)
                parent_sec["subsections"].append(new_sec)
                stack.append((level, new_sec))
                continue

            # 确定当前层（如果还没遇到任何标题，则挂到虚拟根）
            _, cur_sec = stack[-1]

            # 段落
            if node.name == "p":
                text = node.get_text(" ", strip=True)
                # 移除参考文献标记，如 [3], [72, 33] 等
                text = re.sub(r'\[\s*\d+(?:\s*,\s*\d+)*\s*\]', '', text)
                # 清理可能产生的多余空格
                text = re.sub(r'\s+', ' ', text).strip()
                if text:
                    cur_sec["subsections"].append({"text": text})
                continue

            # 图片 or 表格（按 class 判断）
            if node.name == "figure":
                classes = set(node.get("class", []))
                # 表格
                if "ltx_table" in classes:
                    caption_tag = node.find("figcaption")
                    table_info = {
                        "id": node.get("id"),
                        "caption": caption_tag.get_text(" ", strip=True) if caption_tag else None,
                        "content": node.get_text(" ", strip=True),
                    }
                    cur_sec["tables"].append(table_info)
                    continue

                # 图片
                if "ltx_figure" in classes or "ltx_graphics" in classes:
                    caption_spans = node.find_all("span", class_='ltx_caption')
                    for idx, img in enumerate(node.find_all("img")):
                        caption = node.find("figcaption")
                        if caption:
                            caption = caption.get_text(" ", strip=True)
                        else:
                            # 检查是否有足够的caption span
                            if idx < len(caption_spans):
                                caption = caption_spans[idx].get_text(" ", strip=True)
                            else:
                                caption = ""  # 如果没有对应的caption，使用空字符串
                        img_info = {
                            "id": img.get("id"),
                            "url": img.get("src") if img else None,
                            "caption": caption
                        }    
                        cur_sec["figures"].append(img_info)
                    continue

                # 其它不识别的 figure，忽略
                continue

        return paper

    def find_max_heading_level(self, soup):
        """
        在论文正文中寻找出现的最大 h 标签层级（h1-h6）。
        返回如 'h4'，如果没有找到任何 h 标签，则返回 None。
        
        Args:
            soup: BeautifulSoup对象，已经解析好的HTML
        """
        max_level = 0


        for section in soup.find_all("section", class_="ltx_section"):
            for tag in section.find_all(re.compile(r'^h[1-6]$')):
                level = int(tag.name[1])  # 取数字部分
                if level > max_level:
                    max_level = level
                    # max_tag = tag.name
        return max_level

    async def fetch_arxiv_html_stream(self, url: str, chunk_size: int = 8192) -> AsyncGenerator[str, None]:
        """
        使用httpx库流式读取arXiv HTML内容
        
        Args:
            url: arXiv HTML页面URL
            chunk_size: 每次读取的字节块大小
        
        Yields:
            解码后的HTML文本块
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream('GET', url) as response:
                    response.raise_for_status()
                    
                    buffer = ""
                    async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                        try:
                            # 解码字节块并添加到缓冲区
                            chunk_text = chunk.decode('utf-8', errors='ignore')
                            buffer += chunk_text
                            
                            # 当缓冲区达到一定大小时，yield出去
                            if len(buffer) >= chunk_size:
                                yield buffer
                                buffer = ""
                        
                        except UnicodeDecodeError as e:
                            logger.warning(f"解码错误: {e}")
                            continue
                    
                    # 返回剩余的缓冲区内容
                    if buffer:
                        yield buffer
                        
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"流式读取HTML内容失败: {str(e)}")
            logger.error(f"URL: {url}")
            logger.error(f"详细错误信息:\n{error_details}")
            # 返回空字符串，避免后续处理出错
            yield ""

    async def _generate_content_method(self, paper: Dict[str, Any], paper_structured: Dict[str, Any]) -> str:
        """生成正文内容"""
        try:
            # 获取论文类型
            paper_type = paper.get('paper_type', 'method')
            # 自动检测章节关键词
            try_count = 0
            introduction_content = ""
            method_content = ""
            conclusion_content = ""
            
            while try_count < 3:
                try_count += 1
                method_keywords = await self.detect_section_keywords(paper_structured)
                if method_keywords is None:
                    continue
                
                # 使用检测到的关键词获取章节内容
                introduction_content = self._get_section_content_by_keywords(paper_structured, ['introduction'])
                method_content = self._get_section_content_by_keywords(paper_structured, method_keywords['method'])
                conclusion_content = self._get_section_content_by_keywords(paper_structured, method_keywords['conclusion'])

                # 根据尝试次数决定检查条件
                if try_count < 3:
                    # 前两次尝试：要求所有三个内容都不为空
                    if introduction_content != "" and method_content != "" and conclusion_content != "":
                        break
                    else:
                        # 记录失败信息
                        if introduction_content == "":
                            logger.warning(f"第{try_count}次检测，introduction章节内容提取失败")
                        if method_content == "":
                            logger.warning(f"第{try_count}次检测，method章节内容提取失败")
                        if conclusion_content == "":
                            logger.warning(f"第{try_count}次检测，conclusion章节内容提取失败")
                else:
                    # 第三次尝试：允许method_content为空，但introduction和conclusion必须不为空
                    if introduction_content != "" and conclusion_content != "":
                        if method_content == "":
                            logger.warning(f"第{try_count}次检测，只有method章节内容提取失败，继续处理")
                        break
                    else:
                        # 记录失败信息
                        if introduction_content == "":
                            logger.warning(f"第{try_count}次检测，introduction章节内容提取失败")
                        if conclusion_content == "":
                            logger.warning(f"第{try_count}次检测，conclusion章节内容提取失败")
                        if method_content == "":
                            logger.warning(f"第{try_count}次检测，method章节内容提取失败")
            
            # 如果三次尝试后仍不满足条件，返回空字符串
            if introduction_content == "" or conclusion_content == "":
                logger.error("经过3次尝试，章节内容均提取失败，不继续处理")
                return ""
            
            if paper_type == 'method':
                prompt_method = self.content_prompt_template_method.format(
                    title=paper.get('title', ''),
                    authors=', '.join(paper.get('authors', [])),
                    summary=paper.get('summary', ''),
                    categories=', '.join(paper.get('categories', [])),
                    introduction=introduction_content,
                    method=method_content,
                    conclusion=conclusion_content,
                )
            elif paper_type == 'survey':
                prompt_method = self.content_prompt_template_survey.format(
                    title=paper.get('title', ''),
                    authors=', '.join(paper.get('authors', [])),
                    summary=paper.get('summary', ''),
                    categories=', '.join(paper.get('categories', [])),
                    introduction=introduction_content,
                    method=method_content,
                    conclusion=conclusion_content,
                )
            
            response = await self._call_qwen_api(prompt_method)
            content = response.strip()
            
            return content
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"生成正文内容失败 A: {str(e)}")
            logger.error(f"详细错误信息:\n{error_details}")
            return ""

    
    def _find_section_by_keyword(self, sections, keyword):
        keyword = keyword.lower()
        for sec in sections:
            if keyword in sec.get("title", "").lower():
                return sec
            result = self._find_section_by_keyword(sec.get("subsections", []), keyword)
            if result:
                return result
        return None

    def _find_section_by_keyword_path(self, sections, *keywords):
        """
        按路径查找章节：find_section_by_path(sections, "method", "overview")
        """
        current = None
        remaining = list(keywords)

        while remaining:
            kw = remaining[0]
            if current is None:
                # 第一层在根章节中找
                current = self._find_section_by_keyword(sections, kw)
            else:
                # 后续在当前章节的子章节中找
                current = self._find_section_by_keyword(current.get("subsections", []), kw)
            if not current:
                return None
            remaining.pop(0)
        return current

    def extract_titles_from_sections(self, sections: List[Dict[str, Any]]) -> List[str]:
        """
        递归提取 sections 树中所有的 title
        
        Args:
            sections: sections 列表，每个元素可能包含 title 和 subsections
            
        Returns:
            所有 title 的列表
        """
        titles = []
        
        for section in sections:
            # 如果当前 section 有 title，添加到结果中
            if 'title' in section and section['title']:
                titles.append(section['title'])
            
            # 如果当前 section 有 subsections，递归处理
            if 'subsections' in section and section['subsections']:
                subsections_titles = self.extract_titles_from_sections(section['subsections'])
                titles.extend(subsections_titles)
        
        return titles

    async def detect_section_keywords(self, paper_structured: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        使用千问 API 自动检测方法章节的关键词路径
        
        Args:
            paper_structured: 结构化的论文数据，包含 sections
            
        Returns:
            包含检测结果的列表，格式如 ['WorldDreamer', 'overall framework']
            列表中元素依次表示从根章节到目标章节的查找路径
        """
        try:
            # 提取所有标题
            sections = paper_structured.get('sections', [])
            all_titles = self.extract_titles_from_sections(sections)
            
            if not all_titles:
                logger.warning("未找到任何章节标题,")
                return None
            
            
            # 构建提示词
            prompt = self._build_section_detection_prompt(all_titles, paper_structured.get('title', ''))
            
            # 调用千问 API
            response = await self._call_qwen_api(prompt)
            
            # 解析响应
            result = self._parse_section_detection_response(response)
            
            return result
            
        except Exception as e:
            logger.error(f"检测章节关键词失败: {e}")
            return None

    def _build_section_detection_prompt(self, titles: List[str], title: str) -> str:
        """构建章节检测的提示词"""
        return f"""
        你是一名学术论文结构分析专家。你的任务是根据文章标题和带有层级信息的论文的章节标题列表，识别并返回以下两个章节的路径：

        1. **方法概述 (method)**  
        - 根章节：通常名为 "Method"、"Approach"、"Proposed Method"、论文提出的方法名字（如模型名）。  
        - 子章节：通常名为 "Overview"、"Framework"、"Architecture"、"General" 等。  
        - 注意：如果方法的概述部分没有明确的子章节标题，即方法和其内部字章节呈明显总分结构，这意味着方法概述可能直接写在根章节下，此时路径只有根章节。  

        2. **结论 (conclusion)**  
        - 常见命名："Conclusion"、"Conclusions"、"Discussion"、"Summary"。  
        - 通常结论部分会命名为conclusion，但也存在其他命名，如discussion、summary等。
        - 如果出现conclusion一般选择conclusion作为结论路径，无conclusion章节时才考虑discussion、summary等。
        ---

        ### 输入：章节标题列表
        {chr(10).join([f"- {title}" for title in titles])}
        ### 输入：文章标题
        {title}

        ### 输出格式（JSON）
        {{
            "method": ["关键词1", "关键词2"], 
            "conclusion": ["关键词"],
            "reasoning": "说明为什么选择这些章节作为方法概述和结论"
        }}

        要求：
        - 严格按输出格式返回，不要返回其他内容。
        - 路径关键词是从根章节到目标子章节的完整路径,所有关键词必须从所给章节标题中选择。
        - 输出时只保留核心关键词，不需要返回数字编号。
        - 如果未找到对应章节，请返回空数组 []。
        """


    def _parse_section_detection_response(self, response: str) -> Dict[str, List[str]]:
        """解析千问 API 的章节检测响应"""
        try:
            import re
            
            # 尝试直接解析JSON
            try:
                result = json.loads(response)
                return {
                    'introduction': result.get('introduction', ['introduction']),
                    'method': result.get('method', ['method']),
                    'conclusion': result.get('conclusion', ['conclusion'])
                }
            except json.JSONDecodeError:
                pass
            
            # 如果直接解析失败，尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                return {
                    'introduction': result.get('introduction', ['introduction']),
                    'method': result.get('method', ['method']),
                    'conclusion': result.get('conclusion', ['conclusion'])
                }
            
            # 如果都失败，返回默认值
            logger.warning("无法解析API响应为JSON，使用默认关键词")
            return {
                'introduction': ['introduction'],
                'method': ['method'],
                'conclusion': ['conclusion']
            }
            
        except Exception as e:
            logger.error(f"解析章节检测响应失败: {e}")
            return {
                'introduction': ['introduction'],
                'method': ['method'],
                'conclusion': ['conclusion']
            }

    def _get_section_content_by_keywords(self, paper_structured: Dict[str, Any], keywords: List[str]) -> str:
        """
        根据关键词路径获取章节内容
        
        Args:
            paper_structured: 结构化的论文数据
            keywords: 关键词路径列表，如 ['WorldDreamer', 'overall framework']
                     表示先找包含 'WorldDreamer' 的章节，再在其子章节中找包含 'overall framework' 的章节
            
        Returns:
            章节内容文本
        """
        try:
            sections = paper_structured.get('sections', [])
            section = self._find_section_by_keyword_path(sections, *keywords)
            
            if section:
                return self._collect_texts(section)
            else:
                logger.warning(f"未找到关键词对应的章节: {keywords}")
                return ""
                
        except Exception as e:
            logger.error(f"获取章节内容失败: {e}")
            return ""

    
    def _collect_texts(self, sec):
        """
        收集章节及其子章节中的所有 'text' 字段，用 '/n' 连接
        返回字符串，如 "Humans/nHowever/nWe."
        """
        texts = []
        if isinstance(sec, dict):
            # 收集当前章节的 text
            for sub in sec.get("subsections", []):
                if "text" in sub:
                    texts.append(sub["text"])
            # # 递归收集子章节
            # for sub in sec.get("subsections", []):
            #     texts.append(self._collect_texts(sub))
        return '/n'.join(filter(None, texts))  # 过滤空字符串，避免多余 '/n'
    
    async def _call_qwen_api(self, prompt: str) -> str:
        """调用千问API"""
        try:
            # 使用异步方式调用千问API
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                self._sync_call_qwen_api, 
                prompt
            )
            return response
            
        except Exception as e:
            logger.error(f"调用千问API失败: {str(e)}")
            raise e
    
    def _sync_call_qwen_api(self, prompt: str) -> str:
        """同步调用千问API"""
        try:
            response = Generation.call(
                model=self.model,
                prompt=prompt,
                api_key=self.api_key,
                max_tokens=2000,
                temperature=0.3
            )
            
            if response.status_code == 200:
                return response.output.text
            else:
                raise Exception(f"API调用失败: {response.message}")
                
        except Exception as e:
            logger.error(f"千问API调用失败: {str(e)}")
            raise e
