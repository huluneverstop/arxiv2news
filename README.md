# arxiv2news

## 环境配置

查看 *requirements.txt*

## 如何使用

### 1. 设置apikey

本项目调用的是QWen系列模型，从平台上申请apikey后在 *.env* 文件中配置

### 2. 主入口

*run_agent.py* 为项目主入口，有两种使用方式：关键词搜索生成/精确查找生成。

关键词搜索生成：通过关键词模糊匹配文章并生成对应的资讯内容

精确查找生成：通过明确的arxiv id搜索文章并生成对应的资讯内容

### 3. 参数说明

- query：搜索关键词，用于匹配文章，如"world model"、"generation"

- id_list：arxiv id，用于精准搜索，以列表的形式输入可以批量搜索，如["2512.04677","2512.03350"]

- category：限定搜索文章的类别，用于辅助关键词搜索，如["cs.AI","cs.CV"]，类别对照表可查看 Classification Mapping Table

- time-code：限定文章搜索的起始时间，“20251101”表示搜索2025年11月1日之后的文章

- max-results：限定搜索结果数量，同一时间搜索过多文章会被arxiv限制

- start-index：限定搜索结果的起始索引，“10”意味着从搜索结果的第11篇开始输出，用于文章搜索结果的前10篇都不符合要求时

- min-score：设定输出文章的质量评分下限，10分制，默认为6.5，具体评分方式见 *paper_quality_scorer.py*

- work-dir：工作路径，默认为当前目录

### 4. 结果输出

所生成资讯输出在 */output* 中