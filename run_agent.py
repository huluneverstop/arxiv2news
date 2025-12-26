#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arXiv资讯生成Agent主入口
工作流程：搜索-质量检查-生成资讯-格式化输出-保存文件-下载图片
"""

import os
import json
import asyncio
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

# 导入各个模块
from arxiv_search import ArxivSearcher
from paper_quality_scorer import PaperQualityScorer
from content_generator import ContentGenerator
from output_formatter import OutputFormatter
from image_extractor import ImageExtractor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'run_agent_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

async def main_workflow(query: str, id_list: List[str], category: str = None, time_code: str = None, max_results: int = 10, start_index:int=0,min_quality_score: float = 6.0, work_dir:str =None):
    """主工作流程"""
    
    os.chdir(work_dir)
    logger.info(f"工作路径设置为: {work_dir}")

    load_dotenv()
    
    # 获取API密钥
    api_key = os.getenv('API_KEY')
    if not api_key:
        logger.error("请提供千问API密钥")
        return
    
    # 创建时间戳
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    day_timestamp = datetime.now().strftime('%Y%m%d')
    output_dir = f"output/{day_timestamp}"
    
    try:

        
        # 1. 搜索论文
        logger.info(f"步骤1: 搜索论文 - {query}")
        searcher = ArxivSearcher(output_dir, timestamp)
        papers = searcher.search_papers(query=query, id_list=id_list, category=category, time_code=time_code, start_index=start_index, max_results=max_results)
        
        if not papers:
            logger.error("未找到任何论文")
            return
        
        logger.info(f"搜索完成，找到 {len(papers)} 篇论文")
        
        # 保存搜索结果
        logger.info("保存搜索结果")
        searcher.save_results(papers, query, format='json')
        
        # 2. 质量检查
        if query and not id_list:
            logger.info("步骤2: 质量检查")
            quality_scorer = PaperQualityScorer(api_key)
            quality_result = await quality_scorer.batch_score_papers(papers)
            
            # 过滤低质量论文
            scored_papers = quality_result.get('scored_papers', [])
            filtered_papers = []
            
            for item in scored_papers:
                paper = item['paper']
                quality_score = item['quality_score']
                llm_score = quality_score.get('llm_score', 0)
                
                if llm_score >= min_quality_score:
                    filtered_papers.append(item)
                else:
                    logger.info(f"论文 {paper.get('id', 'unknown')} 质量分数 {llm_score:.2f} 低于阈值 {min_quality_score}，已过滤")
            
            if not filtered_papers:
                logger.error("没有论文通过质量检查")
                return
            
            logger.info(f"质量检查完成，通过 {len(filtered_papers)} 篇论文")
            papers = filtered_papers
        else:
            logger.info("无需步骤2: 质量检查")
        
        # 3. 生成资讯内容
        logger.info("步骤3: 生成资讯内容")
        content_generator = ContentGenerator(api_key)
        news_content = []
        
        for paper in papers:
            paper_id = paper.get('id', 'unknown')
            
            logger.info(f"生成论文 {paper_id} 的资讯内容")
            news = await content_generator.generate_news(paper)
            
            news_content.append(news)
            
            # 添加延迟避免API限制
            await asyncio.sleep(1)
        
        # region
        # 4. 提取图片
        # logger.info("步骤4: 提取图片")
        # image_extractor = ImageExtractor(output_dir)
        # all_images = []
        
        # for item in filtered_papers:
        #     paper = item['paper']
        #     paper_id = paper.get('id', 'unknown')
            
        #     try:
        #         logger.info(f"提取论文 {paper_id} 的图片")
        #         images = await image_extractor.extract_images(paper)
                
        #         if images:
        #             all_images.extend(images)
        #             logger.info(f"论文 {paper_id} 图片提取成功，共 {len(images)} 张")
        #         else:
        #             logger.warning(f"论文 {paper_id} 未找到图片")
                    
        #     except Exception as e:
        #         logger.error(f"提取论文 {paper_id} 图片时出错: {str(e)}")
        #         continue
        
        # logger.info(f"图片提取完成，提取 {len(all_images)} 张图片")
        # endregion
        
        # 5. 格式化输出
        logger.info("步骤5: 格式化输出")
        output_formatter = OutputFormatter(timestamp, work_dir)
        output = output_formatter.format_output(news_content, query, papers)
        
        # 6. 保存文件
        logger.info("步骤6: 保存文件")
        saved_files = output_formatter.save_output(output, query)
        
        # 保存图片信息
        # if all_images:
        #     images_file = os.path.join(output_dir, timestamp, "images_info.json")
        #     os.makedirs(os.path.dirname(images_file), exist_ok=True)
            
        #     with open(images_file, 'w', encoding='utf-8') as f:
        #         json.dump(all_images, f, ensure_ascii=False, indent=2)
            
        #     saved_files.append(images_file)
        #     logger.info(f"图片信息已保存到: {images_file}")
        
        logger.info(f"文件保存完成，保存 {len(saved_files)} 个文件")
        
        # 输出结果
        print("\n" + "="*50)
        print("工作流执行结果:")
        print("="*50)
        print(f"查询: {query}")
        print(f"时间戳: {timestamp}")
        print(f"找到论文: {len(papers)}")
        # print(f"通过质量检查: {len(filtered_papers)}")
        print(f"生成资讯: {len(news_content)}")
        # print(f"提取图片: {len(all_images)}")
        print(f"保存文件: {len(saved_files)}")
        print("="*50)
        
        return True
        
    except Exception as e:
        logger.error(f"工作流执行出错: {str(e)}")
        import traceback
        logger.error(f"详细错误信息:\n{traceback.format_exc()}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='资讯生成:使用关键词批量搜索或使用arxiv id精准搜索')
    parser.add_argument('--query', '-q', type=str, default=None, help='搜索关键词，批量搜索') #"generation"
    parser.add_argument('--id_list', '-id', type=str, nargs='*', default=["2512.10950"], help='搜索id列表，精确查找') #["2512.04677","2512.03350"]
    parser.add_argument('--category', '-c', type=str, nargs='*', default=None, help='搜索类别') #["cs.AI","cs.CV"]
    parser.add_argument('--time-code', '-t', type=str, default="20251101", help='起始时间')
    parser.add_argument('--max-results', '-n', type=int, default=20, help='最大搜索结果数量')
    parser.add_argument('--start-index', '-i', type=int, default=0, help='起始索引')
    parser.add_argument('--min-score', '-s', type=float, default=6.5, help='最低质量分数阈值')
    parser.add_argument('--work-dir', '-d', type=str, default="./", help='工作路径')
    
    args = parser.parse_args()
    
    # 运行工作流
    success = asyncio.run(main_workflow(
        query=args.query,
        id_list=args.id_list,
        category=args.category,
        time_code=args.time_code,
        max_results=args.max_results,
        start_index=args.start_index,
        min_quality_score=args.min_score,
        work_dir=args.work_dir
    ))
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
