import sys
import os
import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 从现有的config模块导入配置
from config.loader import load_config
from config.settings import Config

# 加载配置
config = load_config()
DATA_RAW_DIR = config.DATA_RAW_DIR
TEMPLATES_DIR = config.TEMPLATES_DIR
# 注意：CATEGORIES 是一个属性，不是字段，所以我们需要调用它
CATEGORIES = config.CATEGORIES

def convert_chinese_punctuation_to_english(text):
    """
    将中文标点转换为英文标点（简化版本）
    
    Args:
        text: 包含中文标点的文本
        
    Returns:
        转换后的文本，中文标点替换为英文标点
    """
    if not text:
        return text
    
    # 中文标点到英文标点的简单映射
    punctuation_map = {
        '，': ', ',   # 中文逗号 -> 英文逗号 + 空格
        '。': '. ',  # 中文句号 -> 英文句号 + 空格
        '；': '; ',  # 中文分号 -> 英文分号 + 空格
        '：': ': ',  # 中文冒号 -> 英文冒号 + 空格
        '？': '? ',  # 中文问号 -> 英文问号 + 空格
        '！': '! ',  # 中文感叹号 -> 英文感叹号 + 空格
        '（': '(',   # 中文左括号 -> 英文左括号
        '）': ') ',  # 中文右括号 -> 英文右括号 + 空格
        '【': '[',   # 中文左方括号 -> 英文左方括号
        '】': '] ',  # 中文右方括号 -> 英文右方括号 + 空格
        '「': '"',   # 中文左引号 -> 英文双引号
        '」': '" ',  # 中文右引号 -> 英文双引号 + 空格
        '『': '"',   # 中文左双引号 -> 英文双引号
        '』': '" ',  # 中文右双引号 -> 英文双引号 + 空格
        '《': '"',   # 中文左书名号 -> 英文双引号
        '》': '" ',  # 中文右书名号 -> 英文双引号 + 空格
    }
    
    # 简单替换所有中文标点
    for cn_punct, en_punct in punctuation_map.items():
        text = text.replace(cn_punct, en_punct)
    
    # 处理可能出现的多个连续空格
    text = text.replace('  ', ' ')
    
    return text.strip()

def escape_latex(text):
    """
    LaTeX特殊字符转义函数（简化版）
    注意：这个函数可能不完整，根据需要添加更多转义规则
    """
    if not text:
        return text
    
    # 基本的LaTeX特殊字符转义
    escape_map = {
        '\\': r'\\',
    }
    
    for char, replacement in escape_map.items():
        text = text.replace(char, replacement)
    
    return text

def load_papers_feedback():
    """加载论文反馈数据"""
    input_file = os.path.join(DATA_RAW_DIR, "categorized_papers.json")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误: 输入文件 {input_file} 不存在")
        print("请先生成反馈数据")
        return None
    except Exception as e:
        print(f"加载反馈数据时出错: {e}")
        return None

def get_primary_category(paper):
    """获取论文的主学科（分类列表中的第一个）"""
    categories = paper.get('categories', [])
    return categories[0] if categories else "unknown"

def get_other_categories(paper):
    """获取论文的其它学科（除主学科外的其它分类）"""
    categories = paper.get('categories', [])
    if len(categories) <= 1:
        return []
    return categories[1:]

def format_authors(authors):
    """格式化作者列表"""
    if not authors:
        return ""
    return ", ".join([escape_latex(author) for author in authors])

def generate_counter_section(categorized_papers):
    """生成学科统计部分"""
    lines = []
    
    # 按照配置中定义的顺序遍历分类
    for category in CATEGORIES.keys():
        if category in categorized_papers:
            count = len(categorized_papers[category])
            lines.append(f"{category}: {count}")
    
    # 添加others分类
    if "others" in categorized_papers:
        count = len(categorized_papers["others"])
        lines.append(f"others: {count}")
    
    # 在每行后面添加两个换行
    return "\n\n".join(lines) + "\n\n"

def generate_selection_section(categorized_papers):
    """生成精选论文部分，按照分类顺序排列"""
    lines = []
    
    # 按照配置中定义的顺序遍历分类
    for category in CATEGORIES.keys():
        if category in categorized_papers:
            papers = categorized_papers[category]
            # 修正：直接访问selected字段，而不是通过feedback
            selected_papers = [p for p in papers if p.get('selected', False)]
            
            if selected_papers:
                for paper in selected_papers:
                    # 论文基本信息
                    paper_id = paper.get('id', '')
                    #title = escape_latex(paper.get('title', ''))
                    title = paper.get('title', '')
                    authors = format_authors(paper.get('authors', []))
                    primary_category = get_primary_category(paper)
                    other_categories = get_other_categories(paper)
                    
                    # 格式化其它学科
                    other_cats_str = ""
                    if other_categories:
                        other_cats_str = ", " + ", ".join(other_categories)
                    
                    # 生成行
                    line = f"\\arxiv{{{paper_id}}}{{{title}}}{{{authors}}}\\textbf{{{primary_category}}}{other_cats_str}. \\hyperlink{{{paper_id}}}{{$\\rightsquigarrow$}}"
                    lines.append(line)
    
    # 处理others分类
    if "others" in categorized_papers:
        papers = categorized_papers["others"]
        # 修正：直接访问selected字段
        selected_papers = [p for p in papers if p.get('selected', False)]
        
        if selected_papers:
            for paper in selected_papers:
                # 论文基本信息
                paper_id = paper.get('id', '')
                #title = escape_latex(paper.get('title', ''))
                title = paper.get('title', '')
                authors = format_authors(paper.get('authors', []))
                primary_category = get_primary_category(paper)
                other_categories = get_other_categories(paper)
                
                # 格式化其它学科
                other_cats_str = ""
                if other_categories:
                    other_cats_str = ", " + ", ".join(other_categories)
                
                # 生成行
                line = f"\\arxiv{{{paper_id}}}{{{title}}}{{{authors}}}\\textbf{{{primary_category}}}{other_cats_str}. \\hyperlink{{{paper_id}}}{{$\\rightsquigarrow$}}"
                lines.append(line)
    
    # 在每行后面添加两个换行
    if lines:
        return "\n\n".join(lines) + "\n\n"
    else:
        return ""

def generate_body_section(categorized_papers):
    """生成正文部分，保持原始顺序"""
    sections = []
    
    # 按照配置中定义的顺序遍历分类
    for category in CATEGORIES.keys():
        if category in categorized_papers:
            papers = categorized_papers[category]
            if not papers:
                continue
            
            # 添加学科章节
            sections.append(f"\\section{{{category}}}")
            
            # 按照原始顺序处理论文
            for paper in papers:
                # 论文基本信息
                paper_id = paper.get('id', '')
                #title = escape_latex(paper.get('title', ''))
                title = paper.get('title', '')
                authors = format_authors(paper.get('authors', []))
                primary_category = get_primary_category(paper)
                other_categories = get_other_categories(paper)
                
                # 格式化其它学科
                other_cats_str = ""
                if other_categories:
                    other_cats_str = ", " + ", ".join(other_categories)
                
                # 论文基本信息行
                sections.append(f"\\arxivwithtarget{{{paper_id}}}{{{title}}}{{{authors}}}\\textbf{{{primary_category}}}{other_cats_str}.")
                sections.append("")  # 空行
                
                # 反馈内容 - 修正：直接访问comment字段
                comment = paper.get('comment', '')
                if comment:
                    # 转换中文标点为英文标点
                    comment = convert_chinese_punctuation_to_english(comment)
                    sections.append(comment)
                
                sections.append("")  # 空行
                sections.append("")  # 另一个空行，总共两个换行
    
    # 处理others分类
    if "others" in categorized_papers:
        papers = categorized_papers["others"]
        if papers:
            # 添加学科章节
            sections.append("\\section{others}")
            
            # 按照原始顺序处理论文
            for paper in papers:
                # 论文基本信息
                paper_id = paper.get('id', '')
                #title = escape_latex(paper.get('title', ''))
                title = paper.get('title', '')
                authors = format_authors(paper.get('authors', []))
                primary_category = get_primary_category(paper)
                other_categories = get_other_categories(paper)
                
                # 格式化其它学科
                other_cats_str = ""
                if other_categories:
                    other_cats_str = ", " + ", ".join(other_categories)
                
                # 论文基本信息行
                sections.append(f"\\arxivwithtarget{{{paper_id}}}{{{title}}}{{{authors}}}\\textbf{{{primary_category}}}{other_cats_str}.")
                sections.append("")  # 空行
                
                # 反馈内容 - 修正：直接访问comment字段
                comment = paper.get('comment', '')
                if comment:
                    # 转换中文标点为英文标点
                    comment = convert_chinese_punctuation_to_english(comment)
                    sections.append(comment)
                
                sections.append("")  # 空行
                sections.append("")  # 另一个空行，总共两个换行
    
    return "\n".join(sections)

def process_template(template_content, counter_section, selection_section, body_section):
    """处理模板，插入各个部分的内容"""
    # 替换计数器部分
    counter_start = "%counter_begin"
    counter_end = "%counter_end"
    
    if counter_start in template_content and counter_end in template_content:
        start_idx = template_content.find(counter_start) + len(counter_start)
        end_idx = template_content.find(counter_end)
        
        # 保留标记，在它们之间插入内容
        new_content = template_content[:start_idx] + "\n" + counter_section + template_content[end_idx:]
        template_content = new_content
    else:
        print("警告: 未找到counter标记")
    
    # 替换精选部分
    selection_start = "%selection_begin"
    selection_end = "%selection_end"
    
    if selection_start in template_content and selection_end in template_content:
        start_idx = template_content.find(selection_start) + len(selection_start)
        end_idx = template_content.find(selection_end)
        
        new_content = template_content[:start_idx] + "\n" + selection_section + template_content[end_idx:]
        template_content = new_content
    else:
        print("警告: 未找到selection标记")
    
    # 替换正文部分
    body_start = "%body_begin"
    body_end = "%body_end"
    
    if body_start in template_content and body_end in template_content:
        start_idx = template_content.find(body_start) + len(body_start)
        end_idx = template_content.find(body_end)
        
        new_content = template_content[:start_idx] + "\n" + body_section + "\n" + template_content[end_idx:]
        template_content = new_content
    else:
        print("警告: 未找到body标记")
    
    return template_content

def main():
    """主函数：生成LaTeX文件"""
    print("开始生成LaTeX文件...")
    print("=" * 50)
    
    # 加载论文数据
    categorized_papers = load_papers_feedback()
    if categorized_papers is None:
        return
    
    # 显示统计信息
    print("论文统计:")
    total_papers = 0
    for category in list(CATEGORIES.keys()) + ["others"]:
        if category in categorized_papers:
            count = len(categorized_papers[category])
            print(f"  {category}: {count} 篇")
            total_papers += count
    
    print(f"总计: {total_papers} 篇论文")
    
    # 统计精选论文 - 修正：直接访问selected字段
    selected_count = 0
    for category in list(CATEGORIES.keys()) + ["others"]:
        if category in categorized_papers:
            papers = categorized_papers[category]
            for paper in papers:
                if paper.get('selected', False):
                    selected_count += 1
    
    print(f"精选论文: {selected_count} 篇")
    
    # 生成各个部分的内容
    print("\n生成各个部分的内容...")
    counter_section = generate_counter_section(categorized_papers)
    selection_section = generate_selection_section(categorized_papers)
    body_section = generate_body_section(categorized_papers)
    
    # 加载模板
    template_file = os.path.join(TEMPLATES_DIR, "template.tex")
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            template_content = f.read()
        print(f"✓ 加载模板: {template_file}")
    except FileNotFoundError:
        print(f"错误: 模板文件 {template_file} 不存在")
        return
    except Exception as e:
        print(f"加载模板时出错: {e}")
        return
    
    # 处理模板
    processed_content = process_template(template_content, counter_section, selection_section, body_section)
    
    # 生成输出文件名
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_filename = f"daily_feedback_{date_str}.tex"
    output_dir = os.path.join(DATA_RAW_DIR, "daily_feedback_tex")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, output_filename)
    
    # 保存生成的LaTeX文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(processed_content)
        print(f"\n✓ LaTeX文件已保存到: {output_file}")
        
        # 显示文件大小
        file_size = os.path.getsize(output_file)
        print(f"文件大小: {file_size} 字节")
        
    except Exception as e:
        print(f"保存LaTeX文件时出错: {e}")

if __name__ == "__main__":
    main()
