#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arXiv文章搜索
使用arxiv库搜索文章
"""

import arxiv
import json
import os
from datetime import datetime
from typing import List, Dict, Any
import logging
from itertools import islice

# 获取日志器
logger = logging.getLogger(__name__)

class ArxivSearcher:
    def __init__(self, work_path: str, timestamp: str):
        self.output_dir = work_path
        self.timestamp = timestamp
        self.client = arxiv.Client(
            page_size=100,  # 减少每页获取的论文数量
            delay_seconds=3,
            num_retries=3
        )
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        logger.info(f"输出目录: {self.output_dir}")
    
    def search_papers(self, query: str, id_list: List[str] = None, time_code: str = None, category: str = None, start_index: int = 0, max_results: int = 10,
            sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance, 
            sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending) -> List[Dict[str, Any]]:
        """
        搜索arXiv论文
        
        Args:
            query: 搜索关键词 "deep learning"
            id_list: 搜索id列表，精确查找
            time_code: 起始时间代码
            category: 搜索类别，默认cs.*
            start_index: 起始索引，默认0
            max_results: 最大结果数量 50
            sort_by: 排序方式 SortCriterion.Relevance / SortCriterion.SubmittedDate
            sort_order: 排序顺序 SortOrder.Ascending / SortOrder.Descending

        Returns:
            结构化论文信息
        """
        try:
            
            logger.info(f"开始搜索")

            # 使用arxiv库搜索
            search_params = {
                'sort_by': sort_by,
                'sort_order': sort_order
            }

            # 构造查询
            # 优先查询精准id列表
            # 构造查询
            # 优先查询精准id列表
            if id_list: 
                search_params['id_list'] = id_list
                search_params['max_results'] = 1
            else:
                arxiv_query = f'cat:cs.* AND submittedDate:[{time_code} TO 30000101]'
                if query:
                    arxiv_query = f'{query} AND '+arxiv_query
                if category:
                    category_query='('+' OR '.join([f'cat:{c}' for c in category])+')'
                    arxiv_query = arxiv_query.replace('cat:cs.*', f'{category_query}')
                
                search_params['query'] = arxiv_query
                
            search = arxiv.Search(**search_params)
            
            # 获取搜索结果
            papers = []
            for result in islice(self.client.results(search), start_index, start_index + max_results):                
                paper = self._convert_to_dict(result)
                if paper:
                    papers.append(paper)
                
                # 检查是否达到最大结果数
                if len(papers) >= max_results:
                    break
            
            logger.info(f"搜索到 {len(papers)} 篇符合条件的论文")
            return papers
            
        except Exception as e:
            logger.error(f"搜索论文时出错: {str(e)}")
            return []
    
    def _convert_to_dict(self, result: arxiv.Result) -> Dict[str, Any]:
        """
        将arxiv.Result对象转换为字典
        
        Args:
            result: arxiv.Result对象
        
        Returns:
            结构化论文信息字典
        """
        try:
            # 提取基本信息
            paper = {
                'id': result.entry_id.split('/')[-1],  # 提取arXiv ID
                'title': result.title,
                'authors': [author.name for author in result.authors],
                'summary': result.summary,
                'categories': result.categories,
                'primary_category': result.primary_category,
                'published': result.published.isoformat() if result.published else None,
                'updated': result.updated.isoformat() if result.updated else None,
                'doi': result.doi,
                'journal_ref': result.journal_ref,
                'primary_category': result.primary_category,
                'comment': result.comment,
                'links': {
                    'abs':result.entry_id.replace('http://', 'https://'),
                    'pdf':result.entry_id.replace('/abs/', '/pdf/').replace('http://', 'https://'),
                    'html':result.entry_id.replace('/abs/', '/html/').replace('http://', 'https://'),
                    'e-print':result.entry_id.replace('/abs/', '/e-print/').replace('http://', 'https://')
                }
            }
            
            return paper
            
        except Exception as e:
            logger.error(f"转换论文信息时出错: {str(e)}")
            return None
    
    def save_results(self, papers: List[Dict[str, Any]], query: str, format: str = 'json'):
        """
        保存搜索结果
        
        Args:
            papers: 论文列表
            query: 搜索关键词
            format: 输出格式 ('json', 'txt', 'csv')
        """
        
        if format == 'json':
            filename = f"{self.output_dir}/{self.timestamp}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
            logger.info(f"结果已保存到: {filename}")
            
        elif format == 'csv':
            import csv
            filename = f"{self.output_dir}/{query.replace(' ', '_')}.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['标题', '作者', '分类', '发布时间', '摘要', '链接'])
                
                for paper in papers:
                    authors_str = '; '.join(paper['authors'])
                    categories_str = '; '.join(paper['categories'])
                    links_str = '; '.join([f"{link['title']}: {link['url']}" for link in paper['links']])
                    
                    writer.writerow([
                        paper['title'],
                        authors_str,
                        categories_str,
                        paper['published'],
                        paper['summary'],
                        links_str
                    ])
            
            logger.info(f"结果已保存到: {filename}")
    