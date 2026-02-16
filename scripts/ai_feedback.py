import os
import sys
import json
import openai
from typing import List, Dict, Tuple
import time
import math

# 获取项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 从环境变量读取模型名称，如果没有则使用默认值
MODEL_NAME = os.getenv('AI_MODEL_NAME', 'Qwen/Qwen3-8B')

def get_file_paths():
    """获取所有必要的文件路径"""
    root = project_root
    
    paths = {
        'json_input': os.path.join(root, 'data', 'raw', 'all_papers_unique.json'),
        'keywords': os.path.join(root, 'config', 'keywords.txt'),
        'json_output': os.path.join(root, 'data', 'raw', 'all_papers_feedback.json'),
        'progress_dir': os.path.join(root, 'scripts', 'temp_progress')
    }
    
    return paths

def load_keywords(keywords_path: str) -> List[str]:
    """从文本文件加载关键词，每行一个关键词"""
    try:
        with open(keywords_path, 'r', encoding='utf-8') as f:
            keywords = [line.strip() for line in f if line.strip()]
        
        print(f"从 {keywords_path} 加载了 {len(keywords)} 个关键词")
        return keywords
        
    except FileNotFoundError:
        print(f"警告: 关键词文件未找到 - {keywords_path}")
        return [
            "moduli space",
            "Conlumb branch",
            "Hodge theory"
        ]
    except Exception as e:
        print(f"加载关键词错误: {e}")
        return []

def load_papers_from_json(file_path: str) -> List[Dict]:
    """从JSON文件加载论文数据
    
    假设文件包含论文字典列表，每个字典有id, title, authors, categories, abstract等字段
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            papers = json.load(f)
        
        if not isinstance(papers, list):
            raise ValueError("JSON文件应包含论文列表")
        
        print(f"成功加载 {len(papers)} 篇论文")
        return papers
            
    except Exception as e:
        print(f"加载论文数据错误: {e}")
        return []

def process_all_papers(batch_size: int = 5) -> Tuple[List[Dict], int]:
    """
    处理所有论文内容总结功能 - 分批处理所有论文
    
    Args:
        batch_size: 每批处理的论文数量（默认5篇）
        
    Returns:
        papers_with_feedback: 添加了'selected'和'comment'的论文列表
        selected_count: 被精选的论文数量
    """
    # 获取文件路径
    paths = get_file_paths()
    
    # 加载论文数据
    print(f"正在加载论文数据从: {paths['json_input']}")
    all_papers = load_papers_from_json(paths['json_input'])
    
    if not all_papers:
        print("错误: 无法加载论文数据")
        return [], 0
    
    print(f"成功加载 {len(all_papers)} 篇论文")
    
    # 加载关键词
    keywords = load_keywords(paths['keywords'])
    
    if not keywords:
        print("警告: 没有加载到关键词，使用默认关键词")
        keywords = ["moduli space", "Conlumb branch", "Hodge theory"]
    
    print(f"使用关键词: {', '.join(keywords)}")
    print(f"开始处理所有 {len(all_papers)} 篇论文...\n")
    
    # 创建进度文件目录
    if not os.path.exists(paths['progress_dir']):
        os.makedirs(paths['progress_dir'])
        print(f"创建进度目录: {paths['progress_dir']}")

    # 计算总批次数
    total_batches = math.ceil(len(all_papers) / batch_size)
    print(f"将分 {total_batches} 批处理，每批 {batch_size} 篇论文")
    
    # 初始化客户端
    
    deepseek_key = os.environ.get('DEEPSEEK_API_KEY')
    modelscope_key = os.environ.get('MODEL_SCOPE_API_KEY')
    
    client = openai.OpenAI(
        api_key=modelscope_key,  # 替换为你的API密钥
        base_url="https://api-inference.modelscope.cn/v1/"
    )
    
    # 系统提示
    system_prompt = """你是一位严格的数学学术专家。请用中文（数学名词术语保持英文！！！使用英文标点符号！！）为每篇论文生成内容总结。

## 输出格式（对每篇论文）：
第一行：0 或 1
第二行开始：总结（中文！！！数学名词术语保持英文！！！使用英文标点符号！！！）

## 精选标准较为严格，只对以下论文标1：
1. 方法具有一定的开创性
2. 解决了该领域长期存在的问题
3. 与我提供的关键词中的某个较为契合

## 总结撰写规则：
- 如果标1：在同一段内给出详细概括（3-4句）
- 如果标0：保持简洁概括，甚至可以模糊（2句左右）
- 对于一些可能不那么常见的概念，可以用括号在名词后面进行一定的解释，如果做不到完全严谨可以略有模糊

## 内容要求：
0. 简洁一些，不要照搬摘要！！！
1. 使用中文！！！注意斟酌术语翻译！！！注意斟酌术语翻译！！！
2. 使用英文标点符号！！！
3. 数学公式用$...$包裹，严格确保公式部分可以直接被latex中常用的数学包编译。这一点很重要！
4. 大致格式，不需要完全严格遵循：本文用[工具/方法]证明了[结果]，为[问题]提供了[贡献]
5. 不要解释评分原因，直接给出判断
"""
    
    selected_count = 0
    processed_count = 0
    
    # 分批处理所有论文
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min((batch_num + 1) * batch_size, len(all_papers))
        current_batch = all_papers[start_idx:end_idx]
        
        print(f"\n{'='*60}")
        print(f"处理批次 {batch_num+1}/{total_batches} (论文 {start_idx+1}-{end_idx})")
        print(f"{'='*60}")
        
        batch_selected_count = 0
        
        for i, paper in enumerate(current_batch, 1):
            paper_global_idx = start_idx + i
            print(f"\n--- 论文 {paper_global_idx}/{len(all_papers)} ---")
            
            # 提取论文信息
            title = paper.get('title', 'N/A')
            authors = paper.get('authors', [])
            categories = paper.get('categories', [])
            abstract = paper.get('abstract', '')
            
            print(f"标题: {title}")
            print(f"作者: {', '.join(authors) if authors else 'N/A'}")
            print(f"分类: {', '.join(categories) if categories else 'N/A'}")
            print(f"摘要: {abstract[:200]}...")
            
            # 构建用户提示
            user_prompt = f"""请总结以下数学论文：

标题: {title}
作者: {', '.join(authors) if authors else 'N/A'}
分类: {', '.join(categories) if categories else 'N/A'}
摘要: {abstract}

我的关键词列表：{", ".join(keywords)}

请按以下格式输出总结：
[0或1]
[总结内容]
"""
            
            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # 调用API
            try:
                print("调用API生成总结...")
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=300,
                    timeout=30
                )
                
                # 解析响应
                result = response.choices[0].message.content.strip()
                lines = [line.strip() for line in result.split('\n') if line.strip()]
                
                if len(lines) >= 2:
                    selected = lines[0] == '1'
                    comment = '\n'.join(lines[1:]).strip()
                    
                    if selected:
                        selected_count += 1
                        batch_selected_count += 1
                        print("✅ 精选论文")
                    else:
                        print("◯◯ 普通论文")
                    
                    print(f"总结:\n{comment}")
                    
                    # 添加到论文数据中
                    paper['selected'] = selected
                    paper['comment'] = comment
                    
                else:
                    print("❌❌ 响应格式错误")
                    paper['selected'] = False
                    paper['comment'] = "API响应格式错误"
                
                # 显示token使用情况
                if hasattr(response, 'usage'):
                    usage = response.usage
                    print(f"Token使用: 输入={usage.prompt_tokens}, 输出={usage.completion_tokens}, 总计={usage.total_tokens}")
                
                processed_count += 1
                
            except Exception as e:
                print(f"❌❌ API调用错误: {e}")
                paper['selected'] = False
                paper['comment'] = f"API错误: {str(e)}"
                processed_count += 1
            
            # 请求间延迟，避免速率限制
            if i < len(current_batch):
                time.sleep(1)
        
        # 批次处理完成统计
        print(f"\n批次 {batch_num+1} 完成: 处理了 {len(current_batch)} 篇论文，其中 {batch_selected_count} 篇精选")
        
        # 保存当前进度（每批完成后保存）
        progress_file = os.path.join(paths['progress_dir'], f"processing_progress_batch_{batch_num+1}.json")
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump({
                "batch": batch_num + 1,
                "total_batches": total_batches,
                "processed_so_far": processed_count,
                "selected_so_far": selected_count,
                "papers_processed": all_papers[:processed_count]
            }, f, ensure_ascii=False, indent=2)
        
        print(f"进度已保存到: {progress_file}")
        
        # 批次间延迟
        if batch_num < total_batches - 1:
            print(f"等待3秒后处理下一批...")
            time.sleep(3)
    
    # 输出最终统计信息
    print(f"\n{'='*60}")
    print("所有论文处理完成!")
    print(f"{'='*60}")
    print(f"总论文数: {len(all_papers)}")
    print(f"已处理论文数: {processed_count}")
    print(f"精选论文数: {selected_count}")
    print(f"精选比例: {selected_count/len(all_papers):.1%}" if len(all_papers) > 0 else "0%")
    
    # 显示精选论文
    if selected_count > 0:
        print(f"\n精选论文列表:")
        for i, paper in enumerate(all_papers, 1):
            if paper.get('selected', False):
                print(f"{i}. {paper.get('title', 'N/A')}")
    
    # 保存最终结果 - 只保存论文列表，不添加额外元数据
    try:
        with open(paths['json_output'], 'w', encoding='utf-8') as f:
            json.dump(all_papers, f, ensure_ascii=False, indent=2)
        
        print(f"\n完整结果已保存到: {paths['json_output']}")
        print(f"结果文件包含 {len(all_papers)} 篇论文，每篇都有 'selected' 和 'comment' 字段")
        
    except Exception as e:
        print(f"保存结果文件错误: {e}")
    
    return all_papers, selected_count

if __name__ == "__main__":
    # 处理所有论文，每批5篇
    papers_with_feedback, selected_count = process_all_papers(batch_size=5)
    
    if papers_with_feedback:
        print(f"\n处理完成！")
        print(f"总论文数: {len(papers_with_feedback)}")
        print(f"精选论文数: {selected_count}")
        print(f"精选比例: {selected_count/len(papers_with_feedback):.1%}")
        
        # 显示前几篇精选论文
        print(f"\n前5篇精选论文:")
        count = 0
        for paper in papers_with_feedback:
            if paper.get('selected', False):
                print(f"- {paper.get('title', 'N/A')}")
                count += 1
                if count >= 5:
                    break
    else:
        print("处理失败，没有生成结果")
