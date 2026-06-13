# 教材提取知识点流程优化方案

## 一、提取逻辑优化

### 1.1 改进标题识别算法
```python
# 当前问题：简单的正则匹配容易误判
# 优化方案：结合多种特征进行判断

def improved_heading_score(line: str, context: dict) -> float:
    """
    改进的标题评分函数
    考虑因素：
    1. 格式特征（正则匹配）
    2. 位置特征（是否在页面顶部）
    3. 长度特征（标题通常较短）
    4. 上下文特征（前后文本关系）
    """
    score = 0.0
    s = line.strip()
    
    if not s or len(s) > 100:  # 放宽长度限制
        return 0.0
    
    # 1. 格式特征
    format_score = calculate_format_score(s)
    
    # 2. 位置特征
    position_score = calculate_position_score(context)
    
    # 3. 长度特征
    length_score = calculate_length_score(s)
    
    # 4. 上下文特征
    context_score = calculate_context_score(s, context)
    
    # 综合评分
    score = (format_score * 0.4 + 
             position_score * 0.2 + 
             length_score * 0.2 + 
             context_score * 0.2)
    
    return score
```

### 1.2 改进知识点分类
```python
# 当前问题：简单的关键词匹配
# 优化方案：使用机器学习模型或更复杂的规则

def improved_classify_type(title: str, content: str = "") -> str:
    """
    改进的知识点分类函数
    考虑因素：
    1. 标题关键词
    2. 内容特征
    3. 上下文关系
    """
    # 1. 关键词匹配（保留现有逻辑）
    keyword_type = classify_by_keywords(title)
    
    # 2. 内容特征分析
    content_type = analyze_content_features(content) if content else None
    
    # 3. 上下文关系分析
    context_type = analyze_context_relationship(title, content)
    
    # 4. 综合判断
    return resolve_type_conflict(keyword_type, content_type, context_type)
```

### 1.3 改进定义提取
```python
# 当前问题：简单的正则表达式
# 优化方案：使用NLP技术提取定义

def improved_extract_definition(text: str, section_title: str) -> list[str]:
    """
    改进的定义提取函数
    使用NLP技术识别定义句
    """
    definitions = []
    
    # 1. 句子分割
    sentences = split_into_sentences(text)
    
    # 2. 定义句识别
    for sentence in sentences:
        if is_definition_sentence(sentence, section_title):
            definitions.append(sentence)
    
    # 3. 定义排序和筛选
    return rank_definitions(definitions, section_title)
```

## 二、流程优化

### 2.1 合并步骤，提高效率
```python
# 当前：分离的步骤导致重复处理
# 优化：合并为单一流程

def optimized_extraction_workflow(pdf_path: str):
    """
    优化的提取流程
    合并多个步骤，减少重复处理
    """
    # 1. 一次性读取PDF并提取所有信息
    pdf_data = extract_pdf_data(pdf_path)
    
    # 2. 并行处理多个任务
    with ThreadPoolExecutor(max_workers=4) as executor:
        # 并行提取知识点
        nodes_future = executor.submit(extract_knowledge_nodes, pdf_data)
        
        # 并行提取定义
        definitions_future = executor.submit(extract_definitions, pdf_data)
        
        # 并行提取因果关系
        causal_links_future = executor.submit(extract_causal_links, pdf_data)
        
        # 等待所有任务完成
        nodes = nodes_future.result()
        definitions = definitions_future.result()
        causal_links = causal_links_future.result()
    
    # 3. 合并结果
    return merge_extraction_results(nodes, definitions, causal_links)
```

### 2.2 增加层级结构提取
```python
# 当前：只提取扁平列表
# 优化：提取层级结构

def extract_hierarchy(nodes: list[dict]) -> dict:
    """
    提取知识点的层级结构
    """
    hierarchy = {
        "root": None,
        "children": {},
        "levels": {}
    }
    
    for node in nodes:
        # 根据标题格式判断层级
        level = detect_hierarchy_level(node["title"])
        
        # 构建层级关系
        if level == 1:
            hierarchy["root"] = node["id"]
        else:
            parent_id = find_parent_node(node, nodes, level)
            hierarchy["children"].setdefault(parent_id, []).append(node["id"])
        
        hierarchy["levels"][node["id"]] = level
    
    return hierarchy
```

## 三、质量验证优化

### 3.1 增加语义验证
```python
# 当前：只检查格式
# 优化：增加语义验证

def semantic_validation(nodes: list[dict]) -> list[dict]:
    """
    语义层面的验证
    """
    issues = []
    
    for node in nodes:
        # 1. 检查知识点完整性
        if not is_complete_knowledge_node(node):
            issues.append({
                "type": "incomplete",
                "node_id": node["id"],
                "message": "知识点信息不完整"
            })
        
        # 2. 检查定义准确性
        if node.get("definition"):
            if not is_accurate_definition(node["definition"], node["title"]):
                issues.append({
                    "type": "inaccurate_definition",
                    "node_id": node["id"],
                    "message": "定义可能不准确"
                })
        
        # 3. 检查分类合理性
        if not is_reasonable_classification(node):
            issues.append({
                "type": "misclassification",
                "node_id": node["id"],
                "message": "分类可能不正确"
            })
    
    return issues
```

### 3.2 增加完整性检查
```python
def completeness_check(nodes: list[dict], original_content: str) -> dict:
    """
    检查提取的完整性
    """
    return {
        "coverage": calculate_coverage(nodes, original_content),
        "missing_sections": identify_missing_sections(nodes, original_content),
        "redundancy": detect_redundancy(nodes),
        "consistency": check_consistency(nodes)
    }
```

## 四、性能优化

### 4.1 增加缓存机制
```python
# 缓存已处理的内容，避免重复计算
class ExtractionCache:
    def __init__(self):
        self.cache = {}
    
    def get(self, key: str):
        return self.cache.get(key)
    
    def set(self, key: str, value: any):
        self.cache[key] = value
    
    def clear(self):
        self.cache.clear()
```

### 4.2 并行处理优化
```python
def parallel_extraction(pdf_path: str, max_workers: int = 4):
    """
    并行提取知识点
    """
    # 1. 分割PDF为多个部分
    sections = split_pdf_into_sections(pdf_path)
    
    # 2. 并行处理每个部分
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for section in sections:
            future = executor.submit(extract_section, section)
            futures.append(future)
        
        # 3. 收集结果
        results = []
        for future in as_completed(futures):
            results.extend(future.result())
    
    return results
```

## 五、错误处理优化

### 5.1 增加详细的错误信息
```python
class ExtractionError(Exception):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.details = details or {}
    
    def to_dict(self):
        return {
            "error": str(self),
            "details": self.details,
            "timestamp": datetime.now().isoformat()
        }
```

### 5.2 增加恢复机制
```python
def extract_with_recovery(pdf_path: str, max_retries: int = 3):
    """
    带恢复机制的提取流程
    """
    for attempt in range(max_retries):
        try:
            return extract_knowledge_nodes(pdf_path)
        except Exception as e:
            if attempt == max_retries - 1:
                raise ExtractionError(
                    f"提取失败，已重试{max_retries}次",
                    {"attempt": attempt + 1, "error": str(e)}
                )
            time.sleep(2 ** attempt)  # 指数退避
```

## 六、用户界面优化

### 6.1 增加进度显示
```python
from tqdm import tqdm

def extract_with_progress(pdf_path: str):
    """
    带进度显示的提取流程
    """
    # 1. 读取PDF
    with tqdm(total=100, desc="读取PDF") as pbar:
        pdf_data = read_pdf(pdf_path)
        pbar.update(20)
    
    # 2. 提取知识点
    with tqdm(total=100, desc="提取知识点") as pbar:
        nodes = extract_knowledge_nodes(pdf_data)
        pbar.update(40)
    
    # 3. 验证结果
    with tqdm(total=100, desc="验证结果") as pbar:
        issues = validate_nodes(nodes)
        pbar.update(40)
    
    return nodes, issues
```

### 6.2 增加配置选项
```python
@dataclass
class ExtractionConfig:
    """提取配置"""
    # 标题识别
    heading_score_threshold: float = 0.8
    max_heading_length: int = 100
    
    # 知识点分类
    classification_method: str = "keyword"  # keyword, ml, hybrid
    
    # 定义提取
    definition_min_length: int = 10
    definition_max_length: int = 500
    
    # 性能
    max_workers: int = 4
    use_cache: bool = True
    
    # 质量验证
    enable_semantic_validation: bool = True
    completeness_threshold: float = 0.8
```

## 七、实施计划

### 阶段1：提取逻辑优化（1-2周）
1. 改进标题识别算法
2. 改进知识点分类
3. 改进定义提取

### 阶段2：流程优化（1-2周）
1. 合并步骤，提高效率
2. 增加层级结构提取
3. 增加并行处理

### 阶段3：质量验证优化（1周）
1. 增加语义验证
2. 增加完整性检查

### 阶段4：性能和错误处理优化（1周）
1. 增加缓存机制
2. 优化错误处理
3. 增加恢复机制

### 阶段5：用户界面优化（1周）
1. 增加进度显示
2. 增加配置选项

## 八、预期效果

1. **提取准确率提升**：从当前的约70%提升到85%以上
2. **处理速度提升**：通过并行处理，速度提升2-3倍
3. **错误率降低**：通过改进的错误处理，错误率降低50%以上
4. **用户体验提升**：通过进度显示和配置选项，提升用户体验

## 九、测试策略

1. **单元测试**：为每个改进的功能编写单元测试
2. **集成测试**：测试整个提取流程
3. **性能测试**：测试优化后的性能提升
4. **用户测试**：邀请用户测试新功能，收集反馈