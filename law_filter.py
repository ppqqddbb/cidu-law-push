# -*- coding: utf-8 -*-
"""
法律信息过滤器 - 使用 Dify 大模型对爬取结果进行分类过滤
"""

import json
import logging
import requests
from config import DIFY_API_URL, DIFY_API_KEY, LAW_OUTPUT_FILE, CASE_OUTPUT_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class LawFilter:
    def __init__(self):
        self.api_url = DIFY_API_URL
        self.api_key = DIFY_API_KEY
        
    def classify_content(self, title, content=""):
        """
        使用 Dify 大模型对内容进行分类
        返回: 'law' (法律条文) 或 'case' (法律案例) 或 'other' (其他)
        """
        prompt = f"""请判断以下法律相关内容属于哪种类型：

标题：{title}
内容：{content if content else '无'}

类型分类：
- law: 法律条文、法规、规章、司法解释、规范性文件等
- case: 法律案例、裁判文书、典型案例、判决结果等
- other: 其他（如新闻报道、政策解读、普法宣传等）

请只返回类型标识（law/case/other），不要返回其他内容。"""

        try:
            # 调用 Dify API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "inputs": {},
                "query": prompt,
                "response_mode": "blocking",
                "user": "law-crawler"
            }
            
            response = requests.post(
                f"{self.api_url}/chat-messages",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("answer", "").strip().lower()
                
                # 解析返回结果
                if "law" in answer and "case" not in answer:
                    return "law"
                elif "case" in answer:
                    return "case"
                else:
                    return "other"
            else:
                logger.warning(f"Dify API 调用失败: {response.status_code} - {response.text}")
                return "other"
                
        except Exception as e:
            logger.warning(f"Dify API 调用异常: {e}")
            return "other"
    
    def filter_results(self, input_file, law_output=None, case_output=None):
        """
        过滤爬取结果，分类输出到不同文件
        """
        law_output = law_output or LAW_OUTPUT_FILE
        case_output = case_output or CASE_OUTPUT_FILE
        
        # 读取输入文件
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            logger.error(f"输入文件不存在: {input_file}")
            return False
        
        # 解析结果
        results = []
        current_item = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                # 空行表示一个条目结束
                if current_item and 'title' in current_item:
                    results.append(current_item)
                    current_item = {}
                continue
            
            # 跳过文件头部信息
            if line.startswith("法律信息爬取结果"):
                continue
            elif line.startswith("时间范围:"):
                continue
            elif line.startswith("爬取时间:"):
                continue
            elif line.startswith("共"):
                continue
            elif line.startswith("=" * 20):
                continue
            
            # 解析条目内容
            if line.startswith("来源："):
                # 格式：来源：xxx｜日期：xxx
                parts = line[3:].split("｜")
                if len(parts) == 2:
                    current_item["source"] = parts[0].strip()
                    date_part = parts[1].strip()
                    if date_part.startswith("日期："):
                        current_item["date"] = date_part[3:]
            elif line.startswith("链接："):
                current_item["url"] = line[3:]
            elif line.startswith("摘要："):
                current_item["summary"] = line[3:]
            else:
                # 其他行视为标题
                if 'title' not in current_item:
                    current_item["title"] = line
        
        # 添加最后一个条目
        if current_item and 'title' in current_item:
            results.append(current_item)
        
        logger.info(f"读取到 {len(results)} 条记录")
        
        # 分类过滤
        law_items = []
        case_items = []
        other_items = []
        
        for i, item in enumerate(results):
            logger.info(f"正在分类第 {i+1}/{len(results)} 条: {item.get('title', '')[:50]}")
            
            title = item.get("title", "")
            summary = item.get("summary", "")
            
            category = self.classify_content(title, summary)
            
            if category == "law":
                law_items.append(item)
            elif category == "case":
                case_items.append(item)
            else:
                other_items.append(item)
        
        logger.info(f"分类结果: 法律条文 {len(law_items)} 条, 法律案例 {len(case_items)} 条, 其他 {len(other_items)} 条")
        
        # 写入法律条文文件
        self._write_output(law_output, law_items, "法律条文")
        
        # 写入法律案例文件
        self._write_output(case_output, case_items, "法律案例")
        
        return True
    
    def _write_output(self, output_file, items, category_name):
        """写入分类结果到文件"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{category_name}过滤结果\n")
                f.write(f"共 {len(items)} 条\n")
                f.write("=" * 60 + "\n\n")
                
                for item in items:
                    f.write(f"标题：{item.get('title', '')}\n")
                    f.write(f"来源：{item.get('source', '')}\n")
                    f.write(f"日期：{item.get('date', '')}\n")
                    f.write(f"链接：{item.get('url', '')}\n")
                    if item.get('summary'):
                        f.write(f"摘要：{item.get('summary', '')}\n")
                    f.write("\n")
            
            logger.info(f"{category_name}结果已保存到: {output_file}")
        except Exception as e:
            logger.error(f"写入文件失败 {output_file}: {e}")


def main():
    """测试过滤功能"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python law_filter.py <输入文件>")
        print("示例: python law_filter.py result.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    filter_instance = LawFilter()
    filter_instance.filter_results(input_file)


if __name__ == "__main__":
    main()
