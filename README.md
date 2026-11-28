# bluearXiv

自动跟踪 arXiv 指定学科的论文，生成中文摘要和关键词精选日报。

## 核心功能

- **自动抓取**：工作日从 arXiv 获取最新公告，同一批论文只发布一期。
- **中文摘要与精选**：AI 根据 arXiv 原摘要译写中文摘要，并按跟踪关键词的相关性筛选论文。
- **多格式输出**：自动生成结构化的 LaTeX (`latest.tex`) 和 HTML 网页 (`docs/`)。
- **自动部署**：通过 GitHub Actions 工作流，每日自动运行并将生成的网页部署至 GitHub Pages。

## 自动运行与部署

系统通过 GitHub Actions 实现全自动化流程：
- **定时触发**：周一至周五 UTC 04:00（北京时间 12:00）检查最新公告。没有新一期时，首页更新最近成功检查时间。
- **手动触发**：在 GitHub Actions 中可通过 `date` 核对目标日报日期（北京时间，`YYYY-MM-DD`）。实时抓取使用 arXiv 最新公告。
- **测试和复用**：`test_mode` 用示例中文摘要生成最多三篇论文的测试产物，仅供下载预览。勾选 `skip_fetch` 时填写 `source_run_id`，复用本仓库七天内的 `arxiv-source` 产物。正式发布接受当前或更新的公告批次。
- **网页部署**：成功生成的 HTML 通过仓库的 GitHub Pages 发布。

## 本地网页预览

在仓库根目录运行 `python -m http.server 8765 --bind 127.0.0.1 --directory docs`，然后访问 [本地首页](http://localhost:8765/)。现有日报可以直接预览。只重建归档首页时运行 `python scripts/generate_html.py --index-only`。

## 输出文件

运行成功后，您将获得：
- **LaTeX 文档**：仓库中的 `latest.tex` 为最新一期，单次运行的 TeX 文件也包含在 GitHub Actions 产物中。
- **网页报告**：`docs/index.html`（导航页）与 `docs/daily_YYYY-MM-DD.html`（每日详情），可通过 GitHub Pages 访问。
- **中间数据**：`data/raw/` 目录下的各类 JSON 数据文件。

## 配置说明

1.  **学科与关键词**：
    - 在 `config/categories.txt` 中定义跟踪的学科类别（每行一个）。
    - 在 `config/keywords.txt` 中添加筛选关键词（每行一个）。

2.  **API 密钥**（用于 GitHub Actions）：
    在仓库设置中添加以下 Secrets：
    - `DEEPSEEK_API_KEY`
    - `MODEL_SCOPE_API_KEY`
    - 目前仅支持使用DeepSeek API
