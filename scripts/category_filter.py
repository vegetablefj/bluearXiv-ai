import sys
import os
import json
from collections import defaultdict
from typing import List, Dict

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 从现有的config模块导入配置
from config.loader import load_config
from config.settings import Config

# 加载配置
config = load_config()
DATA_RAW_DIR = config.DATA_RAW_DIR
CATEGORIES = config.CATEGORIES

def categorize_papers(papers):
    """将论文按照主学科分类"""
    categorized = defaultdict(list)
    
    # 为每个特殊学科创建空列表
    for category in CATEGORIES.keys():
        categorized[category] = []
    
    # 添加others类别
    categorized["others"] = []
    
    # 分类论文
    for paper in papers:
        paper_categories = paper.get('categories', [])
        
        # 获取论文的主学科（第一个学科）
        primary_category = paper_categories[0] if paper_categories else None
        
        # 如果主学科是特殊学科，放入对应列表
        if primary_category in CATEGORIES:
            categorized[primary_category].append(paper)
        else:
            # 否则放入others
            categorized["others"].append(paper)
    
    return categorized

def main():
    """主函数：加载已有反馈的论文并按照主学科分类"""
    print("开始加载已有反馈的论文并分类...")
    print("=" * 50)
    
    # 加载已有反馈的论文数据
    input_file = os.path.join(DATA_RAW_DIR, "all_papers_feedback.json")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            papers = json.load(f)
        print(f"成功加载 {len(papers)} 篇已有反馈的论文")
    except FileNotFoundError:
        print(f"错误: 输入文件 {input_file} 不存在")
        print("请先运行 ai_feedback.py 生成论文反馈数据")
        return
    except Exception as e:
        print(f"加载论文数据时出错: {e}")
        return
    
    # 统计精选论文数量
    selected_count = sum(1 for paper in papers if paper.get('selected', False))
    
    # 按照主学科分类论文
    categorized_papers = categorize_papers(papers)
    
    # 保存结果
    output_file = os.path.join(DATA_RAW_DIR, "categorized_papers.json")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(categorized_papers, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 分类论文数据已保存到: {output_file}")
        
        # 显示分类统计
        print("\n分类统计:")
        total_papers = 0
        for category, papers_in_category in categorized_papers.items():
            # 统计每个分类中的精选论文数量
            selected_in_category = sum(1 for paper in papers_in_category if paper.get('selected', False))
            print(f"- {category}: {len(papers_in_category)} 篇论文 (其中精选: {selected_in_category} 篇)")
            total_papers += len(papers_in_category)
        
        print(f"\n总计: {total_papers} 篇论文")
        print(f"标记为精选的论文: {selected_count}/{len(papers)}")
        
    except Exception as e:
        print(f"保存分类数据时出错: {e}")

if __name__ == "__main__":
    main()
