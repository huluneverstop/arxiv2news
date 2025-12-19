#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
图片提取模块
从arXiv论文中提取图片和识别图注
支持从摘要、网页和PDF中提取图片
"""

import os
import re
import requests
import asyncio
import httpx
import random
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import logging
import sys
from PIL import Image
import io
import base64
import hashlib
from datetime import datetime
import tarfile
import tempfile
import fitz  # PyMuPDF
import urllib.parse
from tqdm import tqdm
# from hero_image_selector import HeroImageSelector

# 配置日志
# def setup_logging():
#     """配置日志系统"""
#     # 创建logs目录
#     log_dir = os.path.join(os.path.dirname(__file__), 'logs')
#     os.makedirs(log_dir, exist_ok=True)
    
#     # 配置日志格式
#     log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
#     # 创建logger
#     logger = logging.getLogger(__name__)
#     logger.setLevel(logging.INFO)
    
#     # 避免重复添加handler
#     if not logger.handlers:
#         # 控制台处理器
#         console_handler = logging.StreamHandler(sys.stdout)
#         console_handler.setLevel(logging.INFO)
#         console_formatter = logging.Formatter(log_format)
#         console_handler.setFormatter(console_formatter)
#         logger.addHandler(console_handler)
        
#         # 文件处理器
#         log_file = os.path.join(log_dir, 'image_extractor.log')
#         file_handler = logging.FileHandler(log_file, encoding='utf-8')
#         file_handler.setLevel(logging.INFO)
#         file_formatter = logging.Formatter(log_format)
#         file_handler.setFormatter(file_formatter)
#         logger.addHandler(file_handler)
    
#     return logger

# 初始化日志
logger = logging.getLogger(__name__)

class ImageExtractor:
    """图片提取器"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        self.supported_formats = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg'}
        
        # 创建输出目录
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        self.image_collector = [] # 图片收集器收集到的图片list
        # self.url_collector = {}
        
        # 请求头配置
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 超时配置
        self.timeout = 60.0  # httpx使用float类型
        self.max_retries = 3
        self.retry_delay = 2
        
        # httpx客户端配置
        self.client_config = {
            'timeout': self.timeout,
            'follow_redirects': True,
            'verify': True,  # SSL验证
            'http2': False,   # 禁用HTTP/2避免兼容性问题
        }
        
    async def extract_images(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从论文中提取图片和表格
        
        Args:
            paper: 论文信息字典
            
        Returns:
            图片信息列表
        """
        try:
            paper_id = paper.get('id', '')
            # title = paper.get('title', '')
            
            logger.info(f"开始提取论文图片: {paper_id}")
            
            all_images = []
            
            # 策略1: 优先从HTML版本获取图片
            logger.info("策略1: 尝试从HTML版本获取图片")
            html_images = await self._extract_from_html(paper)
            if html_images:
                all_images.extend(html_images)
                logger.info(f"从HTML获取到 {len(html_images)} 张图片")
                
                # # 检查HTML图片下载数量
                # if self.found_images_count == self.downloaded_images_count:
                #     logger.info("HTML图片全部下载成功，跳过其他提取方法")
                # else:
                #     logger.warning(f"HTML图片部分下载失败 ({self.downloaded_images_count}/{self.found_images_count})，尝试从源文件包补充")
                #     # 继续尝试源文件包方法
                #     # source_images = await self._extract_from_source(paper)
                #     # if source_images:
                #     #     all_images.extend(source_images)
                #     #     logger.info(f"从源文件包获取到 {len(source_images)} 张图片")
                #     source_package = await self.download_source_package(paper, self.output_dir)
                #     if source_package:
                #         logger.info(f"已下载源文件包")
                #     else:
                #         logger.info("源文件包下载失败")
                    
                    
            else:
                # logger.info("HTML方法未获取到图片，尝试源文件包方法")
                # # # HTML方法失败，尝试源文件包
                # # source_images = await self._extract_from_source(paper)
                # # if source_images:
                # #     all_images.extend(source_images)
                # #     logger.info(f"从源文件包获取到 {len(source_images)} 张图片")
                # # else:
                # #     logger.info("源文件包方法也失败，考虑PDF方法（暂时注释）")
                # #     # PDF方法暂时注释
                # #     # pdf_images = await self._extract_from_pdf(paper)
                # #     # if pdf_images:
                # #     #     all_images.extend(pdf_images)
                # #     #     logger.info(f"从PDF获取到 {len(pdf_images)} 张图片/表格")

                # source_package = await self.download_source_package(paper, self.output_dir)
                # if source_package:
                #     logger.info(f"已下载源文件包")
                # else:
                #     logger.info("源文件包下载失败")

                logger.info("跳过")
            
            # 去重并添加元数据
            unique_images = self._deduplicate_images(all_images)
            
            # 为每张图片添加论文信息
            for img in unique_images:
                img['paper_id'] = paper_id
                # img['paper_title'] = title
                img['img_name'] = img.get('filename', '')
                img['extraction_time'] = datetime.now().isoformat()
            
            # 选择首图
            # logger.info("开始选择首图...")
            # hero_image = await self.hero_image_selector.select_hero_image(paper, unique_images)
            # if hero_image:
            #     # 标记为首图
            #     hero_image['is_hero_image'] = True
            #     logger.info(f"已选择首图: {hero_image.get('filename', '')}")
            # else:
            #     logger.warning("未找到合适的首图")
            
            logger.info(f"论文 {paper_id} 图片提取完成，共 {len(unique_images)} 张")
            return unique_images
            
        except Exception as e:
            logger.error(f"提取论文图片时出错: {str(e)}")
            return []
    

    def is_absolute_url(self, url):
        """判断是否为完整 URL（绝对 URL）"""
        parsed = urlparse(url)
        # 完整 URL 必须有 scheme（如 https）和 netloc（如 arxiv.org）
        return bool(parsed.scheme) and bool(parsed.netloc)
        
    def _collect_and_categorize_urls(self, buffer: str, base_url: str, seen_urls: set, url_collector: Dict[str, List], image_collector: List ,paper_id: str) -> None:
        """
        从HTML buffer中收集和分类URL
        
        Args:
            buffer: HTML内容buffer
            base_url: 基础URL
            seen_urls: 已见过的URL集合
            url_collector: URL收集器字典
            paper_id: 论文ID
        """
        # 图片链接正则表达式
        img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
        # 链接正则表达式
        link_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
        
        # 收集图片
        img_matches = img_pattern.findall(buffer)
        for img_url in img_matches:
            if img_url not in seen_urls and self._is_valid_image_url(img_url):
                seen_urls.add(img_url)
                absolute_url = urljoin(base_url.rstrip('/')+'/', img_url)
                image_collector.append({
                    'url': absolute_url,
                    'name': img_url.split('.')[-2],
                    'source': 'html'
                })
        
        # 收集链接
        link_matches = link_pattern.findall(buffer)
        for link_url in link_matches:
            # 过滤掉包含论文ID的URL
            if paper_id in link_url or 'LaTeX' in link_url or not self.is_absolute_url(link_url) or 'arxiv' in link_url:
                continue
            if link_url not in seen_urls:
                seen_urls.add(link_url)
                
                # 分类链接
                url_type = self._categorize_url(link_url)
                url_collector[url_type].update({
                    'url': link_url,
                    'check': False    
                })
    
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
        
        # # 项目链接（包含项目相关关键词）
        # project_keywords = [
        #     'project', 'demo', 'paper', 'page', 'website', 'site',
        #     'app', 'tool', 'software', 'code', 'repository', 'repo'
        # ]
        
        # for keyword in project_keywords:
        #     if keyword in url_lower:
        #         return 'project'
        
        # # 其他链接
        # return 'other'
    
    async def _process_additional_links(self, url_collector: Dict[str, List], image_collector: List, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        处理其他类型链接，获取配图候选
        
        Args:
            url_collector: URL收集器
            paper: 论文信息
            
        Returns:
            额外的图片列表
        """
        
        # 初始化链接状态
        # github_processed = False
        # project_processed = False
        
        # # 记录初始链接数量
        # initial_github_count = len(url_collector['github'])
        # initial_project_count = len(url_collector['project'])
        
        # 当url_collector状态为false时不断循环处理
        while not url_collector['state']:
            # 处理GitHub链接
            waiting_url_types = ['github', 'project']   
            for url_type in waiting_url_types:
                if url_collector[url_type].get('url', None) and not url_collector[url_type].get('check', False):
                    logger.info(f"处理{url_type}链接 {url_collector[url_type]['url']}")
                    try:
                        image_collector, url_collector = await self._process_and_update_collector(image_collector, url_collector, paper, url_type)
                    except Exception as e:
                        url_collector[url_type]['check'] = True
                        logger.error(f"{url_type}链接处理失败: {str(e)}")
                        # url_collector[url_type].update({'url':None, 'check':True})
                        
            if all(url_collector[url_type]['check'] for url_type in waiting_url_types):
                url_collector['state'] = True
                logger.info("所有链接处理完成")
                
           
            # 短暂等待避免过度占用CPU
            await asyncio.sleep(0.1)

        paper['links'].update({'github':url_collector['github']['url'], 'project':url_collector['project']['url']})
        return image_collector 

    async def _process_and_update_collector(self, image_collector: List, url_collector:Dict[str,List], paper: Dict[str, Any], url_type: str):
        """处理并更新图像收集器和url收集器"""
    
        try:
            current_url = url_collector[url_type]
            target_type = 'project' if url_type == 'github' else 'github'
            
            # 从当前url提取图片
            response = await self._make_request_with_retry(current_url['url'])
            if response:
                # content = response.text
                

                current_images = await self._get_images_from_url(current_url, url_type, paper)
            
                if current_images:
                    image_collector.extend(current_images)

            current_url['check'] = True
            
            # 检查当前页面中是否有其他关注链接
            if not url_collector[target_type]:
                target_url = await self._get_interested_links_from_url(current_url, paper, target_type)
                # project_links = await self._extract_project_links_from_github_links(url, paper)
                if target_url:
                    url_collector[target_type].update(target_url)
                    logger.info(f"从{url_type}页面更新{target_type}链接: {target_url['url']}")
                else:
                    url_collector[target_type].update({'url':None, 'check':True})
            
        except Exception as e:
            logger.warning(f"处理{url_type}链接失败: {str(e)}")
            return image_collector, url_collector
        
        return image_collector, url_collector

    async def _get_images_from_url(self, current_url: str ,url_type:str, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从当前url提取图片"""
        try:
            response = await self._make_request_with_retry(current_url['url'])
            if not response:
                return []
            
            content = response.text
            
            # 提取图片
            img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
            img_matches = img_pattern.findall(content)

            img_filter = self._filter_images(img_matches, current_url['url'], url_type)

            return img_filter

        except Exception as e:
            logger.warning(f"从{current_url}页面提取图片失败: {str(e)}")
            return []

    def _filter_images(self, img_matches: List[str], base_url: str, source: str) -> List[Dict[str, Any]]:
        """过滤非功能图片"""
        
        filtered_images = []
        
        for img_url in img_matches:
            if not self._is_valid_image_url(img_url):
                continue
                
            # 过滤掉logo、图标等明显不需要的图片
            img_lower = img_url.lower()
            img_name = img_url.split('/')[-1].lower()
            
            # 智能过滤条件
            if self._should_skip_image(img_url, img_name, img_lower):
                continue
            
            # 构建绝对URL
            absolute_url = urljoin(base_url.rstrip('/')+'/', img_url)
            
            # 提取图片名称（去掉扩展名）
            img_name_clean = img_name.rsplit('.', 1)[0] if '.' in img_name else img_name
            
            filtered_images.append({
                'url': absolute_url,
                'name': img_name_clean,
                'source': source
            })
        
        return filtered_images
    
    def _should_skip_image(self, img_url: str, img_name: str, img_lower: str) -> bool:
        """判断是否应该跳过这张图片"""
        
        # 1. 关键词过滤 - 基于文件名和URL
        skip_keywords = [
            # UI元素
            'logo', 'icon', 'favicon', 'button', 'badge', 'shield', 'emoji',
            # 状态指示
            'status', 'travis', 'coveralls', 'codecov', 'pypi', 'npm', 'build',
            # 操作按钮
            'download', 'install', 'get', 'buy', 'shop', 'cart', 'subscribe',
            # 社交媒体
            'social', 'facebook', 'twitter', 'linkedin', 'youtube', 'instagram',
            # 代码平台
            'github', 'gitlab', 'bitbucket', 'stackoverflow', 'reddit',
            # 导航元素
            'arrow', 'chevron', 'caret', 'plus', 'minus', 'close', 'next', 'prev',
            # 界面组件
            'menu', 'hamburger', 'nav', 'breadcrumb', 'pagination', 'tabs',
            # 用户相关
            'avatar', 'profile', 'user', 'team', 'member', 'admin',
            # 其他功能
            'sponsor', 'donate', 'support', 'help', 'faq', 
            # 广告相关
            'ad', 'advertisement', 'banner', 'promo', 'sponsored',
            # 工具图标
            'tool', 'gear', 'settings', 'config', 'preferences', 'options',
            # 机构相关
             'university', 'college', 'institute', 'institut', 'center', 'centre', 'lab', 'laboratory',
             'foundation', 'funded', 'stiftung', 'gmbh', 'inc', 'ltd',
             'mpi', 'mpii', 'eu', 'europ', 'germany','corporation', 'company', 'team'
        ]
        
        # 检查文件名是否包含过滤关键词
        for keyword in skip_keywords:
            if keyword in img_name or keyword in img_lower:
                return True
        
        # 2. 尺寸过滤 - 过滤掉小尺寸的图片（通常是图标）
        if 'size=' in img_url:
            size_match = re.search(r'size=(\d+)', img_url)
            if size_match and int(size_match.group(1)) < 150:  # 阈值150px
                return True
        
        # 3. 路径过滤 - 过滤掉明显是图标的文件路径
        icon_paths = [
            '/icons/', '/images/icons/', '/assets/icons/', '/static/icons/',
            '/img/icons/', '/css/icons/', '/js/icons/', '/fonts/',
            '/ui/', '/components/', '/elements/', '/widgets/'
        ]
        
        for icon_path in icon_paths:
            if icon_path in img_lower:
                return True
        
        # 4. 文件扩展名过滤 - 过滤掉一些特殊格式
        skip_extensions = ['.ico', '.svg']  # 通常是小图标
        if any(img_lower.endswith(ext) for ext in skip_extensions):
            return True
        
        # 5. 智能路径分析 - 过滤掉系统级图标
        system_paths = [
            '/wp-content/', '/wp-includes/', '/wp-admin/',  # WordPress
            '/themes/', '/plugins/', '/uploads/',           # CMS系统
            '/admin/', '/backend/', '/dashboard/'           # 管理后台
        ]
        
        for sys_path in system_paths:
            if sys_path in img_lower:
                return True
        
        return False
            
    async def _get_interested_links_from_url(self, current_url: str, paper: Dict[str, Any], target_url_type: str) -> List[Dict[str, Any]]:
        """从当前url提取感兴趣的链接"""
        try:
            response = await self._make_request_with_retry(current_url['url'])
            if not response:
                return []
            
            content = response.text
            
            # 提取感兴趣的链接
            interested_links = []
            link_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
            link_matches = link_pattern.findall(content)
            
            for link_url in link_matches:
                if paper['id'] in link_url or 'LaTeX' in link_url or not self.is_absolute_url(link_url) or 'arxiv' in link_url:
                    continue    
                if self._categorize_url(link_url) == target_url_type:
                    
                    absolute_url = urljoin(current_url['url'].rstrip('/')+'/', link_url)
                    interested_links.append(absolute_url)
                    
                    return {'url':absolute_url, 'check':False}
            
            return {'url':None, 'check':True}
            
        except Exception as e:
            logger.warning(f"从{current_url}页面提取感兴趣的链接失败: {str(e)}")
            return []
                   

    async def _make_request_with_retry(self, url: str, method: str = 'GET', **kwargs) -> Optional[httpx.Response]:
        """带重试机制的请求"""
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(**self.client_config) as client:
                    response = await client.request(method, url, headers=self.headers, **kwargs)
                    
                    if response.status_code == 200:
                        return response
                    elif response.status_code in [403, 429, 500, 502, 503, 504]:
                        # 服务器错误，等待后重试
                        wait_time = self.retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"请求失败 {url}, 状态码: {response.status_code}, 等待 {wait_time:.1f}秒后重试")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"请求失败 {url}, 状态码: {response.status_code}")
                        return None
                        
            except httpx.TimeoutException:
                logger.warning(f"请求超时 {url}, 尝试 {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
            except httpx.RequestError as e:
                logger.error(f"请求异常 {url}: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
            except Exception as e:
                logger.error(f"未知异常 {url}: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
        
        return None

    async def _extract_from_html(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从HTML版本提取图片 - 使用httpx"""
        try:
            
            html_url = paper.get('links', {}).get('html', '')
            # html_url = paper['links']['html']
            
            logger.info(f"开始从HTML提取图片: {html_url}")
            
            # 带重试机制的请求
            response = await self._make_request_with_retry(html_url)
            if not response:
                logger.warning(f"无法获取HTML内容: {html_url}")
                return []
            
            # 尝试流式读取
            try:
                # URL收集器
                url_collector = {   
                    'github': {},      # GitHub链接
                    'project': {},     # 项目链接
                    'state': False     # 状态标识
                }
                buffer = ""
                
                # # 编译正则表达式模式
                # img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
                # link_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
                
                seen_urls = set()

                # 获取内容长度用于进度条
                content_length = response.headers.get('content-length')
                total_size = int(content_length) if content_length else None
                
                logger.info(f"开始流式解析HTML，内容大小: {total_size/1024:.1f} KB" if total_size else "开始流式解析HTML")
                
                # 创建进度条
                with tqdm(
                    desc="解析HTML内容",
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    disable=total_size is None
                ) as pbar:
                    if total_size:
                        # 使用字节流可视化html读取进度
                        async for chunk in response.aiter_bytes():
                            chunk_size = len(chunk)
                            buffer += chunk.decode('utf-8', errors='ignore')
                            pbar.update(chunk_size)
                            
                            # 收集和分类URL
                            self._collect_and_categorize_urls(
                                buffer, html_url, seen_urls, url_collector, self.image_collector, paper.get('id', '')
                            )
                            
                            # 控制buffer大小
                            if len(buffer) > 100000:  # 100KB
                                buffer = buffer[-50000:]  # 保留后半部分
                    else:
                        # 使用文本流但显示处理进度
                        processed_size = 0
                        async for chunk in response.aiter_text():
                            chunk_size = len(chunk.encode('utf-8'))
                            buffer += chunk
                            processed_size += chunk_size
                            pbar.update(chunk_size)
                            
                            # 收集和分类URL
                            self._collect_and_categorize_urls(
                                buffer, html_url, seen_urls, url_collector, self.image_collector, paper.get('id', '')
                            )
                            
                            # 控制buffer大小
                            if len(buffer) > 100000:  # 100KB 
                                buffer = buffer[-50000:]  # 保留后半部分
                
                # 统计收集到的URL
                total_images = len(self.image_collector)
                
                logger.info(f"HTML流式解析完成，收集到:")
                logger.info(f"  - 图片链接: {total_images} 个")
                logger.info(f"  - GitHub链接: {url_collector['github']}")
                logger.info(f"  - 项目链接: {url_collector['project']}")
                
                # 更新统计信息
                self.found_images_count = total_images
                
                # 处理其他类型链接，获取配图候选
                logger.info("开始处理其他类型链接...")
                self.image_collector = await self._process_additional_links(url_collector, self.image_collector, paper)

                # 并发下载图片
                downloaded_images = []
                if self.image_collector:
                    logger.info("开始并发下载图片...")
                    downloaded_images = await self._get_images_concurrently(self.image_collector, paper['id'])
                    self.downloaded_images_count = len(downloaded_images)
                    logger.info(f"图片下载完成，共 {len(downloaded_images)} 张")
                
        
                
                return downloaded_images
                
            except Exception as e:
                logger.warning(f"流式读取失败，尝试完整读取: {str(e)}")
                # 回退到完整读取
                try:
                    html_content = response.text
                    return await self._parse_html_content(html_content, html_url, paper)
                except Exception as e2:
                    logger.error(f"完整读取也失败: {str(e2)}")
                    return []
                    
        except Exception as e:
            logger.error(f"从HTML提取图片失败: {str(e)}")
            return []
    
    async def _extract_from_source(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从源文件包提取图片 - 使用httpx"""
        try:
            source_url = f"https://arxiv.org/e-print/{paper['id']}"
            logger.info(f"开始下载源文件包: {source_url}")
            
            # 带重试机制的请求
            response = await self._make_request_with_retry(source_url)
            if not response:
                logger.warning(f"无法下载源文件包: {source_url}")
                return []
            
            # 检查文件大小
            content_length = response.headers.get('content-length', None)
            if content_length:
                file_size_mb = int(content_length) / (1024 * 1024)
                logger.info(f"源文件包大小: {file_size_mb:.1f} MB")
                
                if file_size_mb > 100:  # 大于100MB
                    logger.warning(f"源文件包过大 ({file_size_mb:.1f} MB)，跳过下载")
                    return []
            else:
                logger.warning("无法获取文件大小，将尝试下载（无大小限制）")
            
            # 下载到临时文件
            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as temp_file:
                temp_file_path = temp_file.name
                
                try:
                    # 分块下载
                    downloaded_size = 0
                    
                    # 创建下载进度条
                    with tqdm(
                        desc="下载源文件包",
                        total=file_size_mb * 1024 * 1024 if content_length else None,
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        disable=content_length is None
                    ) as pbar:
                        async for chunk in response.aiter_bytes():
                            temp_file.write(chunk)
                            chunk_size = len(chunk)
                            downloaded_size += chunk_size
                            pbar.update(chunk_size)
                    
                    temp_file.flush()
                    logger.info(f"源文件包下载完成: {downloaded_size / (1024 * 1024):.1f} MB")
                    
                    # 提取图片
                    images = self._get_images_from_targz(temp_file_path, paper.get('id', ''))
                    return images
                    
                finally:
                    # 清理临时文件
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"从源文件包提取图片失败: {str(e)}")
            return []

    async def download_source_package(self, paper: Dict[str, Any], target_path: str) -> bool:
        """直接下载源文件包到指定路径 - 使用httpx"""
        try:
            source_url = f"https://arxiv.org/e-print/{paper['id']}"
            target_path = os.path.join(self.output_dir, f"{paper['id']}/source_package.tar.gz")
            logger.info(f"开始下载源文件包到: {target_path}")
            
            
            # 带重试机制的请求
            response = await self._make_request_with_retry(source_url)
            if not response:
                logger.warning(f"无法下载源文件包: {source_url}")
                return False
            
            # 检查文件大小
            content_length = response.headers.get('content-length', None)
            if content_length:
                file_size_mb = int(content_length) / (1024 * 1024)
                logger.info(f"源文件包大小: {file_size_mb:.1f} MB")
                
                if file_size_mb > 200:  # 大于100MB
                    logger.warning(f"源文件包过大 ({file_size_mb:.1f} MB)，跳过下载")
                    return False
            else:
                logger.warning("无法获取文件大小，将尝试下载（无大小限制）")
            
            # 确保目标目录存在
            target_dir = os.path.dirname(target_path)
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
                logger.info(f"创建目标目录: {target_dir}")
            
            # 下载到目标路径
            with open(target_path, 'wb') as target_file:
                downloaded_size = 0
                
                # 创建下载进度条
                with tqdm(
                    desc="下载源文件包",
                    total=file_size_mb * 1024 * 1024 if content_length else None,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    disable=content_length is None
                ) as pbar:
                    async for chunk in response.aiter_bytes():
                        target_file.write(chunk)
                        chunk_size = len(chunk)
                        downloaded_size += chunk_size
                        pbar.update(chunk_size)
                
                target_file.flush()
                logger.info(f"源文件包下载完成: {downloaded_size / (1024 * 1024):.1f} MB -> {target_path}")
                return True
                
        except Exception as e:
            logger.error(f"下载源文件包失败: {str(e)}")
            # 如果下载失败，尝试删除可能部分下载的文件
            try:
                if os.path.exists(target_path):
                    os.unlink(target_path)
                    logger.info(f"清理部分下载的文件: {target_path}")
            except:
                pass
            return False
    
    async def _extract_from_pdf(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从PDF提取图片和表格 - 使用httpx""" ##  提取图片和表格有问题
    
    async def _download_image_with_retry(self, url: str, paper_id: str, source: str) -> Optional[Dict[str, Any]]:
        """带重试机制的图片下载 - 使用httpx"""
        for attempt in range(self.max_retries):
            try:
                response = await self._make_request_with_retry(url)
                if not response:
                    continue
                
                # 获取图片数据
                image_data = response.content
                
                # 检查是否为有效图片
                if not self._is_valid_image_data(image_data):
                    logger.warning(f"无效图片数据: {url}")
                    continue
                
                # 保存图片
                original_filename = os.path.basename(url)
                
                filepath = os.path.join(self.output_dir, f"{paper_id}/{source}_{original_filename}")
                filedir = os.path.dirname(filepath)
                if filedir and not os.path.exists(filedir):
                    os.makedirs(filedir, exist_ok=True)
                    logger.info(f"创建目标目录: {filedir}")
                
                # 显示图片下载进度
                image_size = len(image_data)
                with tqdm(
                    desc=f"下载图片 {os.path.basename(url)}",
                    total=image_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    leave=False  # 下载完成后不保留进度条
                ) as pbar:
                    with open(filepath, 'wb') as f:
                        # 分块写入以显示进度
                        chunk_size = 8192  # 8KB chunks
                        for i in range(0, image_size, chunk_size):
                            chunk = image_data[i:i + chunk_size]
                            f.write(chunk)
                            pbar.update(len(chunk))
                
                # 获取图片信息
                try:
                    with Image.open(filepath) as img:
                        width, height = img.size
                        format = img.format
                except:
                    width, height = 0, 0
                    format = 'unknown'

                logger.warning(f"下载图片成功 {url}")
                logger.warning(f"图片信息: {width}x{height}, 格式: {format}, 大小: {len(image_data)} bytes")
                
                return {
                    'filename': original_filename,
                    'filepath': filepath,
                    'source': source,
                    'width': width,
                    'height': height,
                    'format': format,
                    'size_bytes': len(image_data),
                    'original_path': url
                }
                
            except Exception as e:
                logger.warning(f"下载图片失败 {url}, 尝试 {attempt + 1}/{self.max_retries}: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
        
        return None

    async def _parse_html_content(self, html_content: str, base_url: str, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析HTML内容"""
        images = []
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        img_matches = re.findall(img_pattern, html_content, re.IGNORECASE)
        
        for img_url in img_matches:
            if self._is_valid_image_url(img_url):
                # 过滤掉logo、图标等明显不需要的图片
                img_lower = img_url.lower()
                img_name = img_url.split('/')[-1].lower()
                
                # 过滤条件：包含logo、icon、favicon、button、badge等关键词的图片
                skip_keywords = [
                    'logo', 'icon', 'favicon', 'button', 'badge', 'shield', 
                    'status', 'travis', 'coveralls', 'codecov', 'pypi', 'npm',
                    'download', 'install', 'get', 'buy', 'shop', 'cart',
                    'social', 'facebook', 'twitter', 'linkedin', 'youtube',
                    'github', 'gitlab', 'bitbucket', 'stackoverflow',
                    'arrow', 'chevron', 'caret', 'plus', 'minus', 'close',
                    'menu', 'hamburger', 'nav', 'breadcrumb', 'pagination',
                    'avatar', 'profile', 'user', 'team', 'member',
                    'sponsor', 'donate', 'support', 'help', 'faq'
                ]
                
                # 检查文件名是否包含过滤关键词
                should_skip = False
                for keyword in skip_keywords:
                    if keyword in img_name or keyword in img_lower:
                        should_skip = True
                        break
                
                # 过滤掉小尺寸的图片（通常是图标）
                if not should_skip and 'size=' in img_url:
                    size_match = re.search(r'size=(\d+)', img_url)
                    if size_match and int(size_match.group(1)) < 100:
                        should_skip = True
                
                # 过滤掉明显是图标的文件路径
                icon_paths = ['/icons/', '/images/icons/', '/assets/icons/', '/static/icons/']
                for icon_path in icon_paths:
                    if icon_path in img_lower:
                        should_skip = True
                        break
                
                if not should_skip:
                    absolute_url = urljoin(base_url.rstrip('/')+'/', img_url)
                    
                    downloaded = await self._download_image_with_retry(absolute_url, paper['id'], 'html')
                    images.append(downloaded)
        
        return images
    
    def _is_valid_image_url(self, url: str) -> bool:
        """检查是否为有效的图片URL"""
        if not url:
            return False
        
        # 检查文件扩展名
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        return any(path.endswith(ext) for ext in self.supported_formats)
    
    def _is_valid_image_data(self, data: bytes) -> bool:
        """检查是否为有效的图片数据"""
        if not data or len(data) < 100:  # 最小文件大小
            return False
        
        try:
            # 尝试打开图片
            with Image.open(io.BytesIO(data)) as img:
                return True
        except:
            return False
    
    def _deduplicate_images(self, images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """使用文件名作为标识去重图片""" 
        # 这里如果不使用文件名作为去重标识的话暂时也没有更好的选择
        # 因为从html中解析出来的图片命名和原文件包里的命名往往不一致
        seen = set()
        unique_images = []
        
        for img in images:
            # 使用文件名作为唯一标识
            filepath = img.get('filename', '')
            if filepath and filepath not in seen:
                seen.add(filepath)
                unique_images.append(img)
        
        return unique_images
    
    # def get_extraction_stats(self) -> Dict[str, Any]:
    #     """获取提取统计信息"""
    #     try:
    #         total_files = len([f for f in os.listdir(self.output_dir) if os.path.isfile(os.path.join(self.output_dir, f))])
    #         total_size = sum(os.path.getsize(os.path.join(self.output_dir, f)) for f in os.listdir(self.output_dir) if os.path.isfile(os.path.join(self.output_dir, f)))
            
    #         return {
    #             'total_files': total_files,
    #             'total_size_bytes': total_size,
    #             'total_size_mb': round(total_size / (1024 * 1024), 2),
    #             'output_directory': self.output_dir
    #         }
    #     except Exception as e:
    #         logger.error(f"获取统计信息失败: {str(e)}")
    #         return {}

    async def _get_images_concurrently(self, image_info_list: List[Dict[str, Any]], paper_id: str, max_concurrent: int = 5) -> List[Dict[str, Any]]:
        """并发下载多张图片"""
        if not image_info_list:
            return []
        
        logger.info(f"开始并发下载 {len(image_info_list)} 张图片，最大并发数: {max_concurrent}")
        
        # 创建信号量限制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _get_single_image(img_info):
            async with semaphore:
                try:
                    url = img_info['url']
                    source = img_info['source']
                    
                    downloaded = await self._download_image_with_retry(url, paper_id, source)
                    return downloaded
                except Exception as e:
                    logger.warning(f"并发下载图片失败 {img_info.get('url', 'unknown')}: {str(e)}")
                    return None
        
        # 创建所有下载任务
        tasks = [_get_single_image(img_info) for img_info in image_info_list]
        
        # 并发执行，显示进度条
        downloaded_images = []
        with tqdm(
            desc="并发下载图片",
            total=len(tasks),
            unit="张"
        ) as pbar:
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result:
                    downloaded_images.append(result)
                pbar.update(1)
        
        logger.info(f"并发下载完成，成功下载 {len(downloaded_images)} 张图片")
        return downloaded_images