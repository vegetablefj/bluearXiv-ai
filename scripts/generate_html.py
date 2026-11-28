#!/usr/bin/env python3
"""
HTML生成脚本 - bluearXiv-ai 项目
基于 JSON 数据生成 HTML 格式的论文报告
"""

import os
import json
import re
import datetime
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List, Any
from urllib.parse import quote

# 导入项目配置
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 从config.settings导入Config类
from config.settings import Config

# 创建配置实例
config = Config()

# 从配置实例获取路径和分类
DATA_RAW_DIR = Path(config.DATA_RAW_DIR)
DOCS_DIR = Path(config.PROJECT_ROOT) / "docs"
CATEGORIES = config.CATEGORIES
DISPLAY_TIMEZONE = datetime.timezone(datetime.timedelta(hours=8))
FEATURED_LIMIT = 6
DAILY_FILENAME = re.compile(r"daily_(\d{4}-\d{2}-\d{2})\.html")

# 历史归档只有 HTML。使用原有的标题、精选标记和作者结构读取其索引信息。
FEATURED_PAPER_RE = re.compile(
    r'<a href="https://arxiv\.org/abs/([^"]+)"[^>]*>([^<]*)</a>\s*'
    r'<span class="selection-badge">[^<]*</span>\s*</div>\s*'
    r'<div class="paper-authors">([^<]*)</div>'
)

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
    return escape(text or "", quote=True)


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
    rendered = re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: replacements.get(match[1], match[0]), template)
    return re.sub(r"(?m)^[ \t]+$", "", rendered)


def write_html(path: Path, html_content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as pending:
            temporary_path = Path(pending.name)
            pending.write(html_content)
        temporary_path.replace(path)
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)


def generate_categories_html(categories: List[str]) -> str:
    """生成学科列表的HTML"""
    if not categories:
        return ""
    
    html_items = []
    for cat in categories:
        # 提取学科代码（忽略注释）
        cat_code = cat.split('#')[0].strip()
        if cat_code:
            html_items.append(f'<li class="config-item">{escape_html(cat_code)}</li>')
    
    return "\n".join(html_items)


def generate_keywords_html(keywords: List[str]) -> str:
    """生成关键词列表的HTML"""
    if not keywords:
        return ""
    
    html_items = []
    for keyword in keywords:
        keyword = keyword.strip()
        if keyword:
            html_items.append(f'<li class="config-item">{escape_html(keyword)}</li>')
    
    return "\n".join(html_items)
    
def generate_counter_section(categorized_papers: Dict[str, List[Dict]]) -> str:
    """生成论文统计部分的HTML"""
    counter_html = []
    
    # 计算各学科论文数量
    for category, papers in categorized_papers.items():
        count = len(papers)
        counter_html.append(f'''
        <div class="counter-item">
            <div class="counter-category">{escape_html(category)}</div>
            <div class="counter-value">{count}</div>
        </div>
        ''')
    
    # 计算总计
    total_papers = sum(len(papers) for papers in categorized_papers.values())
    counter_html.append(f'''
    <div class="counter-item counter-total">
        <div class="counter-category">总计</div>
        <div class="counter-value">{total_papers}</div>
    </div>
    ''')
    
    return "\n".join(counter_html)


def generate_selection_section(categorized_papers: Dict[str, List[Dict]]) -> str:
    """生成精选论文部分的HTML"""
    selection_html = []
    for category, papers in categorized_papers.items():
        category_selected = [paper for paper in papers if paper.get('selected')]
        if not category_selected:
            continue

        selection_html.append(f'<h3>{escape_html(category)}</h3>')
        for paper in category_selected:
            paper_id = quote(paper["id"], safe="/.")
            title = escape_html(paper.get('title', '无标题'))
            authors = escape_html(format_authors(paper.get('authors', [])))

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
                <a class="paper-detail-link" href="#paper-{paper_id}">查看中文摘要</a>
            </div>
            ''')

    return "\n".join(selection_html) if selection_html else '<p>今日无精选论文</p>'


def generate_category_tags(categories: List[str]) -> str:
    """生成分类标签的HTML"""
    if not categories:
        return ""
    
    tags = []
    for cat in categories[:5]:  # 最多显示5个分类
        tags.append(f'<span class="category-tag">{escape_html(cat)}</span>')
    
    if len(categories) > 5:
        tags.append(f'<span class="category-tag">+{len(categories)-5}</span>')
    
    return "\n".join(tags)


def generate_category_nav(categorized_papers: Dict[str, List[Dict]]) -> str:
    return "\n".join(
        f'<a href="#{escape_html(category.replace(".", "-"))}">{escape_html(category)}'
        f' <span>{len(papers)}</span></a>'
        for category, papers in categorized_papers.items()
        if papers
    )


def generate_category_sections(categorized_papers: Dict[str, List[Dict]]) -> str:
    """按学科生成论文部分的HTML"""
    category_sections = []
    for category, papers in categorized_papers.items():
        if not papers:
            continue

        sorted_papers = sorted(papers, key=lambda x: not x.get('selected', False))
        section_id = escape_html(category.replace(".", "-"))
        category_sections.append(f'<section id="{section_id}" class="category-section">')
        category_sections.append(f'<h3 class="category-title">{escape_html(category)}</h3>')
        category_sections.append('<div class="paper-list">')
        category_sections.extend(generate_paper_html(paper) for paper in sorted_papers)
        category_sections.append('</div></section>')

    return "\n".join(category_sections)


def generate_paper_html(paper: Dict) -> str:
    """生成单篇论文的HTML"""
    paper_id = quote(paper["id"], safe="/.")
    title = escape_html(paper.get('title', '无标题'))
    authors = escape_html(format_authors(paper.get('authors', [])))
    categories = paper.get('categories', [])
    comment = paper.get('comment', '')
    is_selected = paper.get('selected', False)
    
    # 中文摘要中的公式由浏览器渲染。
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
        <details class="paper-comment">
            <summary>中文摘要</summary>
            <div>{comment_html}</div>
        </details>
        '''
    
    html += '</div>'
    return html


def process_latex_in_comment(comment: str) -> str:
    """将中文摘要作为文本插入页面，KaTeX 在浏览器中识别公式分隔符。"""
    comment = (comment or "").strip()
    if not comment or comment.startswith(("API错误", "API响应格式错误")):
        return "中文摘要暂不可用。"
    return escape_html(comment)
    
def load_categorized_papers() -> Dict[str, List[Dict]]:
    """加载分类后的论文数据"""
    json_path = DATA_RAW_DIR / "categorized_papers.json"
    try:
        categorized_papers = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(categorized_papers, dict) or any(
            not isinstance(papers, list) for papers in categorized_papers.values()
        ):
            raise ValueError("分类数据必须是各学科对应的论文列表")
        return {category: categorized_papers.get(category, []) for category in (*CATEGORIES, "others")}
    except (OSError, ValueError) as error:
        print(f"错误：无法加载 {json_path}: {error}")
        return {}


def generate_daily_html(
    date_str: str = None, *, source_date: str = None, output_dir: Path = DOCS_DIR
) -> bool:
    """生成每日报告的HTML页面"""
    date_str = date_str or datetime.date.today().isoformat()
    print(f"开始生成每日报告 HTML: {date_str}")

    categorized_papers = load_categorized_papers()
    if not any(categorized_papers.values()):
        print("错误：没有可发布的论文数据")
        return False

    template = load_template("daily_report_template.html")
    if not template:
        return False

    source_date_html = ""
    if source_date:
        source_date_html = (
            f'<p class="source-date">arXiv 发布批次 '
            f'<time datetime="{source_date}">{source_date}</time></p>'
        )

    replacements = {
        "DATE": date_str,
        "SOURCE_DATE_PLACEHOLDER": source_date_html,
        "CATEGORIES_LIST_PLACEHOLDER": generate_categories_html(read_list_file("config/categories.txt")),
        "KEYWORDS_LIST_PLACEHOLDER": generate_keywords_html(read_list_file("config/keywords.txt")),
        "COUNTER_SECTION_PLACEHOLDER": generate_counter_section(categorized_papers),
        "SELECTION_SECTION_PLACEHOLDER": generate_selection_section(categorized_papers),
        "CATEGORY_NAV_PLACEHOLDER": generate_category_nav(categorized_papers),
        "CATEGORY_SECTIONS_PLACEHOLDER": generate_category_sections(categorized_papers),
    }

    output_path = output_dir / f"daily_{date_str}.html"
    try:
        write_html(output_path, render_template(template, replacements))
        print(f"每日报告已保存: {output_path}")
        return True
    except OSError as error:
        print(f"错误：保存HTML文件失败: {error}")
        return False


class CanonicalLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        attributes = dict(attrs)
        if "canonical" in (attributes.get("rel") or "").lower().split():
            self.links.add(attributes.get("href") or "")


def read_canonical_filename(content: str) -> str | None:
    head = re.search(r"<head\b[^>]*>(.*?)</head\s*>", content, re.IGNORECASE | re.DOTALL)
    if head and "canonical" in head[1].lower():
        parser = CanonicalLinkParser()
        parser.feed(head[1])
        if len(parser.links) == 1:
            filename = next(iter(parser.links)).strip().removeprefix("./")
            if DAILY_FILENAME.fullmatch(filename):
                return filename
    return None


def scan_existing_daily_files(output_dir: Path = DOCS_DIR) -> List[Dict[str, Any]]:
    """扫描已有的每日报告文件，兼容历史归档的 HTML。"""
    reports = {}
    canonical_links = {}
    for file_path in sorted(output_dir.glob("daily_*.html"), reverse=True):
        match = DAILY_FILENAME.fullmatch(file_path.name)
        if not match or not file_path.is_file() or file_path.is_symlink():
            continue
        try:
            publication_date = datetime.date.fromisoformat(match[1])
        except ValueError:
            continue

        content = file_path.read_text(encoding="utf-8")
        canonical_filename = read_canonical_filename(content)
        if canonical_filename and canonical_filename != file_path.name:
            canonical_links[file_path.name] = canonical_filename
        category_counts = {
            unescape(category.strip()): int(count)
            for category, count in re.findall(
                r'<div\s+class="counter-category"[^>]*>([^<]+)</div>\s*'
                r'<div\s+class="counter-value"[^>]*>(\d+)</div>',
                content,
            )
        }
        total = category_counts.pop("总计", sum(category_counts.values()))
        featured_papers = {
            paper_id: (unescape(title), unescape(authors))
            for paper_id, title, authors in FEATURED_PAPER_RE.findall(content)
        }
        reports[file_path.name] = {
            "date": publication_date,
            "filename": file_path.name,
            "total_papers": total,
            "featured_papers": featured_papers,
            "category_counts": category_counts,
            "alias_dates": [],
        }

    canonical_links = {
        source: target for source, target in canonical_links.items() if target in reports
    }
    superseded = set()
    for source, target in canonical_links.items():
        visited = {source}
        while target in canonical_links and target not in visited:
            visited.add(target)
            target = canonical_links[target]
        if target not in visited:
            reports[target]["alias_dates"].append(reports[source]["date"])
            superseded.add(source)

    return [report for filename, report in reports.items() if filename not in superseded]


def generate_archive_html(daily_files: List[Dict[str, Any]]) -> str:
    date_items = []
    for daily_info in daily_files:
        date = daily_info["date"]
        aliases = " ".join(day.isoformat() for day in sorted(daily_info["alias_dates"]))
        alias_attribute = f' data-alias-dates="{aliases}"' if aliases else ""
        category_counts = {category: count for category, count in daily_info["category_counts"].items() if count}
        category_tags = "".join(
            f'<span class="category-tag">{escape_html(category)}: {count}</span>'
            for category, count in category_counts.items()
        )
        date_items.append(f"""
        <article class="date-card" data-date="{date}"{alias_attribute}>
            <a href="{daily_info['filename']}" class="date-link"><time datetime="{date}">{date:%Y年%m月%d日}</time></a>
            <div class="stats">
                <div class="stat-item">论文 {daily_info['total_papers']} 篇</div>
                <div class="stat-item">精选 {len(daily_info['featured_papers'])} 篇</div>
            </div>
            <div class="category-tags">{category_tags}</div>
        </article>
        """)

    return "\n".join(date_items) if date_items else "<p>暂无往期日报。</p>"


def generate_latest_html(daily_info: Dict[str, Any]) -> str:
    date = daily_info["date"]
    total = daily_info["total_papers"]
    selected = len(daily_info["featured_papers"])
    return f"""
    <p class="edition-date"><time datetime="{date}">{date:%Y年%m月%d日}</time></p>
    <p class="edition-summary">{total} 篇论文 · {selected} 篇精选</p>
    <a class="edition-link" href="{daily_info['filename']}">阅读本期日报 <span aria-hidden="true">↗</span></a>
    """


def generate_home_features(daily_info: Dict[str, Any]) -> str:
    cards = []
    for paper_id, (title, authors) in list(daily_info["featured_papers"].items())[:FEATURED_LIMIT]:
        anchor = quote(unescape(paper_id), safe="/.%")
        detail_url = f"{daily_info['filename']}#paper-{anchor}"
        cards.append(f"""
        <article class="feature-card">
            <h3 class="feature-title"><a href="{detail_url}">{escape_html(title)}</a></h3>
            <p class="feature-meta">{escape_html(authors)}</p>
        </article>
        """)
    return "\n".join(cards) if cards else "<p>本期暂无精选论文。</p>"


def read_last_check(index_path: Path) -> datetime.datetime | None:
    if index_path.is_file():
        match = re.search(r'<time datetime="([^"]+)" data-last-check>', index_path.read_text(encoding="utf-8"))
        if match:
            return parse_check_time(match[1])
    return None


def render_last_check(checked_at: datetime.datetime | None) -> str:
    if checked_at is None:
        return "暂无记录"
    display_time = checked_at.astimezone(DISPLAY_TIMEZONE)
    return (
        f'<time datetime="{checked_at.isoformat()}" data-last-check>'
        f'{display_time:%Y-%m-%d %H:%M}（北京时间）</time>'
    )


def generate_index_html(*, output_dir: Path = DOCS_DIR, checked_at: datetime.datetime | None = None) -> bool:
    """生成索引页HTML"""
    print("开始生成索引页 HTML")
    template = load_template("index_template.html")
    if not template:
        return False

    output_path = output_dir / "index.html"
    try:
        daily_files = scan_existing_daily_files(output_dir)
        latest = daily_files[0] if daily_files else None
        last_check = render_last_check(checked_at or read_last_check(output_path))
        replacements = {
            "DATE_LIST_PLACEHOLDER": generate_archive_html(daily_files),
            "LATEST_EDITION_PLACEHOLDER": generate_latest_html(latest) if latest else "<p>暂无日报。</p>",
            "FEATURED_PAPERS_PLACEHOLDER": generate_home_features(latest) if latest else "<p>暂无精选论文。</p>",
            "LAST_CHECK_PLACEHOLDER": last_check,
            "LAST_UPDATE": last_check,
            "CATEGORIES_LIST_PLACEHOLDER": generate_categories_html(read_list_file("config/categories.txt")),
            "KEYWORDS_LIST_PLACEHOLDER": generate_keywords_html(read_list_file("config/keywords.txt")),
        }
        write_html(output_path, render_template(template, replacements))
        print(f"索引页已保存: {output_path}")
        return True
    except (OSError, ValueError) as error:
        print(f"错误：索引页生成失败: {error}")
        return False


def parse_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期应为 YYYY-MM-DD")
    return datetime.date.fromisoformat(value).isoformat()


def parse_check_time(value: str) -> datetime.datetime:
    timestamp = datetime.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    if timestamp.utcoffset() is None:
        raise ValueError("最近检查时间必须包含时区")
    return timestamp


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="生成HTML格式的arXiv论文报告")
    parser.add_argument("--date", help="指定日报日期（格式：YYYY-MM-DD），默认使用今天")
    parser.add_argument("--source-date", help="arXiv 论文发布批次日期（格式：YYYY-MM-DD）")
    parser.add_argument("--checked-at", help="成功抓取的时间（ISO 8601，带时区）")
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR, help="HTML 文件输出目录")
    parser.add_argument("--skip-index", action="store_true", help="跳过索引页生成")
    parser.add_argument("--index-only", action="store_true", help="只更新索引页")
    args = parser.parse_args()

    if args.index_only and (args.skip_index or args.date or args.source_date):
        parser.error("--index-only 不能与 --skip-index、--date 或 --source-date 同时使用")
    try:
        date = parse_date(args.date) if args.date else None
        source_date = parse_date(args.source_date) if args.source_date else None
        checked_at = parse_check_time(args.checked_at) if args.checked_at else None
    except ValueError as error:
        parser.error(str(error))

    if not args.index_only and not generate_daily_html(date, source_date=source_date, output_dir=args.output_dir):
        return 1
    if not args.skip_index and not generate_index_html(output_dir=args.output_dir, checked_at=checked_at):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
