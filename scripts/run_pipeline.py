"""Generate or check one arXiv announcement for the daily report."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

if __package__:
    from .fetch_paper_ids import CATEGORIES, deduplicate_papers, fetch_latest_issue
else:
    from fetch_paper_ids import CATEGORIES, deduplicate_papers, fetch_latest_issue


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
STATE_FILE = ROOT / 'data' / 'pipeline_state.json'
PAPERS_FILE = 'all_papers_unique.json'
ISSUE_FILE = 'issue.json'
DAILY_FILE = re.compile(r'daily_(\d{4}-\d{2}-\d{2})\.html')
PAPER_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9./_-]*')


def parse_date(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError(f"日期须使用 YYYY-MM-DD: {value}")
    return parsed


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def paper_ids(papers):
    if not isinstance(papers, list):
        raise ValueError('源论文数据必须是列表')
    ids = set()
    for paper in papers:
        if not isinstance(paper, dict):
            raise ValueError('源论文数据包含无效条目')
        identifier = paper.get('id')
        if not isinstance(identifier, str) or not PAPER_ID.fullmatch(identifier) or identifier in ids:
            raise ValueError('源论文数据包含无效或重复的 arXiv 标识符')
        for field in ('title', 'abstract'):
            if not isinstance(paper.get(field), str):
                raise ValueError(f"{identifier} 缺少 {field}")
        if not paper['title'].strip():
            raise ValueError(f"{identifier} 缺少论文标题")
        for field in ('authors', 'categories'):
            values = paper.get(field)
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError(f"{identifier} 的 {field} 无效")
        ids.add(identifier)
    return ids


def issue_metadata(source_date, papers):
    ids = paper_ids(papers)
    contents = '\n'.join([source_date.isoformat(), *sorted(ids)])
    return {
        'source_date': source_date.isoformat(),
        'paper_signature': hashlib.sha256(contents.encode('utf-8')).hexdigest(),
        'paper_count': len(ids),
        'categories': sorted(CATEGORIES),
    }


def read_cached_issue(cache_dir):
    if not (cache_dir / ISSUE_FILE).is_file() or not (cache_dir / PAPERS_FILE).is_file():
        raise ValueError(f"缺少源缓存文件 {cache_dir / ISSUE_FILE} 或 {cache_dir / PAPERS_FILE}")
    issue = read_json(cache_dir / ISSUE_FILE)
    papers = read_json(cache_dir / PAPERS_FILE)
    if not isinstance(issue, dict) or not isinstance(issue.get('source_date'), str):
        raise ValueError('源缓存缺少有效公告日期')
    if issue != issue_metadata(parse_date(issue['source_date']), papers):
        raise ValueError('源缓存与公告日期、论文标识符或当前学科配置不符')
    return issue, papers


def legacy_edition(source_date, papers):
    # Existing archives predate the tracker. Reuse the expected edition only
    # when its published paper IDs match the current announcement.
    expected = source_date + timedelta(days=1)
    if expected.isoformat() != latest_existing_edition():
        return None
    report = DOCS / f'daily_{expected}.html'
    soup = BeautifulSoup(report.read_text(encoding='utf-8'), 'html.parser')
    ids = set()
    for link in soup.find_all('a', href=True):
        url = urlsplit(link['href'])
        if url.hostname in {'arxiv.org', 'www.arxiv.org'} and url.path.startswith('/abs/'):
            ids.add(url.path.removeprefix('/abs/'))
    return expected.isoformat() if ids == paper_ids(papers) else None


def latest_existing_edition():
    dates = [match[1] for path in DOCS.glob('daily_*.html')
             if (match := DAILY_FILE.fullmatch(path.name))]
    return max(dates, default='')


def run_script(script, *arguments, raw_dir):
    env = {
        **os.environ,
        'BLUEARXIV_DATA_RAW_DIR': str(raw_dir),
        'PYTHONIOENCODING': f"{sys.stdout.encoding or 'utf-8'}:backslashreplace",
    }
    subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / script), *map(str, arguments)],
        cwd=ROOT,
        env=env,
        check=True,
    )


def check_output(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"缺少本次生成的文件: {path.name}")


def generate_report(raw_dir, docs, edition, source_date, checked_at_args, test_mode):
    run_script('ai_feedback.py', *(['--test-mode'] if test_mode else []), raw_dir=raw_dir)
    run_script('category_filter.py', raw_dir=raw_dir)
    run_script('generate_tex.py', '--date', edition, raw_dir=raw_dir)
    run_script(
        'generate_html.py', '--date', edition, '--source-date', source_date,
        '--output-dir', docs, *checked_at_args, raw_dir=raw_dir,
    )
    tex = raw_dir / 'daily_feedback_tex' / f'daily_feedback_{edition}.tex'
    for path in (tex, docs / 'index.html', docs / f'daily_{edition}.html'):
        check_output(path)
    return tex


def set_output(**values):
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a', encoding='utf-8') as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")


def run(args):
    checked_at_args = []
    if args.cache_dir:
        issue, papers = read_cached_issue(args.cache_dir)
    else:
        source_date, categories = fetch_latest_issue()
        papers = deduplicate_papers(categories)
        issue = issue_metadata(source_date, papers)
        checked_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        if not args.test_mode:
            checked_at_args = ['--checked-at', checked_at]
        if args.cache_output_dir:
            write_json(args.cache_output_dir / ISSUE_FILE, issue)
            write_json(args.cache_output_dir / PAPERS_FILE, papers)
            set_output(cache_ready='true')

    source_date = parse_date(issue['source_date'])
    edition = source_date + timedelta(days=1)
    if args.date and args.date != edition:
        raise ValueError(f"请求的日报日期是 {args.date}，当前源公告对应北京时间 {edition}")
    set_output(report_date=edition, source_date=source_date, paper_count=len(papers))

    previous = {}
    if not args.test_mode and STATE_FILE.is_file():
        previous = read_json(STATE_FILE)
        if not isinstance(previous, dict) or not all(
            isinstance(previous.get(key), str) for key in ('source_date', 'report_date', 'paper_signature')
        ):
            raise ValueError(f"已发布状态无效: {STATE_FILE}")
    if previous and source_date < parse_date(previous['source_date']):
        raise ValueError(f"arXiv 公告 {source_date} 早于已发布的 {previous['source_date']}")

    same_issue = (
        previous.get('paper_signature') == issue['paper_signature']
        and (DOCS / f"daily_{previous['report_date']}.html").is_file()
        and (ROOT / 'latest.tex').is_file()
    )
    existing = None if previous or args.test_mode else legacy_edition(source_date, papers)
    unchanged = not papers or same_issue or existing
    if not args.test_mode and not unchanged:
        same_source = previous.get('source_date') == issue['source_date']
        if edition.isoformat() <= latest_existing_edition() and not same_source:
            raise ValueError(f"日报日期 {edition} 与已有归档冲突")

    with TemporaryDirectory(prefix='bluearxiv-') as temporary:
        tmp = Path(temporary)
        raw_dir = tmp / 'raw'
        docs = tmp / 'docs'
        raw_dir.mkdir()
        if args.test_mode:
            docs.mkdir()
        else:
            shutil.copytree(DOCS, docs)

        if unchanged:
            if args.test_mode:
                raise ValueError('当前源公告没有可用于测试的论文')
            if checked_at_args:
                run_script('generate_html.py', '--index-only', '--output-dir', docs,
                           *checked_at_args, raw_dir=raw_dir)
                check_output(docs / 'index.html')
                shutil.copyfile(docs / 'index.html', DOCS / 'index.html')
            if existing:
                write_json(STATE_FILE, {**issue, 'report_date': existing})
            set_output(result='unchanged')
            print('没有需要重新生成的 arXiv 日报')
            return

        write_json(raw_dir / PAPERS_FILE, papers)
        tex = generate_report(raw_dir, docs, edition, source_date, checked_at_args, args.test_mode)

        if args.artifact_dir:
            shutil.copytree(docs, args.artifact_dir / 'docs', dirs_exist_ok=True)
            shutil.copyfile(tex, args.artifact_dir / tex.name)
            for name in ('all_papers_feedback.json', 'categorized_papers.json'):
                shutil.copyfile(raw_dir / name, args.artifact_dir / name)

        if args.test_mode:
            set_output(result='test')
            print(f"仅生成测试预览，论文数: {min(len(papers), 3)}")
            return

        shutil.copytree(docs, DOCS, dirs_exist_ok=True)
        shutil.copyfile(tex, ROOT / 'latest.tex')
        write_json(STATE_FILE, {**issue, 'report_date': edition.isoformat()})
        set_output(result='generated')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', type=parse_date, help='预期的北京时间日报日期 (YYYY-MM-DD)')
    parser.add_argument('--cache-dir', type=Path, help='从指定目录读取同一次运行的源公告缓存')
    parser.add_argument('--cache-output-dir', type=Path, help='写入本次成功抓取的源公告缓存')
    parser.add_argument('--artifact-dir', type=Path, help='保存本次生成的 TeX、HTML 文件')
    parser.add_argument('--test-mode', action='store_true', help='仅生成少量示例摘要和临时预览')
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError, requests.RequestException, subprocess.CalledProcessError) as exc:
        print(f"日报流程失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
