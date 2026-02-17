#!/usr/bin/env python3
"""
HTML生成脚本 - bluearXiv-ai 项目
基于 JSON 数据生成 HTML 格式的论文报告
"""

import os
import json
import re
import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple

# 导入项目配置
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 从config.settings导入Config类
from config.settings import Config

# 创建配置实例
config = Config()

# 从配置实例获取路径和分类
DATA_RAW_DIR = Path(config.DATA_RAW_DIR)
TEX_DIR = Path(config.DATA_RAW_DIR) / "daily_feedback_tex"  # 注意：settings.py中没有TEX_DIR，这里按原计划定义
CATEGORIES = config.CATEGORIES  # 这是属性，返回字典

# 尝试从config.loader导入read_list_file
try:
    from config.loader import read_list_file
except ImportError:
    # 如果config.loader中没有read_list_file，则自己定义
    def read_list_file(filename: str) -> List[str]:
        """读取列表文件，每行一个条目"""
        filepath = Path(__file__).parent.parent / filename
        if not filepath.exists():
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        result = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                result.append(line)
        
        return result



def escape_html(text: str) -> str:
    """转义HTML特殊字符"""
    if not text:
        return ""
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))


def format_authors(authors_list: List[str]) -> str:
    """格式化作者列表"""
    if not authors_list:
        return ""
    if len(authors_list) <= 3:
        return ", ".join(authors_list)
    else:
        return authors_list[0] + " et al."
        
def load_template(template_name: str) -> str:
    """读取HTML模板文件"""
    template_path = Path(__file__).parent.parent / "templates" / "html" / template_name
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"错误：模板文件 {template_name} 未找到")
        return ""


def render_template(template: str, replacements: Dict[str, str]) -> str:
    """使用字典替换模板中的占位符"""
    result = template
    for key, value in replacements.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, value)
    return result


def generate_categories_html(categories: List[str]) -> str:
    """生成学科列表的HTML"""
    if not categories:
        return ""
    
    html_items = []
    for cat in categories:
        # 提取学科代码（忽略注释）
        cat_code = cat.split('#')[0].strip()
        if cat_code:
            html_items.append(f'<li class="config-item">{cat_code}</li>')
    
    return "\n".join(html_items)


def generate_keywords_html(keywords: List[str]) -> str:
    """生成关键词列表的HTML"""
    if not keywords:
        return ""
    
    html_items = []
    for keyword in keywords:
        keyword = keyword.strip()
        if keyword:
            html_items.append(f'<li class="config-item">{keyword}</li>')
    
    return "\n".join(html_items)
    
def generate_counter_section(categorized_papers: Dict[str, List[Dict]]) -> str:
    """生成论文统计部分的HTML"""
    counter_html = []
    
    # 计算各学科论文数量
    for category, papers in categorized_papers.items():
        count = len(papers)
        counter_html.append(f'''
        <div class="counter-item">
            <div class="counter-category">{category}</div>
            <div class="counter-value">{count}</div>
        </div>
        ''')
    
    # 计算总计
    total_papers = sum(len(papers) for papers in categorized_papers.values())
    counter_html.append(f'''
    <div class="counter-item" style="background-color: #e8f4fc;">
        <div class="counter-category" style="font-weight: bold;">总计</div>
        <div class="counter-value" style="color: #2c3e50;">{total_papers}</div>
    </div>
    ''')
    
    return "\n".join(counter_html)


def generate_selection_section(categorized_papers: Dict[str, List[Dict]]) -> str:
    """生成精选论文部分的HTML"""
    selection_html = []
    
    # 收集所有精选论文
    all_selected_papers = []
    for category, papers in categorized_papers.items():
        for paper in papers:
            if paper.get('selected', False):
                paper['primary_category'] = category  # 直接使用当前分类作为主学科
                all_selected_papers.append(paper)
    
    if not all_selected_papers:
        return '<p style="color: #666; font-style: italic;">今日无精选论文</p>'
    
    # 按学科分组显示精选论文
    for category in CATEGORIES.keys():
        category_selected = [p for p in all_selected_papers if p['primary_category'] == category]
        if not category_selected:
            continue
            
        # 添加学科标题
        selection_html.append(f'<h3 style="color: #4a6fa5; margin-top: 15px; margin-bottom: 10px;">{category}</h3>')
        
        for paper in category_selected:
            paper_id = paper['id']
            title = escape_html(paper.get('title', '无标题'))
            authors = format_authors(paper.get('authors', []))
            
            selection_html.append(f'''
            <div class="paper-item">
                <div class="paper-title">
                    <a href="https://arxiv.org/abs/{paper_id}" target="_blank">{title}</a>
                    <span class="selection-badge">⭐ 精选</span>
                </div>
                <div class="paper-authors">{authors}</div>
                <div class="paper-categories">
                    {generate_category_tags(paper.get('categories', []))}
                </div>
            </div>
            ''')
    
    # 处理others分类的精选论文
    if 'others' in categorized_papers:
        others_selected = [p for p in all_selected_papers if p['primary_category'] == 'others']
        if others_selected:
            selection_html.append('<h3 style="color: #4a6fa5; margin-top: 15px; margin-bottom: 10px;">others</h3>')
            for paper in others_selected:
                paper_id = paper['id']
                title = escape_html(paper.get('title', '无标题'))
                authors = format_authors(paper.get('authors', []))
                
                selection_html.append(f'''
                <div class="paper-item">
                    <div class="paper-title">
                        <a href="https://arxiv.org/abs/{paper_id}" target="_blank">{title}</a>
                        <span class="selection-badge">⭐ 精选</span>
                    </div>
                    <div class="paper-authors">{authors}</div>
                    <div class="paper-categories">
                        {generate_category_tags(paper.get('categories', []))}
                    </div>
                </div>
                ''')
    
    return "\n".join(selection_html)


def generate_category_tags(categories: List[str]) -> str:
    """生成分类标签的HTML"""
    if not categories:
        return ""
    
    tags = []
    for cat in categories[:5]:  # 最多显示5个分类
        tags.append(f'<span class="category-tag">{cat}</span>')
    
    if len(categories) > 5:
        tags.append(f'<span class="category-tag">+{len(categories)-5}</span>')
    
    return "\n".join(tags)
    
def generate_category_sections(categorized_papers: Dict[str, List[Dict]]) -> str:
    """按学科生成论文部分的HTML"""
    category_sections = []
    
    # 按配置的学科顺序生成
    for category in CATEGORIES.keys():
        if category in categorized_papers and categorized_papers[category]:
            papers = categorized_papers[category]
            
            # 将精选论文放在前面
            sorted_papers = sorted(papers, key=lambda x: not x.get('selected', False))
            
            section_id = category.replace('.', '-')  # 用于锚点的ID
            category_sections.append(f'<div id="{section_id}" class="category-section">')
            category_sections.append(f'<h3 class="category-title">{category}</h3>')
            category_sections.append('<div class="paper-list">')
            
            for paper in sorted_papers:
                category_sections.append(generate_paper_html(paper))
            
            category_sections.append('</div>')
            category_sections.append('</div>')
    
    # 处理others分类
    if 'others' in categorized_papers and categorized_papers['others']:
        papers = categorized_papers['others']
        sorted_papers = sorted(papers, key=lambda x: not x.get('selected', False))
        
        category_sections.append('<div id="others" class="category-section">')
        category_sections.append('<h3 class="category-title">others</h3>')
        category_sections.append('<div class="paper-list">')
        
        for paper in sorted_papers:
            category_sections.append(generate_paper_html(paper))
        
        category_sections.append('</div>')
        category_sections.append('</div>')
    
    return "\n".join(category_sections)


def generate_paper_html(paper: Dict) -> str:
    """生成单篇论文的HTML"""
    paper_id = paper['id']
    title = escape_html(paper.get('title', '无标题'))
    authors = format_authors(paper.get('authors', []))
    categories = paper.get('categories', [])
    comment = paper.get('comment', '')
    is_selected = paper.get('selected', False)
    
    # 处理评论中的LaTeX公式
    comment_html = process_latex_in_comment(comment)
    
    html = f'''
    <div id="paper-{paper_id}" class="paper-item">
        <div class="paper-title">
            <a href="https://arxiv.org/abs/{paper_id}" target="_blank">{title}</a>
    '''
    
    if is_selected:
        html += '<span class="selection-badge">⭐ 精选</span>'
    
    html += f'''
        </div>
        <div class="paper-authors">{authors}</div>
        <div class="paper-categories">
            {generate_category_tags(categories)}
        </div>
    '''
    
    if comment_html:
        html += f'''
        <div class="paper-comment">
            {comment_html}
        </div>
        '''
    
    html += '</div>'
    return html


def process_latex_in_comment(comment: str) -> str:
    """处理评论中的LaTeX公式，确保KaTeX能正确渲染"""
    if not comment:
        return ""
    
    # 替换行内公式 \( \) 为 $ $
    comment = re.sub(r'\\\((.+?)\\\)', r'$\1$', comment)
    
    # 替换行内公式 $ $ 为 \( \)（如果还未处理）
    comment = re.sub(r'\$(.+?)\$', r'\(\1\)', comment)
    
    # 处理行间公式 \[ \] 为 $$ $$
    comment = re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', comment)
    
    # 处理行间公式 $$ $$ 为 \[ \]
    comment = re.sub(r'\$\$(.+?)\$\$', r'\[\1\]', comment)
    
    return comment
    
def load_categorized_papers() -> Dict[str, List[Dict]]:
    """加载分类后的论文数据"""
    json_path = DATA_RAW_DIR / "categorized_papers.json"
    
    if not json_path.exists():
        print(f"错误：JSON文件未找到: {json_path}")
        return {}
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            categorized_papers = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误：JSON文件解析失败: {e}")
        return {}
    
    # 确保返回的字典包含所有配置的学科和others
    result = {}
    
    # 添加配置的学科
    for category in CATEGORIES.keys():
        # 如果JSON中有该学科，则使用，否则为空列表
        result[category] = categorized_papers.get(category, [])
    
    # 添加others分类
    result['others'] = categorized_papers.get('others', [])
    
    return result


def generate_daily_html(date_str: str = None) -> bool:
    """生成每日报告的HTML页面"""
    # 如果没有提供日期，使用当前日期
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    print(f"开始生成每日报告 HTML: {date_str}")
    
    # 1. 加载数据
    categorized_papers = load_categorized_papers()
    if not categorized_papers:
        print("警告：没有找到论文数据，跳过HTML生成")
        return False
    
    # 2. 读取学科和关键词配置
    categories_list = read_list_file("config/categories.txt")
    keywords_list = read_list_file("config/keywords.txt")
    
    # 3. 读取每日报告模板
    template = load_template("daily_report_template.html")
    if not template:
        return False
    
    # 4. 生成各个部分
    counter_section = generate_counter_section(categorized_papers)
    selection_section = generate_selection_section(categorized_papers)
    category_sections = generate_category_sections(categorized_papers)
    categories_html = generate_categories_html(categories_list)
    keywords_html = generate_keywords_html(keywords_list)
    
    # 5. 替换模板中的占位符
    replacements = {
        'DATE': date_str,
        'CATEGORIES_LIST_PLACEHOLDER': categories_html,
        'KEYWORDS_LIST_PLACEHOLDER': keywords_html,
        'COUNTER_SECTION_PLACEHOLDER': counter_section,
        'SELECTION_SECTION_PLACEHOLDER': selection_section,
        'CATEGORY_SECTIONS_PLACEHOLDER': category_sections
    }
    
    html_content = render_template(template, replacements)
    
    # 6. 确保输出目录存在
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    # 7. 保存HTML文件
    output_path = docs_dir / f"daily_{date_str}.html"
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"每日报告已保存: {output_path}")
        return True
    except IOError as e:
        print(f"错误：保存文件失败: {e}")
        return False


def scan_existing_daily_files() -> List[Dict[str, Any]]:
    """扫描docs目录中已有的每日报告文件"""
    docs_dir = Path(__file__).parent.parent / "docs"
    
    if not docs_dir.exists():
        return []
    
    daily_files = []
    
    for file_path in docs_dir.glob("daily_*.html"):
        match = re.search(r'daily_(\d{4}-\d{2}-\d{2})\.html$', file_path.name)
        if match:
            date_str = match.group(1)
            
            # 读取文件内容提取统计信息
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 从HTML中提取统计信息
            total_match = re.search(r'总计.*?counter-value[^>]*?>(\d+)<', content, re.DOTALL)
            total_papers = int(total_match.group(1)) if total_match else 0
            
            selected_match = re.findall(r'selection-badge[^>]*?>⭐ 精选<', content)
            selected_count = len(selected_match) // 2
            
            # 修复正则表达式：更精确地提取学科和计数
            category_counts = {}
            # 使用更精确的正则表达式，避免匹配到空学科
            category_matches = re.findall(
                r'<div\s+class="counter-category"[^>]*>([^<]+)</div>\s*<div\s+class="counter-value"[^>]*>(\d+)</div>',
                content
            )
            
            for cat, count in category_matches:
                cat = cat.strip()
                if cat and cat != '总计':  # 排除空字符串和总计
                    category_counts[cat] = int(count)
            
            daily_files.append({
                'date': date_str,
                'filename': file_path.name,
                'total_papers': total_papers,
                'selected_count': selected_count,
                'category_counts': category_counts,
            })
    
    return daily_files
    
def generate_index_html() -> bool:
    """生成索引页HTML"""
    print("开始生成索引页 HTML")
    
    # 1. 读取学科和关键词配置
    categories_list = read_list_file("config/categories.txt")
    keywords_list = read_list_file("config/keywords.txt")
    
    # 2. 读取索引模板
    template = load_template("index_template.html")
    if not template:
        return False
    
    # 3. 扫描现有每日报告文件
    daily_files = scan_existing_daily_files()
    
    # 按日期倒序排列（最新的在最上面）
    daily_files.sort(key=lambda x: x['date'], reverse=True)
    
    # 4. 生成日期列表HTML
    date_items = []
    for daily_info in daily_files:
        date_str = daily_info['date']
        display_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y年%m月%d日")
        
        # 生成学科统计标签
        category_tags = []
        for cat, count in daily_info['category_counts'].items():
            if count > 0:
                category_tags.append(f'<span class="category-tag">{cat}: {count}</span>')
        
        date_item = f'''
        <div class="date-card">
            <a href="{daily_info['filename']}" class="date-link">{display_date}</a>
            <div class="stats">
                <div class="stat-item">总论文数: {daily_info['total_papers']}</div>
                <div class="stat-item">精选论文: {daily_info['selected_count']}</div>
                <div class="category-tags">
                    {''.join(category_tags)}
                </div>
            </div>
        </div>
        '''
        date_items.append(date_item)
    
    date_list_html = "\n".join(date_items) if date_items else '<p style="color: #666; font-style: italic;">暂无报告</p>'
    
    # 5. 生成学科和关键词列表HTML
    categories_html = generate_categories_html(categories_list)
    keywords_html = generate_keywords_html(keywords_list)
    
    # 6. 替换模板中的占位符
    last_update = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    replacements = {
        'DATE_LIST_PLACEHOLDER': date_list_html,
        'CATEGORIES_LIST_PLACEHOLDER': categories_html,
        'KEYWORDS_LIST_PLACEHOLDER': keywords_html,
        'LAST_UPDATE': last_update
    }
    
    html_content = render_template(template, replacements)
    
    # 7. 保存索引页
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    output_path = docs_dir / "index.html"
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"索引页已保存: {output_path}")
        return True
    except IOError as e:
        print(f"错误：保存文件失败: {e}")
        return False
        
def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='生成HTML格式的arXiv论文报告')
    parser.add_argument('--date', type=str, help='指定日期（格式：YYYY-MM-DD），默认使用今天')
    parser.add_argument('--skip-index', action='store_true', help='跳过索引页生成')
    
    args = parser.parse_args()
    
    # 生成每日报告
    success = generate_daily_html(args.date)
    
    if not success:
        print("每日报告生成失败")
        return
    
    # 更新索引页（除非指定跳过）
    if not args.skip_index:
        generate_index_html()
    else:
        print("跳过索引页生成")
    
    print("HTML生成完成！")


if __name__ == "__main__":
    main()
