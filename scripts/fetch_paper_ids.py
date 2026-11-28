import sys
import os
import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime, timezone
from urllib3.util import Retry

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 从现有的config模块导入配置
from config.loader import load_config

# 加载配置
config = load_config()
CATEGORIES = config.CATEGORIES
DATA_RAW_DIR = config.DATA_RAW_DIR
ARXIV_BASE_URL = config.ARXIV_BASE_URL
REQUEST_DELAY = getattr(config, 'REQUEST_DELAY', 1)
INCLUDE_REPLACEMENTS = getattr(config, 'INCLUDE_REPLACEMENTS', False)
LISTING_DATE = "Showing new listings for "
SECTION_HEADING = re.compile(
    r"^(New submissions|Cross submissions|Replacement submissions)"
    r" \(showing ([\d,]+) of ([\d,]+) entries\)$",
    re.IGNORECASE,
)

def create_robust_session():
    """创建具有重试策略的稳健会话"""
    session = requests.Session()
    
    retries = Retry(total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))
    adapter = requests.adapters.HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def parse_listing(content, category_code):
    """读取实际的公告日期，并验证纳入的列表没有缺项。"""
    soup = BeautifulSoup(content, 'html.parser')
    headings = soup.find_all(['h2', 'h3'])
    heading = next((tag.get_text(' ', strip=True) for tag in headings
                    if tag.get_text(' ', strip=True).startswith(LISTING_DATE)), None)
    if heading is None:
        raise ValueError(f"{category_code}: 无法识别 arXiv 公告日期")
    announced = datetime.strptime(heading.removeprefix(LISTING_DATE), '%A, %d %B %Y').date()

    expected = 0
    found = False
    include = False
    papers = []
    for tag in soup.find_all(['h2', 'h3', 'dt']):
        if tag.name != 'dt':
            section = SECTION_HEADING.fullmatch(tag.get_text(' ', strip=True))
            include = False
            if section:
                found = True
                name, visible, total = section.groups()
                include = INCLUDE_REPLACEMENTS or name.lower() != 'replacement submissions'
                if include:
                    total = int(total.replace(',', ''))
                    if int(visible.replace(',', '')) != total:
                        raise ValueError(f"{category_code}: arXiv 公告未显示完整列表")
                    expected += total
        elif include:
            paper = extract_paper_info(tag)
            if paper is not None:
                papers.append(paper)

    empty = re.search(r'\bTotal of 0 entries\b', soup.get_text(' ', strip=True))
    if (not found and not empty) or len(papers) != expected:
        raise ValueError(f"{category_code}: arXiv 公告条目解析不完整")
    return announced, papers


def fetch_papers_from_new_page(session, category_code):
    url = f"{ARXIV_BASE_URL}/list/{category_code}/new"
    response = session.get(url, params={'show': 2000}, timeout=30)
    response.raise_for_status()
    return parse_listing(response.content, category_code)

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
            'fetched_at': datetime.now(timezone.utc).isoformat()
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

def fetch_latest_issue():
    category_papers = {}
    dates = {}
    with create_robust_session() as session:
        for category_name, category_code in CATEGORIES.items():
            if category_papers:
                time.sleep(REQUEST_DELAY)
            dates[category_name], category_papers[category_name] = fetch_papers_from_new_page(
                session, category_code
            )
            print(f"{category_name}: {dates[category_name]}，{len(category_papers[category_name])} 篇论文")

    if len(set(dates.values())) != 1:
        raise ValueError(f"各学科未返回同一 arXiv 公告日期: {dates}")
    return next(iter(dates.values())), category_papers


def main():
    try:
        source_date, categories = fetch_latest_issue()
        os.makedirs(DATA_RAW_DIR, exist_ok=True)
        for name, papers in categories.items():
            with open(os.path.join(DATA_RAW_DIR, f"{name.lower()}_papers.json"), 'w', encoding='utf-8') as f:
                json.dump(papers, f, indent=2, ensure_ascii=False)

        papers = deduplicate_papers(categories)
        with open(os.path.join(DATA_RAW_DIR, 'all_papers_unique.json'), 'w', encoding='utf-8') as f:
            json.dump(papers, f, indent=2, ensure_ascii=False)
        print(f"{source_date}: {len(papers)} 篇唯一论文")
        return 0
    except (OSError, ValueError, requests.RequestException) as exc:
        print(f"抓取 arXiv 公告失败: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
