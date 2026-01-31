#!/usr/bin/env python3
"""
xelatex_compile.py
自动编译LaTeX文件，生成PDF并管理文件
"""

import re
import os
import sys
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
import argparse
import logging

log_dir = Path("log")
log_dir.mkdir(exist_ok=True)

date_str = datetime.now().strftime("%Y-%m-%d")
script_name = Path(__file__).stem
log_file = log_dir / f"{date_str}.log"

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding='utf-8')  # 输出到log文件夹中的文件
    ]
)
logger = logging.getLogger(__name__)

def get_project_paths():
    """获取项目路径"""
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    # 项目根目录是脚本目录的父目录
    project_root = script_dir.parent
    
    paths = {
        'project_root': project_root,
        'scripts_dir': script_dir,
        'data_raw_daily_feedback_pdf': project_root / 'data' / 'raw' / 'daily_feedback_pdf',
        'templates_dir': project_root / 'templates',
        'main_tex': project_root / 'latest.tex',
        'output_pdf_latest': project_root / 'latest.pdf'
    }
    
    return paths

def check_dependencies():
    """检查系统依赖"""
    required_commands = ['xelatex', 'latexmk']
    
    missing_commands = []
    for cmd in required_commands:
        try:
            subprocess.run([cmd, '--version'],
                         capture_output=True,
                         check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing_commands.append(cmd)
    
    if missing_commands:
        logger.error(f"缺少必要的LaTeX命令: {', '.join(missing_commands)}")
        logger.info("请安装完整的LaTeX发行版:")
        logger.info("  - Ubuntu/Debian: sudo apt-get install texlive-xetex texlive-latex-extra")
        logger.info("  - macOS: 安装MacTeX")
        logger.info("  - Windows: 安装MikTeX或TeX Live")
        return False
    
    logger.info("✓ 所有依赖检查通过")
    return True

def check_latex_syntax(tex_file):
    """
    检查LaTeX文件的基本语法
    """
    if not tex_file.exists():
        logger.error(f"TeX文件不存在: {tex_file}")
        return False
    
    try:
        with open(tex_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查常见的LaTeX语法问题
        problems = []
        
        # 检查是否以\documentclass开头
        if not re.search(r'\\documentclass', content):
            problems.append("未找到 \\documentclass 声明")
        
        # 检查是否以\begin{document}和\end{document}包围
        if content.find(r'\begin{document}') == -1:
            problems.append("未找到 \\begin{document}")
        
        if content.find(r'\end{document}') == -1:
            problems.append("未找到 \\end{document}")
        
        # 检查不匹配的大括号
        open_braces = content.count('{')
        close_braces = content.count('}')
        if open_braces != close_braces:
            problems.append(f"大括号不匹配: 开启{{{open_braces}}} 个, 关闭{{{close_braces}}} 个")
        
        # 检查不匹配的$
        dollar_count = content.count('$')
        if dollar_count % 2 != 0:
            problems.append(f"数学模式$符号不匹配: 共{dollar_count}个")
        
        if problems:
            logger.warning("LaTeX语法检查发现问题:")
            for problem in problems:
                logger.warning(f"  - {problem}")
            return False
        else:
            logger.info("✓ LaTeX语法检查通过")
            return True
            
    except Exception as e:
        logger.error(f"语法检查时发生错误: {e}")
        return False

def compile_with_latexmk(tex_file, engine='xelatex'):
    """
    使用latexmk编译LaTeX文件（推荐），但显示详细错误信息
    
    Args:
        tex_file: .tex文件路径
        engine: 编译引擎
    
    Returns:
        tuple: (成功与否, 生成的PDF路径)
    """
    if not tex_file.exists():
        logger.error(f"TeX文件不存在: {tex_file}")
        return False, None
    
    try:
        # 构建latexmk命令，去掉-silent以获取详细错误信息
        cmd = [
            'latexmk',
            f'-{engine}',
            '-interaction=nonstopmode',
            # '-silent',  # 注释掉这一行以获取详细输出
            '-pdf',     # 生成PDF
            str(tex_file)
        ]
        
        logger.info(f"使用latexmk编译: {tex_file.name}")
        logger.info(f"命令: {' '.join(cmd)}")
        
        # 执行编译命令，捕获所有输出
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            # 不设置check=True，这样我们可以自己处理错误
        )
        
        # 记录所有输出
        if result.stdout:
            logger.info("编译标准输出:")
            logger.info(result.stdout)
        
        if result.stderr:
            logger.error("编译标准错误:")
            logger.error(result.stderr)
        
        # 检查PDF文件
        pdf_path = tex_file.with_suffix('.pdf')
        if pdf_path.exists():
            pdf_size = pdf_path.stat().st_size
            logger.info(f"✓ PDF文件生成成功: {pdf_path}")
            logger.info(f"文件大小: {pdf_size} 字节")
            return True, pdf_path
        else:
            logger.error("❌ PDF文件未生成")
            
            # 如果编译失败，尝试更基本的命令
            logger.info("尝试使用直接xelatex编译...")
            return compile_with_xelatex_direct(tex_file)
            
    except subprocess.TimeoutExpired:
        logger.error("❌ 编译超时")
        return False, None
    except Exception as e:
        logger.error(f"编译过程中发生未知错误: {e}")
        return False, None

def compile_with_xelatex_direct(tex_file, compile_times=2):
    """
    直接使用xelatex编译，提供更详细的错误信息
    """
    if not tex_file.exists():
        logger.error(f"TeX文件不存在: {tex_file}")
        return False, None
    
    original_cwd = os.getcwd()
    tex_dir = tex_file.parent
    
    try:
        os.chdir(tex_dir)
        tex_filename = tex_file.name
        
        logger.info("=" * 50)
        logger.info("使用直接xelatex编译获取详细错误信息")
        logger.info("=" * 50)
        
        # 编译多次以确保引用正确
        for i in range(compile_times):
            logger.info(f"第 {i+1}/{compile_times} 次编译...")
            
            cmd = [
                'xelatex',
                '-interaction=nonstopmode',
                '-shell-escape',
                tex_filename
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            logger.info(f"编译返回码: {result.returncode}")
            
            if result.stdout:
                logger.info("标准输出:")
                # 只显示最后100行输出，避免日志过大
                lines = result.stdout.strip().split('\n')
                for line in lines[-100:]:
                    logger.info(line)
            
            if result.stderr:
                logger.error("标准错误:")
                lines = result.stderr.strip().split('\n')
                for line in lines[-50:]:
                    logger.error(line)
            
            if result.returncode != 0:
                logger.error(f"第 {i+1} 次编译失败")
                # 但仍然继续下一次编译
        
        # 检查PDF文件
        pdf_path = tex_file.with_suffix('.pdf')
        if pdf_path.exists():
            pdf_size = pdf_path.stat().st_size
            logger.info(f"✓ PDF文件生成成功: {pdf_path}")
            logger.info(f"文件大小: {pdf_size} 字节")
            return True, pdf_path
        else:
            logger.error("❌ PDF文件未生成")
            return False, None
            
    except Exception as e:
        logger.error(f"直接编译过程中发生错误: {e}")
        return False, None
    finally:
        os.chdir(original_cwd)

def clean_intermediate_files(tex_file):
    """
    清理LaTeX编译中间文件
    
    Args:
        tex_file: .tex文件路径
    """
    base_name = tex_file.stem
    tex_dir = tex_file.parent
    
    # LaTeX中间文件扩展名
    intermediate_extensions = [
        '.aux', '.log', '.out', '.toc', '.lof', '.lot',
        '.bbl', '.blg', '.nav', '.snm', '.vrb', '.synctex.gz',
        '.fdb_latexmk', '.fls', '.xdv'
    ]
    
    cleaned_count = 0
    for ext in intermediate_extensions:
        file_path = tex_dir / (base_name + ext)
        if file_path.exists():
            try:
                file_path.unlink()
                cleaned_count += 1
                logger.debug(f"清理文件: {file_path.name}")
            except Exception as e:
                logger.warning(f"无法删除文件 {file_path}: {e}")
    
    if cleaned_count > 0:
        logger.info(f"✓ 清理了 {cleaned_count} 个中间文件")
    else:
        logger.info("没有找到需要清理的中间文件")

def copy_pdf_to_destination(pdf_file, dest_path):
    """
    复制PDF文件到目标位置
    
    Args:
        pdf_file: 源PDF文件路径
        dest_path: 目标路径
    
    Returns:
        bool: 复制是否成功
    """
    try:
        # 确保目标目录存在
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 复制文件
        shutil.copy2(pdf_file, dest_path)
        logger.info(f"✓ PDF文件已复制到: {dest_path}")
        return True
    except Exception as e:
        logger.error(f"❌ 复制PDF文件失败: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='自动编译LaTeX文件')
    parser.add_argument('--tex-file', help='要编译的TeX文件路径')
    parser.add_argument('--use-latexmk', action='store_true',
                       help='使用latexmk代替xelatex（推荐）')
    parser.add_argument('--no-clean', action='store_true',
                       help='不清理中间文件')
    parser.add_argument('--keep-all', action='store_true',
                       help='保留所有PDF副本')
    
    args = parser.parse_args()
    
    # 获取路径
    paths = get_project_paths()
    
    logger.info("=" * 50)
    logger.info("开始LaTeX自动编译流程")
    logger.info("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
        
    # 确定要编译的TeX文件
    if args.tex_file:
        tex_file = Path(args.tex_file)
        if not tex_file.exists():
            logger.error(f"指定的TeX文件不存在: {tex_file}")
            return 1
    else:
        tex_file = paths['main_tex']
        if not tex_file.exists():
            logger.error(f"默认TeX文件不存在: {tex_file}")
            logger.info("请指定要编译的TeX文件: python xelatex_compile.py --tex-file path/to/file.tex")
            return 1
            
    # 检查LaTeX语法
    logger.info("检查LaTeX文件语法...")
    if not check_latex_syntax(tex_file):
        logger.warning("LaTeX文件可能存在语法问题，继续尝试编译...")
    
    # 编译LaTeX文件
    if args.use_latexmk:
        success, pdf_path = compile_with_latexmk(tex_file, engine='xelatex')
    else:
        success, pdf_path = compile_with_xelatex(tex_file)
    
    
    # 清理中间文件
    if not args.no_clean:
        clean_intermediate_files(tex_file)
    
    # 复制PDF文件到目标位置
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. 复制到主文件夹作为latest.pdf
    latest_pdf_path = paths['output_pdf_latest']
    copy_success_1 = copy_pdf_to_destination(pdf_path, latest_pdf_path)
    
    # 2. 复制到data/raw作为带日期的文件
    dated_pdf_path = paths['data_raw_daily_feedback_pdf'] / f"daily_feedback_{date_str}.pdf"
    copy_success_2 = copy_pdf_to_destination(pdf_path, dated_pdf_path)
    
    # 3. 如果需要保留所有副本，再复制一份带时间戳的
    if args.keep_all:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_pdf_path = paths['data_raw_daily_feedback_pdf'] / f"daily_feedback_{timestamp_str}.pdf"
        copy_pdf_to_destination(pdf_path, timestamp_pdf_path)
    
    # 输出总结
    logger.info("=" * 50)
    logger.info("编译流程完成")
    logger.info("=" * 50)
    
    if copy_success_1:
        logger.info(f"✓ 最新PDF: {latest_pdf_path}")
    
    if copy_success_2:
        logger.info(f"✓ 日期PDF: {dated_pdf_path}")
    
    logger.info("✓ 所有操作完成")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"未处理的异常: {e}")
        sys.exit(1)
