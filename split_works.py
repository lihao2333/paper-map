#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import re

def split_works(text):
    """将文本拆分成多篇工作"""
    if not text or text.strip() == '':
        return []
    
    # 移除首尾空白
    text = text.strip()
    
    # 按换行符分割
    lines = text.split('\n')
    
    works = []
    current_work = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 判断是否是新工作的开始：
        # 1. 以项目名称+冒号开头（如 "DriveDreamer4D: xxx"）
        # 2. 以大写字母开头的项目名称（如 "PAGS纯重建方案"）
        # 3. 以方括号开头的（如 "[ICCV 2025] Twig"）
        # 4. 如果当前工作为空，则开始新工作
        
        is_new_work = False
        
        # 检查是否以项目名称+冒号开头
        if re.match(r'^[A-Z][a-zA-Z0-9_-]+:', line):
            is_new_work = True
        # 检查是否以方括号开头
        elif line.startswith('['):
            is_new_work = True
        # 检查是否以大写字母开头的项目名称（简单启发式）
        elif re.match(r'^[A-Z][A-Z0-9]+', line) and len(line.split()) <= 3:
            is_new_work = True
        # 如果当前工作为空，开始新工作
        elif not current_work:
            is_new_work = True
        
        if is_new_work and current_work:
            # 保存当前工作
            works.append('\n'.join(current_work).strip())
            current_work = [line]
        else:
            current_work.append(line)
    
    # 添加最后一个工作
    if current_work:
        works.append('\n'.join(current_work).strip())
    
    # 如果没有识别到多篇工作，返回原始文本
    if not works:
        return [text]
    
    return works

def process_csv(input_file, output_file):
    """处理 CSV 文件，将每个 cell 中的多篇工作拆分"""
    rows = []
    
    # 读取原始 CSV
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    
    # 处理数据
    header = rows[0]
    new_rows = [header]  # 保留表头
    
    for row_idx, row in enumerate(rows[1:], start=1):
        time_col = row[0] if row else ''
        
        # 为每个 cell 拆分工作
        cell_works = []
        for col_idx, cell in enumerate(row[1:], start=1):
            works = split_works(cell)
            cell_works.append(works)
        
        # 找到每个 cell 中工作的最大数量
        max_works = max(len(works) for works in cell_works) if cell_works else 0
        
        # 为每篇工作创建一行
        for work_idx in range(max_works):
            new_row = [time_col]
            for works in cell_works:
                if work_idx < len(works):
                    new_row.append(works[work_idx])
                else:
                    new_row.append('')
            new_rows.append(new_row)
    
    # 写入新 CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)
    
    print(f"处理完成！已生成新文件: {output_file}")
    print(f"原始行数: {len(rows)}, 新行数: {len(new_rows)}")

if __name__ == '__main__':
    input_file = 'competitor_research.csv'
    output_file = 'competitor_research_split.csv'
    process_csv(input_file, output_file)

