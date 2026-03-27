#!/usr/bin/env python3
"""
Neo4j Graph Memory v2 - 项目维度的知识图谱
支持项目、模块、智能体的关联关系

作者：知微
日期：2026-03-27
"""

from neo4j import GraphDatabase
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import re
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Neo4jGraphMemoryV2:
    """Neo4j 图谱记忆管理类 v2 - 项目维度"""
    
    # 智能体映射
    AGENT_MAPPING = {
        '后端': 'serverdevelopment',
        '数据库': 'serverdevelopment',
        '运维': 'serverdevelopment',
        '前端': 'uidevelopment',
        'UI': 'uidevelopment',
        '产品': 'productmanager',
        '管理员': 'main',
    }
    
    def __init__(self, uri: str = NEO4J_URI, 
                 user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # 验证连接并初始化拓扑
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("✅ Neo4j connected successfully")
            self._init_agent_topology()
        except Exception as e:
            logger.error(f"❌ Neo4j connection failed: {e}")
            raise
        
        logger.info(f"Neo4jGraphMemoryV2 initialized: {uri}")
        
    def _init_agent_topology(self):
        """静态初始化核心智能体的上下级组织架构拓扑"""
        try:
            with self.driver.session() as session:
                cypher = """
                MERGE (main:Entity:Agent {name: 'main'})
                MERGE (pm:Entity:Agent {name: 'productmanager'})
                MERGE (server:Entity:Agent {name: 'serverdevelopment'})
                MERGE (ui:Entity:Agent {name: 'uidevelopment'})
                
                MERGE (main)-[:`上下级` {role: 'manager'}]->(pm)
                MERGE (main)-[:`上下级` {role: 'manager'}]->(server)
                MERGE (main)-[:`上下级` {role: 'manager'}]->(ui)
                """
                session.run(cypher)
                logger.info("✅ Agent hierarchy initialized")
        except Exception as e:
            logger.error(f"Failed to initialize agent topology: {e}")
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
    
    def _extract_triplets_with_llm(self, user_intent: str, ai_solution: str, user_id: str, agent_id: str) -> List[Dict]:
        """使用 LLM 动态抽取 SPO 三元组事实 (双向抽取问题与方案、甚至纠正)"""
        try:
            import json, os, urllib.request, urllib.parse
            if not LLM_API_KEY:
                return []
            
            url = f"{LLM_BASE_URL}/chat/completions"
            system_prompt = f"""
你是一个专业的实时知识图谱事实提取引擎。当前正在处理由用户({user_id})和AI智能体({agent_id})产生的真实对话流。

【历史问答交互】
用户说："{user_intent}"
AI的解决方案/回答："{ai_solution}"

【系统任务】从这轮对话中提取出结构化的核心事实三元组（主体-关系-客体）。
**特别指令：**
1. 记录日常客观事实（例如：用户-喜欢-吃苹果）。
2. 记录技术探索结果：如果AI抛出了任何具备参考价值的具体方案或知识库词条，请将其提炼为：(问题或需求核心描述) -[:提供方案/解决为]-> (具体的方案方法)。
3. **记录被打脸的方案（RAG 纠错闭环）**：如果用户的语句是对AI之前的方案提出强烈抗议（比如“这个方案不行”、“报错了”、“你不能这么搞”），你必须从上下文脑补出他推翻了什么方案，然后输出一条极其特殊的新关系：(具体的失败方案名) -[:已被推翻/失效]-> (它试图解决的问题名)。

【提取要求 (极其重要)】
1. **原子级极细粒度拆分**：遇到长难句、超长说明书文本，绝对不允许将一段话打包成一个巨大的节点。必须将其打散为最细粒度的“原子级三元组”。
2. **节点长度限制**：提取出的 Subject（主语）和 Object（宾语/客体），字数必须严格控制在 **15 个字符以内**！切忌用大段描述做节点。如果原内容包含复杂逻辑，请拆解成多个级联的短关系（例如：不要写 (小明)-[发现]->(苹果落地是因为引力)，而应拆解为 (苹果)-[能够]->(落地), (苹果落地)-[归因于]->(万有引力) 等等）。
3. 只提取有实际沉淀价值的事实。代词“我”必须解析为“{user_id}”。
4. 输出严格的 JSON 数组格式，没有任何 Markdown 包裹，格式要求为：
[
  {{"s": "核心词", "p": "关系动词", "o": "极短客体"}}
]
绝对不能输出除纯 JSON 外任何文本！没有事实就输出 []！
"""
            data = {
                "model": LLM_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": system_prompt.strip()
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 1500,
                "result_format": "message"
            }
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'))
            req.add_header('Content-Type', 'application/json')
            req.add_header('Authorization', f'Bearer {LLM_API_KEY}')
            
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '[]')
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
                
            parsed = json.loads(content.strip())
            
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict) and "triplets" in parsed:
                return parsed["triplets"]
            return []
        except Exception as e:
            logger.error(f"LLM Triplet Extraction error: {e}")
            return []
    
    def insert_after_chat(self, user_id: str, intent: str, task: str = "", 
                         solution: str = "", result: str = "",
                         intent_type: str = "query",
                         confidence: float = 0.9,
                         agent_id: Optional[str] = None) -> bool:
        """对话后提取三元组事实插入图集 (V3: Spontaneous Entity Relational Graph)"""
        if not user_id:
            user_id = "User"
            
        try:
            with self.driver.session() as session:
                target_agent = agent_id or 'main'
                
                # 创建会话溯源（Provenance Timeline）
                session.run("""
                MERGE (u:Entity:User {name: $user_id})
                ON CREATE SET u.created_at = datetime()
                
                CREATE (i:Intent {
                    content: $intent,
                    intent_type: $intent_type,
                    confidence: $confidence,
                    created_at: datetime()
                })
                CREATE (u)-[:HAS_INTENT {created_at: datetime()}]->(i)
                """, user_id=user_id, intent=intent, intent_type=intent_type, confidence=confidence)
                
                # LLM 动态双向抽取事实三元组（包括人类问题与AI方案）
                triplets = self._extract_triplets_with_llm(intent, solution, user_id, target_agent)
                logger.info(f"🔍 Auto-detected SPO Triplets: {triplets}")
                
                # 将抽取的 SPO 关系实时编织进知识网络
                inserted_count = 0
                for triplet in triplets:
                    subj = triplet.get('s') or triplet.get('subject')
                    pred = triplet.get('p') or triplet.get('predicate')
                    obj = triplet.get('o')  or triplet.get('object')
                    
                    if not subj or not pred or not obj:
                        continue
                        
                    # 为防止 Neo4j 由于特殊符号崩溃，将中文和字符约束在安全区间，并用反引号包裹
                    pred_safe = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5_]', '', pred)
                    if not pred_safe:
                        pred_safe = "RELATED_TO"
                    
                    cypher = f"""
                    MERGE (s:Entity {{name: $subj}})
                    ON CREATE SET s.created_at = datetime()
                    
                    MERGE (o:Entity {{name: $obj}})
                    ON CREATE SET o.created_at = datetime()
                    
                    // 动态创建极高自由度关系（比如 -[:爱吃]-> 苹果 ）
                    MERGE (s)-[r:`{pred_safe}`]->(o)
                    ON CREATE SET r.created_at = datetime()
                    
                    WITH s, o, r
                    MATCH (i:Intent {{content: $intent, intent_type: $intent_type}})
                    // 把 Intent 挂接在该实体旁边作为消息源证明
                    MERGE (i)-[:MENTIONS]->(s)
                    MERGE (i)-[:MENTIONS]->(o)
                    """
                    
                    try:
                        session.run(cypher, subj=subj, obj=obj, intent=intent, intent_type=intent_type)
                        inserted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to insert triplet [{subj}]-[{pred_safe}]->[{obj}]: {e}")
                
                logger.info(f"✅ Inserted facts record: {user_id} → {inserted_count} triplets established.")
                return True
        
        except Exception as e:
            logger.error(f"❌ Insert failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def retrieve_before_chat(self, user_id: str, keyword: str = "", 
                            limit: int = 5, project: Optional[str] = None) -> List[Dict]:
        """
        对话前检索历史（增强版 - 支持项目过滤）
        
        Args:
            user_id: 用户 ID
            keyword: 关键词
            limit: 返回数量
            project: 指定项目（可选）
        
        Returns:
            list: 历史记录列表
        """
        try:
            with self.driver.session() as session:
                # 构建查询
                if project:
                    cypher = """
                    MATCH (u:User {id: $user_id})-[:HAS_INTENT]->(i:Intent)-[:RELATED_TO]->(p:Project {name: $project})
                    WHERE i.content CONTAINS $keyword
                    RETURN i.content AS content, 
                           i.created_at AS time,
                           p.name AS project,
                           [(i)-[:HAS_TASK]->(t:Task) | t.description][0..3] AS tasks
                    ORDER BY i.created_at DESC
                    LIMIT $limit
                    """
                elif keyword:
                    cypher = """
                    MATCH (u:User {id: $user_id})-[:HAS_INTENT]->(i:Intent)
                    WHERE i.content CONTAINS $keyword
                    OPTIONAL MATCH (i)-[:RELATED_TO]->(p:Project)
                    RETURN i.content AS content, 
                           i.created_at AS time,
                           p.name AS project,
                           [(i)-[:HAS_TASK]->(t:Task) | t.description][0..3] AS tasks
                    ORDER BY i.created_at DESC
                    LIMIT $limit
                    """
                else:
                    cypher = """
                    MATCH (u:User {id: $user_id})-[:HAS_INTENT]->(i:Intent)
                    OPTIONAL MATCH (i)-[:RELATED_TO]->(p:Project)
                    RETURN i.content AS content, 
                           i.created_at AS time,
                           p.name AS project,
                           [(i)-[:HAS_TASK]->(t:Task) | t.description][0..3] AS tasks
                    ORDER BY i.created_at DESC
                    LIMIT $limit
                    """
                
                params = {
                    'user_id': user_id,
                    'keyword': keyword,
                    'limit': limit
                }
                
                if project:
                    params['project'] = project
                
                result = session.run(cypher, **params)
                records = [record.data() for record in result]
                
                logger.info(f"✅ Retrieved {len(records)} records for {user_id}" + (f" (project={project})" if project else ""))
                return records
        
        except Exception as e:
            logger.error(f"❌ Retrieve failed: {e}")
            return []
    
    def get_project_overview(self, project_name: str) -> Dict:
        """
        获取项目全貌
        
        Returns:
            Dict: 项目信息，包括模块、智能体、任务统计
        """
        try:
            with self.driver.session() as session:
                cypher = """
                MATCH (p:Project {name: $project_name})
                
                // 获取所有模块和负责智能体
                OPTIONAL MATCH (p)-[:HAS_MODULE]->(m:Module)-[:ASSIGNED_TO]-(a:Agent)
                
                // 获取相关对话
                OPTIONAL MATCH (i:Intent)-[:RELATED_TO]->(p)
                
                // 获取任务
                OPTIONAL MATCH (i)-[:HAS_TASK]->(t:Task)
                
                RETURN 
                    p.name AS project,
                    p.status AS status,
                    collect(DISTINCT {module: m.name, agent: a.name, agent_id: a.id}) AS modules,
                    count(DISTINCT i) AS total_intents,
                    count(DISTINCT t) AS total_tasks,
                    sum(CASE WHEN t.status = '完成' OR t.status = 'success' THEN 1 ELSE 0 END) AS completed_tasks
                
                """
                
                result = session.run(cypher, project_name=project_name)
                record = result.single()
                
                if record:
                    return {
                        'project': record['project'],
                        'status': record['status'],
                        'modules': [m for m in record['modules'] if m['module']],
                        'total_intents': record['total_intents'],
                        'total_tasks': record['total_tasks'],
                        'completed_tasks': record['completed_tasks'] or 0
                    }
                return {}
        
        except Exception as e:
            logger.error(f"❌ Project overview failed: {e}")
            return {}
    
    def get_agent_projects(self, agent_id: str) -> List[Dict]:
        """
        获取智能体参与的所有项目
        
        Returns:
            List[Dict]: 项目列表
        """
        try:
            with self.driver.session() as session:
                cypher = """
                MATCH (a:Agent {id: $agent_id})-[:WORKS_ON]->(p:Project)
                OPTIONAL MATCH (p)-[:HAS_MODULE]->(m:Module)
                WHERE (m)-[:ASSIGNED_TO]->(a)
                
                RETURN 
                    p.name AS project,
                    p.status AS status,
                    collect(m.name) AS modules,
                    a.role AS role
                
                """
                
                result = session.run(cypher, agent_id=agent_id)
                return [record.data() for record in result]
        
        except Exception as e:
            logger.error(f"❌ Agent projects failed: {e}")
            return []
    
    def get_user_collaborations(self, user_id: str) -> List[Dict]:
        """
        获取用户的协作关系（与哪些智能体在哪些项目上合作）
        
        Returns:
            List[Dict]: 协作关系列表
        """
        try:
            with self.driver.session() as session:
                cypher = """
                MATCH (u:User {id: $user_id})-[:COLLABORATES_WITH]->(a:Agent)
                OPTIONAL MATCH (a)-[:WORKS_ON]->(p:Project)
                
                RETURN 
                    a.name AS agent_name,
                    a.id AS agent_id,
                    collect(DISTINCT p.name) AS projects,
                    count(DISTINCT p) AS project_count
                
                """
                
                result = session.run(cypher, user_id=user_id)
                return [record.data() for record in result]
        
        except Exception as e:
            logger.error(f"❌ User collaborations failed: {e}")
            return []
    
    def query_history(self, user_id: str, keyword: str = "", 
                     days: int = 7, limit: int = 10) -> List[Dict]:
        """查询用户历史（兼容旧接口）"""
        return self.retrieve_before_chat(user_id, keyword, limit)
    
    def get_user_stats(self, user_id: str) -> Dict:
        """获取用户统计（增强版）"""
        try:
            with self.driver.session() as session:
                cypher = """
                MATCH (u:User {id: $user_id})-[:HAS_INTENT]->(i:Intent)
                OPTIONAL MATCH (i)-[:RELATED_TO]->(p:Project)
                OPTIONAL MATCH (i)-[:HAS_TASK]->(t:Task)
                
                RETURN 
                    count(i) AS total_intents,
                    count(DISTINCT p) AS projects_involved,
                    count(t) AS total_tasks,
                    sum(CASE WHEN t.status = '完成' OR t.status = 'success' THEN 1 ELSE 0 END) AS completed_tasks
                
                """
                
                result = session.run(cypher, user_id=user_id)
                record = result.single()
                
                if record:
                    return {
                        'total_intents': record['total_intents'],
                        'projects_involved': record['projects_involved'] or 0,
                        'total_tasks': record['total_tasks'] or 0,
                        'completed_tasks': record['completed_tasks'] or 0
                    }
                return {'total_intents': 0}
        
        except Exception as e:
            logger.error(f"❌ Stats failed: {e}")
            return {'total_intents': 0}
    
    def get_all_projects(self) -> List[str]:
        """获取所有项目"""
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (p:Project) RETURN p.name AS name")
                return [record['name'] for record in result]
        except Exception as e:
            logger.error(f"❌ Get projects failed: {e}")
            return []
    
    def get_all_users(self) -> List[str]:
        """获取所有用户"""
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (u:User) RETURN u.id AS id")
                return [record['id'] for record in result]
        except Exception as e:
            logger.error(f"❌ Get users failed: {e}")
            return []
    
    def get_all_intents(self, limit: int = 20) -> List[Dict]:
        """获取所有意图（增强版 - 包含项目信息）"""
        try:
            with self.driver.session() as session:
                result = session.run("""
                MATCH (i:Intent)
                OPTIONAL MATCH (i)-[:RELATED_TO]->(p:Project)
                RETURN i.content AS content, 
                       i.created_at AS time,
                       p.name AS project
                ORDER BY i.created_at DESC
                LIMIT $limit
                """, limit=limit)
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"❌ Get intents failed: {e}")
            return []
    
    def clear_all(self):
        """清空所有数据（测试用）"""
        try:
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
                logger.info("✅ Cleared all data")
        except Exception as e:
            logger.error(f"❌ Clear failed: {e}")


def get_graph_memory(agent_id: str = "main") -> Neo4jGraphMemoryV2:
    """获取图谱记忆实例"""
    return Neo4jGraphMemoryV2(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD
    )


if __name__ == '__main__':
    # 测试 V3 Knowledge Graph 结构
    print("🧪 Testing Neo4j Graph Memory V3 (SPO Entities)...")
    gm = get_graph_memory()
    
    print("\n1. Testing dynamic generation of triplets...")
    
    test_intent_1 = "我爱吃苹果！你能不能帮忙查一下附近有没有什么大个的红富士苹果卖？另外张三其实是负责后端的工程师。"
    result1 = gm.insert_after_chat(
        user_id='Boss',
        intent=test_intent_1,
        agent_id='main'
    )
    print(f"   Test 1 Result: {'✅' if result1 else '❌'}")
    
    print("\n2. Graph facts have been generated. Check via Neo4j browser!")
    gm.close()
