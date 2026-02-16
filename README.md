# bluearXiv-ai

自动抓取、分析 arXiv 特定领域论文，并生成日报的系统。

## 核心功能

- **自动抓取**：每日从 arXiv 获取最新的论文信息。
- **AI 分析**：使用 AI 模型分析论文摘要，生成评论与精选推荐。
- **多格式输出**：自动生成结构化的 LaTeX (`latest.tex`) 和 HTML 网页 (`docs/`)。
- **自动部署**：通过 GitHub Actions 工作流，每日自动运行并将生成的网页部署至 GitHub Pages。

## 自动运行与部署

系统通过 GitHub Actions 实现全自动化流程：
- **定时触发**：每天 UTC 时间 04:00（北京时间 12:00）自动运行。
- **手动触发**：可在 GitHub 仓库的 Actions 页面手动启动工作流。
- **网页部署**：处理完成后，生成的 HTML 报告会自动发布到 `https://<用户名>.github.io/bluearXiv-ai/`。

## 输出文件

运行成功后，您将获得：
- **LaTeX 文档**：`latest.tex`（最新）与 `data/raw/daily_feedback_tex/daily_feedback_YYYY-MM-DD.tex`（历史存档）。
- **网页报告**：`docs/index.html`（导航页）与 `docs/daily_YYYY-MM-DD.html`（每日详情），可通过 GitHub Pages 访问。
- **中间数据**：`data/raw/` 目录下的各类 JSON 数据文件。

## 配置说明

1.  **学科与关键词**：
    - 在 `config/categories.txt` 中定义跟踪的学科类别。
    - 在 `config/keywords.txt` 中添加筛选关键词（每行一个）。

2.  **API 密钥**（用于 GitHub Actions）：
    在仓库设置中添加以下 Secrets：
    - `DEEPSEEK_API_KEY`
    - `MODEL_SCOPE_API_KEY`