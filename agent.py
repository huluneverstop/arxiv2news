#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arXiv资讯生成Agent
基于LangGraph和千问模型，自动生成arXiv论文的中文资讯
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

# LangGraph相关导入
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

# 千问模型导入
from dashscope import Generation

# 本地模块导入
from arxiv_search import ArxivSearcher
from paper_processor import PaperProcessor
from content_generator import ContentGenerator
from image_extractor import ImageExtractor
from output_formatter import OutputFormatter

# 获取日志器
logger = logging.getLogger(__name__)

class ArxivAgentState:
    """Agent状态管理类"""
    
    def __init__(self):
        self.query: str = ""
        self.papers: List[Dict[str, Any]] = []
        self.processed_papers: List[Dict[str, Any]] = []
        self.images: List[Dict[str, Any]] = []
        self.news_content: List[Dict[str, Any]] = []
        self.errors: List[str] = []
        self.current_step: str = ""
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "query": self.query,
            "papers_count": len(self.papers),
            "processed_count": len(self.processed_papers),
            "images_count": len(self.images),
            "news_count": len(self.news_content),
            "errors": self.errors,
            "current_step": self.current_step
        }

class ArxivAgent:
    """arXiv资讯生成Agent主类"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.state = ArxivAgentState()
        
        # 初始化各个组件
        self.searcher = ArxivSearcher()
        self.image_extractor = ImageExtractor()
        self.content_generator = ContentGenerator(api_key)
        self.output_formatter = OutputFormatter()
        
        # 构建工作流图
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """构建工作流图"""
        
        # 创建状态图
        workflow = StateGraph(ArxivAgentState)
        
        # 添加节点
        workflow.add_node("search_papers", self._search_papers_node)
        workflow.add_node("extract_images", self._extract_images_node)
        workflow.add_node("generate_content", self._generate_content_node)
        workflow.add_node("format_output", self._format_output_node)
        
        # 设置边和条件
        workflow.set_entry_point("search_papers")
        workflow.add_edge("search_papers", "extract_images")
        workflow.add_edge("extract_images", "generate_content")
        workflow.add_edge("generate_content", "format_output")
        workflow.add_edge("format_output", END)
        
        return workflow.compile()
    
    async def _search_papers_node(self, state: ArxivAgentState) -> ArxivAgentState:
        """搜索论文节点"""
        try:
            state.current_step = "searching_papers"
            logger.info(f"开始搜索论文: {state.query}")
            
            # 使用现有的arXiv搜索工具
            papers = self.searcher.search_papers(state.query, max_results=10)
            state.papers = papers
            
            logger.info(f"搜索完成，找到 {len(papers)} 篇论文")
            
        except Exception as e:
            error_msg = f"搜索论文时出错: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg)
            
        return state
    
    async def _process_papers_node(self, state: ArxivAgentState) -> ArxivAgentState:
        """处理论文节点"""
        try:
            state.current_step = "processing_papers"
            logger.info("开始处理论文信息")
            
            processed_papers = []
            for paper in state.papers:
                processed = self.processor.process_paper(paper)
                processed_papers.append(processed)
            
            state.processed_papers = processed_papers
            logger.info(f"论文处理完成，共处理 {len(processed_papers)} 篇")
            
        except Exception as e:
            error_msg = f"处理论文时出错: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg)
            
        return state
    
    async def _extract_images_node(self, state: ArxivAgentState) -> ArxivAgentState:
        """提取图片节点"""
        try:
            state.current_step = "extracting_images"
            logger.info("开始提取论文图片")
            
            all_images = []
            for paper in state.processed_papers:
                images = await self.image_extractor.extract_images(paper)
                all_images.extend(images)
            
            state.images = all_images
            logger.info(f"图片提取完成，共提取 {len(all_images)} 张图片")
            
        except Exception as e:
            error_msg = f"提取图片时出错: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg)
            
        return state
    
    async def _generate_content_node(self, state: ArxivAgentState) -> ArxivAgentState:
        """生成内容节点"""
        try:
            state.current_step = "generating_content"
            logger.info("开始生成中文资讯内容")
            
            news_content = []
            for paper in state.processed_papers:
                # 获取相关图片
                paper_images = [img for img in state.images if img.get('paper_id') == paper.get('id')]
                
                # 生成资讯内容
                news = await self.content_generator.generate_news(paper, paper_images)
                news_content.append(news)
            
            state.news_content = news_content
            logger.info(f"内容生成完成，共生成 {len(news_content)} 篇资讯")
            
        except Exception as e:
            error_msg = f"生成内容时出错: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg)
            
        return state
    
    async def _format_output_node(self, state: ArxivAgentState) -> ArxivAgentState:
        """格式化输出节点"""
        try:
            state.current_step = "formatting_output"
            logger.info("开始格式化输出")
            
            # 生成最终输出
            output = self.output_formatter.format_output(
                state.news_content,
                state.images,
                state.query
            )
            
            # 保存输出
            self.output_formatter.save_output(output, state.query)
            
            logger.info("输出格式化完成")
            
        except Exception as e:
            error_msg = f"格式化输出时出错: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg)
            
        return state
    
    async def run(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """运行Agent"""
        try:
            logger.info(f"开始运行arXiv资讯生成Agent，查询: {query}")
            
            # 初始化状态
            self.state = ArxivAgentState()
            self.state.query = query
            
            # 运行工作流
            final_state = await self.workflow.ainvoke(self.state)
            
            # 返回结果
            result = {
                "status": "success",
                "query": query,
                "papers_count": len(final_state.papers),
                "news_count": len(final_state.news_content),
                "images_count": len(final_state.images),
                "output_path": f"output/news_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "errors": final_state.errors
            }
            
            logger.info("Agent运行完成")
            return result
            
        except Exception as e:
            error_msg = f"Agent运行出错: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "query": query
            }

def main():
    """主函数"""
    # 从环境变量获取API密钥
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("请设置环境变量 DASHSCOPE_API_KEY")
        return
    
    # 创建Agent
    agent = ArxivAgent(api_key)
    
    # 运行示例
    query = "PU Learning"
    print(f"开始处理查询: {query}")
    
    # 异步运行
    result = asyncio.run(agent.run(query))
    
    print("处理结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
