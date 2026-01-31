import sys
import os
import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime
from collections import defaultdict

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 从现有的config模块导入配置
from config.loader import load_config
from config.settings import Config

# 加载配置
config = load_config()
CATEGORIES = config.CATEGORIES
DATA_RAW_DIR = config.DATA_RAW_DIR
ARXIV_BASE_URL = config.ARXIV_BASE_URL
REQUEST_DELAY = getattr(config, 'REQUEST_DELAY', 1)
INCLUDE_REPLACEMENTS = getattr(config, 'INCLUDE_REPLACEMENTS', False)

def create_robust_session():
    """创建具有重试策略的稳健会话"""
    session = requests.Session()
    
    # 简单的重试适配器
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def fetch_papers_from_new_page(category_code):
    """从arXiv的new页面获取论文信息"""
    url = f"{ARXIV_BASE_URL}/list/{category_code}/new"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 找到主要内容区域，排除替换论文
        content = str(soup)
        if "Replacement submissions" in content and not INCLUDE_REPLACEMENTS:
            # 只获取第一个"Replacement submissions"之前的内容
            content = content.split("Replacement submissions")[0]
            soup = BeautifulSoup(content, 'html.parser')
        
        papers = []
        # 查找所有的dt标签（每个论文条目）
        dt_tags = soup.find_all('dt')
        
        for dt in dt_tags:
            paper_info = extract_paper_info(dt)
            if paper_info:
                papers.append(paper_info)
        
        return papers
        
    except Exception as e:
        print(f"获取 {category_code} 论文时出错: {e}")
        return []

def extract_paper_info(dt_tag):
    """从dt标签中提取论文信息"""
    try:
        # 提取论文ID
        abs_link = dt_tag.find('a', href=re.compile(r'^/abs/'))
        if not abs_link:
            return None
            
        paper_id = abs_link['href'].replace('/abs/', '')
        
        # 找到对应的dd标签（包含详细信息）
        dd_tag = dt_tag.find_next_sibling('dd')
        if not dd_tag:
            return None
        
        # 提取标题
        title_div = dd_tag.find('div', class_='list-title')
        title = title_div.text.replace('Title:', '').strip() if title_div else ""
        
        # 提取作者
        authors_div = dd_tag.find('div', class_='list-authors')
        authors = []
        if authors_div:
            author_links = authors_div.find_all('a')
            authors = [a.text.strip() for a in author_links]
        
        # 提取学科分类
        subjects_div = dd_tag.find('div', class_='list-subjects')
        categories = []
        if subjects_div:
            # 简单提取所有括号内的内容
            full_text = subjects_div.get_text()
            category_codes = re.findall(r'\((.*?)\)', full_text)
            # 过滤掉明显不是学科分类的内容
            for code in category_codes:
                if ' ' not in code and 2 <= len(code) <= 20:
                    categories.append(code)
        
        # 提取摘要
        abstract_p = dd_tag.find('p', class_='mathjax')
        abstract = abstract_p.text.strip() if abstract_p else ""
        
        return {
            'id': paper_id,
            'title': title,
            'authors': authors,
            'categories': categories,
            'abstract': abstract,
            'fetched_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"提取论文信息时出错: {e}")
        return None

def deduplicate_papers(all_papers_dict):
    """根据论文ID去重，保留第一次遇到的论文信息"""
    unique_papers = {}
    
    for category_name, papers in all_papers_dict.items():
        for paper in papers:
            paper_id = paper['id']
            if paper_id not in unique_papers:
                # 第一次遇到这篇论文，直接保存
                unique_papers[paper_id] = paper
    
    # 转换为列表并按ID排序
    return sorted(unique_papers.values(), key=lambda x: x['id'])

def main():
    """主函数"""
    print("开始从arXiv new页面获取论文信息...")
    print("=" * 50)
    
    # 确保数据目录存在
    os.makedirs(DATA_RAW_DIR, exist_ok=True)
    
    all_papers_by_category = {}
    
    for category_name, category_code in CATEGORIES.items():
        print(f"\n处理分类: {category_name} ({category_code})")
        
        # 获取论文信息
        papers = fetch_papers_from_new_page(category_code)
        
        if papers:
            print(f"✓ 获取到 {len(papers)} 篇论文")
            
            # 保存到分类文件
            filename = f"{category_name.lower()}_papers.json"
            filepath = os.path.join(DATA_RAW_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(papers, f, indent=2, ensure_ascii=False)
            
            print(f"✓ 论文信息已保存到: {filepath}")
            
            # 添加到分类集合
            all_papers_by_category[category_name] = papers
            
            # 添加延迟避免请求过快
            time.sleep(REQUEST_DELAY)
        else:
            print("✗ 未获取到论文信息")
    
    # 去重处理
    if all_papers_by_category:
        unique_papers = deduplicate_papers(all_papers_by_category)
        
        # 保存去重后的论文列表
        unique_file = os.path.join(DATA_RAW_DIR, "all_papers_unique.json")
        with open(unique_file, 'w', encoding='utf-8') as f:
            json.dump(unique_papers, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 去重后的论文列表已保存到: {unique_file}")
        print(f"✓ 总共获取到 {len(unique_papers)} 篇唯一论文")
    
    print("\n完成！")

if __name__ == "__main__":
    main()
