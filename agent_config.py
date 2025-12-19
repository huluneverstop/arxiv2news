#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arXiv资讯生成Agent配置文件
"""

import os
from typing import Dict, Any

class AgentConfig:
    """Agent配置类"""
    
    def __init__(self):
        # 千问API配置
        self.qwen_api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.qwen_model = "qwen-max"  # 使用千问Max模型
        self.qwen_max_tokens = 2000
        self.qwen_temperature = 0.7
        
        # 搜索配置
        self.default_query = "PU Learning"
        self.default_max_results = 10
        self.search_delay = 1.0  # 搜索间隔（秒）
        
        # 图片提取配置
        self.image_output_dir = "output/images"
        self.supported_image_formats = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']
        self.max_image_size = 10 * 1024 * 1024  # 10MB
        self.image_download_timeout = 30  # 30秒超时
        
        # 内容生成配置
        self.title_max_length = 20  # 标题最大长度
        self.content_max_length = 2000  # 内容最大长度
        self.generation_delay = 1.0  # 生成间隔（秒）
        
        # 输出配置
        self.output_dir = "output/news"
        self.output_formats = ['json', 'md']  # 输出格式
        self.include_images = True  # 是否包含图片
        
        # 日志配置
        self.log_level = "INFO"
        self.log_file = "agent.log"
        
        # 错误处理配置
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 5  # 重试间隔（秒）
        
        # 性能配置
        self.max_concurrent_requests = 5  # 最大并发请求数
        self.request_timeout = 60  # 请求超时时间（秒）
    
    def validate(self) -> bool:
        """验证配置"""
        errors = []
        
        if not self.qwen_api_key:
            errors.append("千问API密钥未设置")
        
        if self.default_max_results <= 0:
            errors.append("最大结果数必须大于0")
        
        if self.search_delay < 0:
            errors.append("搜索间隔不能为负数")
        
        if len(errors) > 0:
            print("❌ 配置验证失败:")
            for error in errors:
                print(f"   - {error}")
            return False
        
        return True
    
    def get_search_config(self) -> Dict[str, Any]:
        """获取搜索配置"""
        return {
            'query': self.default_query,
            'max_results': self.default_max_results,
            'delay': self.search_delay
        }
    
    def get_qwen_config(self) -> Dict[str, Any]:
        """获取千问配置"""
        return {
            'api_key': self.qwen_api_key,
            'model': self.qwen_model,
            'max_tokens': self.qwen_max_tokens,
            'temperature': self.qwen_temperature
        }
    
    def get_image_config(self) -> Dict[str, Any]:
        """获取图片配置"""
        return {
            'output_dir': self.image_output_dir,
            'supported_formats': self.supported_image_formats,
            'max_size': self.max_image_size,
            'timeout': self.image_download_timeout
        }
    
    def get_output_config(self) -> Dict[str, Any]:
        """获取输出配置"""
        return {
            'output_dir': self.output_dir,
            'formats': self.output_formats,
            'include_images': self.include_images
        }
    
    def print_config(self):
        """打印配置信息"""
        print("🔧 Agent配置信息:")
        print("=" * 50)
        print(f"千问模型: {self.qwen_model}")
        print(f"默认查询: {self.default_query}")
        print(f"最大结果数: {self.default_max_results}")
        print(f"图片输出目录: {self.image_output_dir}")
        print(f"资讯输出目录: {self.output_dir}")
        print(f"输出格式: {', '.join(self.output_formats)}")
        print(f"包含图片: {'是' if self.include_images else '否'}")
        print(f"日志级别: {self.log_level}")
        print("=" * 50)
    
    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                print(f"✅ 配置已更新: {key} = {value}")
            else:
                print(f"⚠️ 未知配置项: {key}")

# 全局配置实例
config = AgentConfig()

def get_config() -> AgentConfig:
    """获取配置实例"""
    return config

def update_config(**kwargs):
    """更新配置"""
    config.update_config(**kwargs)

if __name__ == "__main__":
    # 显示配置信息
    config.print_config()
    
    # 验证配置
    if config.validate():
        print("✅ 配置验证通过")
    else:
        print("❌ 配置验证失败")
    
    print("\n使用方法:")
    print("1. 设置环境变量: export DASHSCOPE_API_KEY='your_api_key'")
    print("2. 运行Agent: python run_agent.py")
    print("3. 或使用完整版: python arxiv_agent.py")
