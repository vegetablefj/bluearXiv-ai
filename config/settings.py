# config/settings.py
import os
from dataclasses import dataclass

@dataclass
class Config:
    # 项目根目录
    PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 数据目录
    DATA_DIR: str = os.path.join(PROJECT_ROOT, 'data')
    DATA_RAW_DIR: str = os.path.join(DATA_DIR, 'raw')
    
    # 模板目录
    TEMPLATES_DIR: str = os.path.join(PROJECT_ROOT, 'templates')
    
    # arXiv配置
    ARXIV_BASE_URL: str = "https://arxiv.org"
    
    # 关注的学科分类 - 从文件读取
    @property
    def CATEGORIES(self):
        """从categories.txt文件读取学科分类"""
        categories_file = os.path.join(self.PROJECT_ROOT, 'config', 'categories.txt')
        categories = {}
        
        try:
            with open(categories_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):  # 忽略空行和注释
                        # 假设每行是学科代码，如 "math.AG"
                        categories[line] = line
        except FileNotFoundError:
            print(f"警告: 分类文件 {categories_file} 不存在，使用默认分类")
            # 如果文件不存在，使用默认分类
            categories = {
                "math.AG": "math.AG",
                "math.RT": "math.RT",
                "math.QA": "math.QA"
            }
        except Exception as e:
            print(f"读取分类文件时出错: {e}")
            # 出错时使用默认分类
            categories = {
                "math.AG": "math.AG",
                "math.RT": "math.RT",
                "math.QA": "math.QA"
            }
        
        return categories
