#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文质量打分模块
使用千问模型对arXiv论文进行多维度质量评估
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from dashscope import Generation

logger = logging.getLogger(__name__)

class PaperQualityScorer:
    """论文质量打分器 - 规则层+LLM层混合评分"""
    
    def __init__(self, api_key: str, w_rule: float = 0.3, w_llm: float = 0.7):
        self.api_key = api_key
        self.model = "qwen-plus-2025-07-14"  # Qwen3
        # self.w_rule = w_rule  # 规则层 重
        self.min_score = 6.0
        
        # 顶会列表（可根据需要扩展）
        self.top_conferences = {
            'cs.CV': ['CVPR', 'ICCV', 'ECCV', 'NeurIPS', 'ICML', 'ICLR'],
            'cs.LG': ['NeurIPS', 'ICML', 'ICLR', 'AAAI', 'IJCAI'],
            'cs.CL': ['ACL', 'EMNLP', 'NAACL', 'TACL', 'CL'],
            'cs.AI': ['AAAI', 'IJCAI', 'NeurIPS', 'ICML', 'ICLR'],
            'cs.RO': ['ICRA', 'IROS', 'RSS', 'CoRL'],
            'cs.CR': ['CCS', 'S&P', 'USENIX Security', 'NDSS', 'CRYPTO'],
            'cs.SE': ['ICSE', 'FSE', 'ASE', 'OOPSLA', 'PLDI'],
            'cs.DC': ['OSDI', 'SOSP', 'NSDI', 'FAST', 'ATC'],
            'cs.NI': ['SIGCOMM', 'INFOCOM', 'NSDI', 'IMC'],
            'cs.DS': ['STOC', 'FOCS', 'SODA', 'ICALP', 'ESA']
        }
        
        # 质量评估和文章类型分类提示词模板
        self.quality_prompt_template = """
            你是一名学术论文质量评估专家。请基于给定的论文的有限信息（标题、摘要、分类、作者、评论），对论文进行初步的多维度质量评估，并判断文章类型。  
            注意：输入信息仅包含摘要等元数据，没有完整正文和实验细节，请避免臆测；如果信息不足，请在评分理由中明确说明"基于摘要有限信息的推断"。  

            论文信息：
            标题：{title}
            摘要：{summary}
            分类：{categories}
            作者：{authors}
            评论：{commment}

            请完成以下两个任务：

            **任务1：质量评估**
            包含以下四个维度，请对论文进行评分（1-10分，10分为最高分）：

            1. **新颖性 (Novelty)**: 研究是否提出了新的问题、方法或应用方向？是否在已有工作上有明显改进？
            2. **研究可靠性 (Research Reliability)**: 从摘要描述判断方法是否合理、技术思路是否可行、逻辑是否自洽。  
            3. **潜在影响力 (Potential Impact)**: 研究方向是否重要？成果是否有可能在学术界或应用领域产生影响？
            4. **表达与结构 (Clarity & Structure)**: 摘要是否写作清晰、逻辑连贯、结构规范？是否存在逻辑漏洞或表达问题？

            | 维度 | 9–10 分 | 7–8 分 | 5–6 分 | 1–4 分 |
            |------|---------|--------|--------|--------|
            | 新颖性 | 具有重大创新或突破，可能开启新方向 | 有一定创新性或改进 | 与已有工作差异有限 | 几乎无创新，重复已有工作 |
            | 研究可靠性 | 方法完整且合理，逻辑严谨 | 方法基本合理，有小缺口或不明确之处 | 技术合理性不足，描述模糊 | 存在明显不可靠或不合逻辑的地方 |
            | 潜在影响力 | 极具影响力，可能推动领域发展 | 有一定价值，可能在特定场景应用 | 价值有限，影响较小 | 基本无潜在影响或应用意义 |
            | 表达与结构 | 表达清晰，逻辑严谨，结构规范 | 大体清晰，但有少量问题 | 表达一般，结构不够紧凑 | 表达混乱或逻辑性差 |

            **任务2：文章类型分类**
            请根据论文特征判断文章属于以下哪种类型，准确输出类型关键词，不要输出其他内容:

            综述型：survey
            新方法型：method
            
            请按照以下JSON格式输出结果：

            {{
                "novelty": 8,
                "research_reliability": 7,
                "potential_impact": 6,
                "clarit_structure": 8,
                "overall_score": 7.25,
                "paper_type": "method",
                "paper_type_reason": "论文提出了新的算法模型，实验设计严谨",
                "reasoning": {{
                    "novelty_reason": "论文提出了新的注意力机制，在现有方法基础上有所创新",
                    "research_reliability_reason": "技术方案合理，实验设计较为完整，但缺乏与更多baseline的对比",
                    "potential_impact_reason": "在计算机视觉领域有潜在应用价值，但实际部署可能面临挑战",😟
                    "clarit_structure_reason": "写作清晰，逻辑结构合理，实验数据充分，无明显水文特征"
                }},
                "confidence": 0.85
            }}
             """

    def _categorize_url(self, url: str) -> str:
        """
        对URL进行分类
        
        Args:
            url: 要分类的URL
            
        Returns:
            分类结果: 'github', 'project', 'other'
        """
        url_lower = url.lower()
        
        # GitHub链接
        if 'github.com' in url_lower:
            return 'github'
        else:
            return 'project'

    def _rule_filter(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        规则层筛选：检查论文是否满足进入LLM层的基本条件
        条件：是顶会 OR 有项目/github链接（至少满足一个）
        返回: {"passed": bool, "details": {...}}
        """
        import re
        
        details = {
            "is_top_conference": False,
            "has_links": False,
            "conference_name": None
        }
        
        # 1. 检查是否为顶会
        journal_ref = paper.get('journal_ref', '')
        comment = paper.get('comment', '')
        publication_text = f"{journal_ref} {comment}".upper()
        paper_categories = paper.get('categories', [])
        
        for category in paper_categories:
            if category in self.top_conferences:
                for conf in self.top_conferences[category]:
                    if conf.upper() in publication_text:
                        details["is_top_conference"] = True
                        details["conference_name"] = conf
                        break
                if details["is_top_conference"]:
                    break
        
        # 2. 检查是否有项目/github链接
        abstract = paper.get('summary', '')
        full_text = f"{abstract} {comment}"
        
        # 使用提供的链接检测正则表达式
        link_pattern = re.compile(r'https?://[^\s]+', re.IGNORECASE)
        link_matches = link_pattern.findall(full_text)
        
        # 对找到的链接进行分类
        if link_matches:
            details["has_links"] = True
            
            # 对每个链接进行分类
            for link in link_matches:
                link_type = self._categorize_url(link)
                if link_type == 'github':
                    paper['links']['github']=link
                else:
                    paper['links']['project']=link

        # 判断是否通过筛选
        passed = details["is_top_conference"] or details["has_links"]
        
        return {
            "passed": passed,
            "details": details
        }

    async def llm_filter(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM层评分：基于新颖性、技术深度、应用价值、领域贡献，同时判断文章类型
        返回: {"llm_score": 0-10, "paper_type": "A/B/C", "details": {...}}
        """
        try:
            # 构建提示词
            prompt = self.quality_prompt_template.format(
                title=paper.get('title', ''),
                summary=paper.get('summary', ''),
                categories=', '.join(paper.get('categories', [])),
                authors=', '.join(paper.get('authors', [])),
                commment=paper.get('comment', '')
            )
            
            # 调用千问API
            response = await self._call_qwen_api(prompt)
            
            # 解析JSON响应
            llm_result = self._parse_score_response(response) 
            
            return {
                "llm_score": llm_result.get('overall_score', 0.0),
                "llm_details": llm_result,
                "paper_type": llm_result.get('paper_type', 'method'),
                "paper_type_reason": llm_result.get('paper_type_reason', '默认为method'),
            }
            
        except Exception as e:
            logger.error(f"LLM评分失败: {str(e)}")
            return {
                "llm_score": 0.0,
                "llm_details": self._get_default_score(paper),
                "paper_type": "method",
                "paper_type_reason": "出现错误，默认为method",
            }

    async def _score_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """对单篇论文进行混合质量评分（规则层筛选+规则层评分+LLM层）"""
        try:
            logger.info(f"开始评估论文质量: {paper.get('id', 'unknown')}")
            
            # 1. 规则层筛选
            filter_result = self._rule_filter(paper)
            if not filter_result["passed"]:
                logger.info(f"论文 {paper.get('id', 'unknown')} 未通过规则层筛选，跳过LLM层评分")
                return {
                    "paper_id": paper.get('id', ''),
                    "paper_title": paper.get('title', ''),
                    "rule_passed": filter_result["passed"],
                    "rule_details": filter_result["details"],
                    "llm_score": 0.0,
                    "llm_details": {}

                }
            
            # 2. LLM层评分（包含文章类型判断）
            llm_result = await self.llm_filter(paper)
            llm_score = llm_result["llm_score"]
            llm_details = llm_result["llm_details"]
            paper_type = llm_result["paper_type"]
            paper_type_reason = llm_result["paper_type_reason"]
        
            # 3. 组合结果
            score_result = {
                "paper_id": paper.get('id', ''),
                "paper_title": paper.get('title', ''),
                "rule_passed": filter_result["passed"],
                "rule_details": filter_result["details"],
                "rule_score": 1.0 if filter_result["passed"] else 0.0,  # 规则层通过为1.0，否则为0.0
                "llm_score": llm_score,
                "llm_details": llm_details,
                "paper_type": paper_type,
                "paper_type_reason": paper_type_reason,
            }
            paper['paper_type'] = paper_type

            
            logger.info(f"论文 {paper.get('id', 'unknown')} 质量评估完成 - 得分: {llm_score:.2f}, 类型: {paper_type}")
            return score_result
            
        except Exception as e:
            logger.error(f"评估论文质量时出错: {str(e)}")
            return {
                    "paper_id": paper.get('id', ''),
                    "paper_title": paper.get('title', ''),
                    "rule_passed": filter_result["passed"],
                    "rule_details": filter_result["details"],
                    "rule_score": 1.0 if filter_result["passed"] else 0.0,
                    "llm_score": 0.0,
                    "llm_details": {},
                    "paper_type": "method",
                    "paper_type_reason": "出现错误，默认为method",

                }

    
    async def batch_score_papers(self, papers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量评估论文质量并过滤低质量论文"""
        try:
            logger.info(f"开始批量评估 {len(papers)} 篇论文的质量")
            
            scored_papers = []
            rule_filtered_count = 0
            score_filtered_count = 0
            total_processed = 0
            
            for i, paper in enumerate(papers):
                logger.info(f"正在评估第 {i+1}/{len(papers)} 篇论文...")
                
                # 评估单篇论文
                score_result = await self._score_paper(paper)
                total_processed += 1
                
                # 检查是否被规则层筛选掉
                rule_passed = score_result.get('rule_passed', False)
                if rule_passed:
                    # 检查是否达到最低分数要求
                    logger.info(f"论文 {paper.get('id', 'unknown')} 通过规则层筛选")
                    total_score = score_result.get('llm_score', 0)
                    if total_score >= self.min_score:
                        scored_papers.append({
                            'paper': paper,
                            'quality_score': score_result
                        })
                        logger.info(f"论文 {paper.get('id', 'unknown')} 通过质量筛选 (总分: {total_score:.2f})")
                    else:
                        score_filtered_count += 1
                        logger.info(f"论文 {paper.get('id', 'unknown')} 未通过质量筛选 (总分: {total_score:.2f})")
                
                else:
                    rule_filtered_count += 1
                    logger.info(f"论文 {paper.get('id', 'unknown')} 未通过规则层筛选")
                    continue
                
                
                # 添加延迟避免API限制
                await asyncio.sleep(1)
            
            logger.info(f"批量评估完成，通过筛选: {len(scored_papers)} 篇，规则层过滤: {rule_filtered_count} 篇，分数过滤: {score_filtered_count} 篇")
            
            return {
                'scored_papers': scored_papers,
                'statistics': {
                    'total_processed': total_processed,
                    'rule_filtered': rule_filtered_count,
                    'score_filtered': score_filtered_count,
                    'passed': len(scored_papers),
                    'rule_filter_rate': rule_filtered_count / total_processed if total_processed > 0 else 0,
                    'score_filter_rate': score_filtered_count / total_processed if total_processed > 0 else 0,
                    'final_pass_rate': len(scored_papers) / total_processed if total_processed > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"批量评估论文质量时出错: {str(e)}")
            return {
                'scored_papers': [],
                'statistics': {
                    'total_processed': 0,
                    'rule_filtered': 0,
                    'score_filtered': 0,
                    'passed': 0,
                    'rule_filter_rate': 0,
                    'score_filter_rate': 0,
                    'final_pass_rate': 0
                }
            }
    
    def _parse_score_response(self, response: str) -> Dict[str, Any]:
        """解析千问API的JSON响应"""
        try:
            import json
            import re
            
            # 尝试直接解析JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass
            
            # 如果直接解析失败，尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            
            # 如果都失败，返回默认评分
            logger.warning("无法解析API响应为JSON，使用默认评分")
            return self._get_default_score()
            
        except Exception as e:
            logger.error(f"解析评分响应失败: {str(e)}")
            return self._get_default_score()
    
    def _get_default_score(self, paper: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取默认评分（当API调用失败时使用）"""
        if paper:
            
            return {
                    "novelty": 0,
                    "research_reliability": 0,
                    "potential_impact": 0,
                    "clarit_structure": 0,
                    "overall_score": 0.0,
                    "paper_type": "method",
                    "paper_type_reason": "默认为method",
                    "reasoning": {
                        "novelty_reason": "无法评估，API调用失败",
                        "research_reliability_reason": "无法评估，API调用失败",
                        "potential_impact_reason": "无法评估，API调用失败",
                        "clarit_structure_reason": "无法评估，API调用失败"
                    },
                    "confidence": 10.0
                }
        else:
            return {
                    "novelty": 0,
                    "research_reliability": 0,
                    "potential_impact": 0,
                    "clarit_structure": 0,
                    "overall_score": 0.0,
                    "paper_type": "method",
                    "paper_type_reason": "默认为method",
                    "reasoning": {
                        "novelty_reason": "无法评估，不存在论文",
                        "research_reliability_reason": "无法评估，不存在论文",
                        "potential_impact_reason": "无法评估，不存在论文",
                        "clarit_structure_reason": "无法评估，不存在论文"
                    },
                    "confidence": 10.0
                }
    
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
                temperature=0.3  # 降低温度以获得更稳定的评分
            )
            
            if response.status_code == 200:
                return response.output.text
            else:
                raise Exception(f"API调用失败: {response.message}")
                
        except Exception as e:
            logger.error(f"千问API调用失败: {str(e)}")
            raise e
    
    def generate_quality_report(self, batch_result: Dict[str, Any]) -> Dict[str, Any]:
        """生成质量评估报告"""
        try:
            scored_papers = batch_result.get('scored_papers', [])
            statistics = batch_result.get('statistics', {})
            
            if not scored_papers:
                return {
                    "filter_statistics": {
                        "passed": 0,
                        "rule_filtered": statistics.get('rule_filtered', 0),
                        "score_filtered": statistics.get('score_filtered', 0)
                    },
                    "paper_type_counts": {
                        "method": 0,
                        "survey": 0
                    },
                    "papers": []
                }
            
            # 1. 筛选统计
            filter_stats = {
                "passed": len(scored_papers),
                "rule_filtered": statistics.get('rule_filtered', 0),
                "score_filtered": statistics.get('score_filtered', 0)
            }
            
            # 2. 文章类型统计
            paper_types = [item['quality_score'].get('paper_type', 'method') for item in scored_papers]
            type_counts = {
                'method': paper_types.count('method'),
                'survey': paper_types.count('survey')
            }
            
            # 3. 每篇论文的详细信息
            papers_detail = []
            for item in scored_papers:
                paper_info = {
                    "id": item['paper']['id'],
                    "title": item['paper']['title'],
                    "rule_score": item['quality_score']['rule_score'],
                    "llm_score": item['quality_score']['llm_score'],
                    "paper_type": item['quality_score'].get('paper_type', 'method'),
                    "rule_details": item['quality_score'].get('rule_details', {}),
                    "llm_details": item['quality_score'].get('llm_details', {})
                }
                papers_detail.append(paper_info)
            
            # 生成报告
            report = {
                "filter_statistics": filter_stats,
                "paper_type_counts": type_counts,
                "papers": papers_detail
            }
            
            return report
            
        except Exception as e:
            logger.error(f"生成质量报告失败: {str(e)}")
            return {"error": str(e)}
