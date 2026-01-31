# bluearXiv-ai

自动抓取、分析和生成 arXiv 数学论文日报的系统。

## 功能特性

1. **自动抓取** - 从 arXiv 获取最新的数学论文
2. **AI 分析** - 使用 AI 模型分析论文并生成中文摘要
3. **分类过滤** - 按学科分类并筛选重要论文
4. **自动生成** - 生成 LaTeX 格式的日报文档
5. **自动编译** - 编译 LaTeX 为 PDF 文档（由于中文编译的问题，目前暂未能实现）

## 自动运行

系统已配置GitHub Actions工作流，每天自动运行：
- 北京时间 12:00 (UTC 04:00)

### 手动触发
在GitHub仓库的Actions页面可以手动触发运行。

## 配置文件

### keywords.txt
在`config/keywords.txt`中添加每行一个关键词，用于AI筛选论文。

## 输出文件

处理完成后会生成：
- `latest.tex` - 最新的LaTeX文档
- `latest.pdf` - 编译后的PDF日报
- `data/raw/daily_feedback_YYYY-MM-DD.pdf` - 带日期的PDF备份
- 各种中间JSON数据文件

## GitHub Actions配置

在仓库设置中添加Secrets：
- `DEEPSEEK_API_KEY`: DeepSeek API密钥
- `MODEL_SCOPE_API_KEY`: ModelScope API密钥
