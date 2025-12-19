#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输出格式化模块
生成arXiv论文资讯的文档和配图形式输出
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List
import logging
import re

logger = logging.getLogger(__name__)

class OutputFormatter:
    """输出格式化器"""
    
    def __init__(self, timestamp: str, base_output_dir: str = "/media/home/pengyunning/arXiv2xhs/output"):
        self.timestamp = timestamp
        self.base_output_dir =os.path.join(base_output_dir, "output")
    
    def ensure_output_dir(self, output_dir: str):
        """确保输出目录存在"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"创建输出目录: {output_dir}")
    
    def format_output(self, news_content: List[Dict[str, Any]], query: str, papers: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """格式化输出内容"""
        try:
            logger.info("开始格式化输出内容")
            
            # 解析资讯内容
            parsed_news = []
            for i, news in enumerate(news_content):
                if news['content'] is None:
                    continue
                parsed = self._parse_news_content(news, papers[i] if papers and i < len(papers) else None)
                if parsed['content']['content_summary'] == 'NOT_PROVIDED':
                    continue
                parsed_news.append(parsed)
    
            
            # 生成输出
            output = {
                'title': f"arXiv查询query - {query}",
                'generation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'query': query,
                'news_content': parsed_news,
                # 'stats': stats,
                'total_news': len(parsed_news)
            }
            
            logger.info("输出内容格式化完成")
            return output
            
        except Exception as e:
            logger.error(f"格式化输出时出错: {str(e)}")
            return {}
    
    def _parse_news_content(self, news: Dict[str, Any], paper: Dict[str, Any] = None) -> Dict[str, Any]:
        """解析资讯内容"""
        content = news.get('content', '')
        # 解析每个内容版本
        parsed = self._parse_single_content(content)
        
        # 获取论文基本信息
        paper_info = {}
        if paper:
            paper_info = {
                'paper_id': paper.get('id', ''),
                'paper_title': paper.get('title', ''),
                'authors': paper.get('authors', []),
                'arxiv_link': paper.get('links', {}).get('abs', ''),
                'github_link': paper.get('links', {}).get('github', ''),
                'project_link': paper.get('links', {}).get('project', ''),
                'categories': paper.get('categories', []),
                'summary': paper.get('summary', '')
            }
        
        return {
            'paper_info': paper_info,
            'content': parsed,
        }
    
    def _parse_single_content(self, content: str) -> Dict[str, Any]:
        """解析单个内容版本"""
        if not content:
            return {
                'title': 'NOT_PROVIDED',
                'alternative_titles': [],
                'content_summary': 'NOT_PROVIDED',
                'tags': []
            }
        
        # 提取标题
        title = self._extract_section(content, '标题')
        
        # 提取备选标题
        alternative_titles = self._extract_alternative_titles(content)
        
        # 提取详细内容总结
        content_summary = self._extract_section(content, '详细内容总结')
        
        # 提取话题标签
        tags = self._extract_tags(content)
        
        return {
            'title': title,
            'alternative_titles': alternative_titles,
            'content_summary': content_summary,
            'tags': tags
        }
    
    def _extract_alternative_titles(self, content: str) -> List[str]:
        """提取备选标题"""
        try:
            # 查找备选标题部分
            start_pattern = "备选标题："
            start_pos = content.find(start_pattern)
            
            if start_pos == -1:
                start_pattern = "备选标题:"
                start_pos = content.find(start_pattern)
            
            if start_pos == -1:
                return []
            
            start_pos += len(start_pattern)
            
            # 查找下一个部分标题
            end_pos = len(content)
            for next_section in ['详细内容总结', '话题标签', '标题']:
                if next_section != '备选标题':
                    next_pos = content.find(f"{next_section}：", start_pos)
                    if next_pos != -1 and next_pos < end_pos:
                        end_pos = next_pos
                    
                    next_pos = content.find(f"{next_section}:", start_pos)
                    if next_pos != -1 and next_pos < end_pos:
                        end_pos = next_pos
            
            section_content = content[start_pos:end_pos].strip()
            if not section_content:
                return []
            
            # 解析标题列表
            titles = []
            # 尝试不同的分隔符
            for separator in [',', '，', '\n']:
                if separator in section_content:
                    titles = [t.strip() for t in section_content.split(separator) if t.strip()]
                    break
            
            if not titles:
                titles = [section_content.strip()]
            
            return titles
            
        except Exception as e:
            logger.warning(f"提取备选标题失败: {str(e)}")
            return []
    
    def _extract_tags(self, content: str) -> List[str]:
        """提取话题标签"""
        try:
            # 查找话题标签部分
            start_pattern = "话题标签："
            start_pos = content.find(start_pattern)
            
            if start_pos == -1:
                start_pattern = "话题标签:"
                start_pos = content.find(start_pattern)
            
            if start_pos == -1:
                return []
            
            start_pos += len(start_pattern)
            
            # 查找下一个部分标题
            end_pos = len(content)
            for next_section in ['标题', '备选标题', '详细内容总结']:
                if next_section != '话题标签':
                    next_pos = content.find(f"{next_section}：", start_pos)
                    if next_pos != -1 and next_pos < end_pos:
                        end_pos = next_pos
                    
                    next_pos = content.find(f"{next_section}:", start_pos)
                    if next_pos != -1 and next_pos < end_pos:
                        end_pos = next_pos
            
            section_content = content[start_pos:end_pos].strip()
            if not section_content:
                return []
            
            # 解析标签列表
            tags = []
            # 尝试不同的分隔符
            for separator in [',', '，', '\n']:
                if separator in section_content:
                    tags = [t.strip() for t in section_content.split(separator) if t.strip()]
                    break
            
            if not tags:
                tags = [section_content.strip()]
            
            return tags
            
        except Exception as e:
            logger.warning(f"提取话题标签失败: {str(e)}")
            return []
    
    def _extract_section(self, content: str, section_name: str) -> str:
        """提取内容中的特定部分"""
        try:
            # 查找部分标题
            start_pattern = f"{section_name}："
            start_pos = content.find(start_pattern)
            
            if start_pos == -1:
                start_pattern = f"{section_name}:"
                start_pos = content.find(start_pattern)
            
            if start_pos == -1:
                return "NOT_PROVIDED"
            
            start_pos += len(start_pattern)
            
            # 查找下一个部分标题
            end_pos = len(content)
            for next_section in ['标题', '备选标题', '详细内容总结', '话题标签']:
                if next_section != section_name:
                    next_pos = content.find(f"{next_section}：", start_pos)
                    if next_pos != -1 and next_pos < end_pos:
                        end_pos = next_pos
                    
                    next_pos = content.find(f"{next_section}:", start_pos)
                    if next_pos != -1 and next_pos < end_pos:
                        end_pos = next_pos
            
            section_content = content[start_pos:end_pos].strip()
            return section_content if section_content else "NOT_PROVIDED"
            
        except Exception as e:
            logger.warning(f"提取部分内容失败: {str(e)}")
            return "NOT_PROVIDED"
    
    def save_output(self, output: Dict[str, Any], query: str) -> List[str]:
        """保存输出到文件 - 每篇文章分开存储"""
        try:
            # 动态构建输出路径
            day_timestamp = datetime.now().strftime("%Y%m%d")
            # day_timestamp = "20250829"
            if query:
                query_dir = query.replace(' ', '_')
                output_dir = os.path.join(self.base_output_dir, day_timestamp, query_dir)
            else:
                output_dir = os.path.join(self.base_output_dir, day_timestamp)
            
            # 确保输出目录存在
            self.ensure_output_dir(output_dir)
            
            saved_files = []
            
            # 为每篇论文单独保存文件
            news_content = output.get('news_content', [])
            for i, news in enumerate(news_content):
                paper_info = news.get('paper_info', {})
                paper_id = paper_info.get('paper_id', f'paper_{i+1}')
                
                # 构建单篇论文的输出数据
                single_paper_output = {
                    'title': f"arXiv论文资讯 - {paper_info.get('paper_title', '未知标题')}",
                    'generation_time': output.get('generation_time', ''),
                    'query': query,
                    'paper_info': paper_info,
                    'content': news.get('content', {}),
                }
                
                # 生成文件名
                base_filename = f"news_{paper_id}_{self.timestamp}"
                
                # 保存JSON格式
                json_path = os.path.join(output_dir, f"{base_filename}.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(single_paper_output, f, ensure_ascii=False, indent=2)
                
                # 保存Markdown格式
                md_path = os.path.join(output_dir, f"{base_filename}.md")
                md_content = self._generate_single_paper_markdown(single_paper_output)
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
                
                saved_files.append(base_filename)
                logger.info(f"论文 {paper_id} 输出保存完成: {base_filename}")
            
            logger.info(f"所有输出保存完成，共 {len(saved_files)} 个文件")
            return saved_files
            
        except Exception as e:
            logger.error(f"保存输出时出错: {str(e)}")
            return []
    
    def _generate_single_paper_markdown(self, output: Dict[str, Any]) -> str:
        """生成单篇论文的Markdown内容"""
        try:
            paper_info = output.get('paper_info', {})
            
            md_content = f"# {output.get('title', '')}\n\n"
            md_content += f"生成时间: {output.get('generation_time', '')}\n\n"
            
            # 论文基本信息
            md_content += "## 📄 论文信息\n\n"
            md_content += f"**论文ID**: {paper_info.get('paper_id', '')}\n\n"
            md_content += f"**标题**: {paper_info.get('paper_title', '未知标题')}\n\n"
            md_content += f"**作者**: {', '.join(paper_info.get('authors', []))}\n\n"
            md_content += f"**arXiv链接**: {paper_info.get('arxiv_link', '')}\n\n"
            md_content += f"**GitHub链接**: {paper_info.get('github_link', '')}\n\n"
            md_content += f"**项目链接**: {paper_info.get('project_link', '')}\n\n"
            md_content += f"**分类**: {', '.join(paper_info.get('categories', []))}\n\n"
            
            # 论文摘要
            # summary = paper_info.get('summary', '')
            # if summary:
            #     md_content += f"**摘要**:\n{summary}\n\n"
            
            md_content += "---\n\n"
            
            # 三个版本的内容
            content_data = output.get('content', {})
            if content_data.get('title') != 'NOT_PROVIDED':
                md_content += f"## {content_data.get('title', '')}\n\n"
                
                # 备选标题
                alt_titles = content_data.get('alternative_titles', [])
                if alt_titles:
                    md_content += f"**备选标题**: {', '.join(alt_titles)}\n\n"
                
                # 内容总结
                summary = content_data.get('content_summary', '')
                if summary != 'NOT_PROVIDED':
                    md_content += f"**内容总结**:\n{summary}\n\n"
                
                # 话题标签
                tags = content_data.get('tags', [])
                if tags:
                    md_content += f"**话题标签**: {', '.join(tags)}\n\n"
                
                md_content += "---\n\n"
            
            return md_content
            
        except Exception as e:
            logger.error(f"生成单篇论文Markdown失败: {str(e)}")
            return f"# 生成失败\n\n{str(e)}"
    