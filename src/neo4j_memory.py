#!/usr/bin/env python3
"""
Neo4j Memory Module - Python 版本
自动记录对话到 Neo4j 知识图谱

作者：知微
日期：2026-03-27
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

# 尝试导入 neo4j 驱动
try:
    from neo4j import GraphDatabase, Driver
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("⚠️ neo4j driver not installed. Run: pip install neo4j")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Neo4jMemory:
    """Neo4j 记忆管理器"""
    
    def __init__(self):
        self.driver: Optional[Driver] = None
        self._connect()
    
    def _connect(self):
        """连接到 Neo4j 数据库"""
        if not NEO4J_AVAILABLE:
            logger.error("❌ neo4j driver not available")
            return
        
        # 从环境变量或配置文件读取连接信息
        uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        user = os.getenv('NEO4J_USER', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD', 'password')
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # 测试连接
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            logger.info(f"✅ Connected to Neo4j at {uri}")
            self._init_schema()
        except Exception as e:
            logger.error(f"❌ Failed to connect to Neo4j: {e}")
            self.driver = None
    
    def _init_schema(self):
        """初始化数据库 Schema"""
        if not self.driver:
            return
        
        constraints = [
            "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT project_name IF NOT EXISTS FOR (p:Project) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT agent_id IF NOT EXISTS FOR (a:Agent) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT intent_id IF NOT EXISTS FOR (i:Intent) REQUIRE i.id IS UNIQUE",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    logger.warning(f"Constraint creation warning: {e}")
        
        logger.info("✅ Schema initialized")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.driver is not None
    
    def record_message(self, user_id: str, message: str, response: str, 
                       agent_id: str = 'main') -> Dict[str, Any]:
        """
        记录对话到 Neo4j
        
        Args:
            user_id: 用户 ID
            message: 用户消息
            response: AI 回复
            agent_id: 智能体 ID
        
        Returns:
            记录结果
        """
        if not self.driver:
            return {'success': False, 'error': 'Not connected to Neo4j'}
        
        try:
            timestamp = datetime.now().isoformat()
            intent_id = f"intent_{timestamp}_{hash(message) % 10000}"
            
            # 提取项目和模块
            project_name = self._extract_project(message)
            module_name = self._extract_module(message)
            
            with self.driver.session() as session:
                # 创建用户节点
                session.run("""
                    MERGE (u:User {id: $user_id})
                    ON CREATE SET u.created_at = $timestamp
                """, user_id=user_id, timestamp=timestamp)
                
                # 创建智能体节点
                session.run("""
                    MERGE (a:Agent {id: $agent_id})
                    ON CREATE SET a.created_at = $timestamp
                """, agent_id=agent_id, timestamp=timestamp)
                
                # 创建意图节点
                session.run("""
                    MERGE (i:Intent {id: $intent_id})
                    SET i.content = $message,
                        i.response = $response,
                        i.created_at = $timestamp
                """, intent_id=intent_id, message=message, 
                     response=response, timestamp=timestamp)
                
                # 创建用户-意图关系
                session.run("""
                    MATCH (u:User {id: $user_id}), (i:Intent {id: $intent_id})
                    MERGE (u)-[:HAS_INTENT]->(i)
                """, user_id=user_id, intent_id=intent_id)
                
                # 创建智能体-意图关系
                session.run("""
                    MATCH (a:Agent {id: $agent_id}), (i:Intent {id: $intent_id})
                    MERGE (a)-[:RESPONDED_TO]->(i)
                """, agent_id=agent_id, intent_id=intent_id)
                
                # 创建项目节点（如果提取到）
                if project_name:
                    session.run("""
                        MERGE (p:Project {name: $project_name})
                        ON CREATE SET p.created_at = $timestamp
                    """, project_name=project_name, timestamp=timestamp)
                    
                    session.run("""
                        MATCH (i:Intent {id: $intent_id}), (p:Project {name: $project_name})
                        MERGE (i)-[:RELATED_TO]->(p)
                    """, intent_id=intent_id, project_name=project_name)
                    
                    # 创建模块节点（如果提取到）
                    if module_name:
                        session.run("""
                            MERGE (m:Module {name: $module_name, project: $project_name})
                            ON CREATE SET m.created_at = $timestamp
                        """, module_name=module_name, project_name=project_name, 
                             timestamp=timestamp)
                        
                        session.run("""
                            MATCH (p:Project {name: $project_name}), 
                                  (m:Module {name: $module_name, project: $project_name})
                            MERGE (p)-[:HAS_MODULE]->(m)
                        """, project_name=project_name, module_name=module_name)
                        
                        session.run("""
                            MATCH (m:Module {name: $module_name, project: $project_name}), 
                                  (a:Agent {id: $agent_id})
                            MERGE (m)-[:ASSIGNED_TO]->(a)
                        """, module_name=module_name, project_name=project_name, 
                             agent_id=agent_id)
                
                # 创建用户-智能体协作关系
                session.run("""
                    MATCH (u:User {id: $user_id}), (a:Agent {id: $agent_id})
                    MERGE (u)-[:COLLABORATES_WITH]->(a)
                """, user_id=user_id, agent_id=agent_id)
            
            logger.info(f"✅ Recorded intent: {intent_id}")
            return {
                'success': True,
                'intent_id': intent_id,
                'project': project_name,
                'module': module_name
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to record message: {e}")
            return {'success': False, 'error': str(e)}
    
    def retrieve_context(self, user_id: str, message: str, 
                         limit: int = 3) -> Dict[str, Any]:
        """
        检索历史对话上下文
        
        Args:
            user_id: 用户 ID
            message: 当前消息（用于相似度匹配）
            limit: 返回数量
        
        Returns:
            上下文信息
        """
        if not self.driver:
            return {'context': None, 'history': [], 'has_history': False}
        
        try:
            with self.driver.session() as session:
                # 查询用户的历史意图
                result = session.run("""
                    MATCH (u:User {id: $user_id})-[:HAS_INTENT]->(i:Intent)
                    OPTIONAL MATCH (i)-[:RELATED_TO]->(p:Project)
                    OPTIONAL MATCH (p)-[:HAS_MODULE]->(m:Module)
                    RETURN i.id AS intent_id,
                           i.content AS content,
                           i.response AS response,
                           i.created_at AS created_at,
                           p.name AS project,
                           m.name AS module
                    ORDER BY i.created_at DESC
                    LIMIT $limit
                """, user_id=user_id, limit=limit)
                
                history = []
                for record in result:
                    history.append({
                        'intent_id': record['intent_id'],
                        'content': record['content'],
                        'response': record['response'],
                        'created_at': record['created_at'],
                        'project': record['project'],
                        'module': record['module']
                    })
                
                # 格式化上下文
                if history:
                    context_lines = ["💭 历史对话参考:"]
                    for idx, h in enumerate(history, 1):
                        project_tag = f"[{h['project']}]" if h['project'] else ""
                        context_lines.append(f"{idx}. {project_tag} {h['content']}")
                    
                    context = "\n".join(context_lines)
                    return {
                        'context': context,
                        'history': history,
                        'has_history': True
                    }
                else:
                    return {
                        'context': None,
                        'history': [],
                        'has_history': False
                    }
                    
        except Exception as e:
            logger.error(f"❌ Failed to retrieve context: {e}")
            return {'context': None, 'history': [], 'has_history': False}
    
    def _extract_project(self, message: str) -> Optional[str]:
        """从消息中提取项目名称"""
        # 简单的关键词匹配
        project_keywords = {
            '小程序': '冀教版英语学习小程序',
            '学生系统': '学生系统',
            '电商': '电商系统',
            '后台': '后台管理系统',
            '管理': '管理系统',
        }
        
        for keyword, project in project_keywords.items():
            if keyword in message:
                return project
        
        return None
    
    def _extract_module(self, message: str) -> Optional[str]:
        """从消息中提取模块名称"""
        module_keywords = {
            '后端': '后端',
            '前端': '前端',
            '数据库': '数据库',
            'API': 'API',
            '后台': '后台',
            '页面': '前端',
            '接口': '后端',
        }
        
        for keyword, module in module_keywords.items():
            if keyword in message:
                return module
        
        return None
    
    def get_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户统计信息"""
        if not self.driver:
            return {
                'total_intents': 0,
                'projects_involved': 0,
                'total_tasks': 0,
                'completed_tasks': 0
            }
        
        try:
            with self.driver.session() as session:
                # 统计意图数量
                result = session.run("""
                    MATCH (u:User {id: $user_id})-[:HAS_INTENT]->(i:Intent)
                    RETURN count(i) AS total_intents
                """, user_id=user_id)
                total_intents = result.single()['total_intents']
                
                # 统计项目数量
                result = session.run("""
                    MATCH (u:User {id: $user_id})-[:HAS_INTENT]->(i:Intent)
                          -[:RELATED_TO]->(p:Project)
                    RETURN count(DISTINCT p) AS projects_involved
                """, user_id=user_id)
                projects_involved = result.single()['projects_involved']
                
                return {
                    'total_intents': total_intents,
                    'projects_involved': projects_involved,
                    'total_tasks': 0,  # 可以扩展
                    'completed_tasks': 0
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {
                'total_intents': 0,
                'projects_involved': 0,
                'total_tasks': 0,
                'completed_tasks': 0
            }
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            logger.info("✅ Neo4j connection closed")


# 全局单例
_memory_instance = None

def get_memory() -> Neo4jMemory:
    """获取 Memory 实例（单例）"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = Neo4jMemory()
    return _memory_instance


def record_message(user_id: str, message: str, response: str, 
                   agent_id: str = 'main') -> Dict[str, Any]:
    """便捷函数：记录消息"""
    memory = get_memory()
    return memory.record_message(user_id, message, response, agent_id)


def retrieve_context(user_id: str, message: str, 
                     limit: int = 3) -> Dict[str, Any]:
    """便捷函数：检索上下文"""
    memory = get_memory()
    return memory.retrieve_context(user_id, message, limit)


# 测试
if __name__ == '__main__':
    print("🧪 Testing Neo4j Memory Module...")
    
    memory = get_memory()
    
    if memory.is_connected():
        print("✅ Connected to Neo4j")
        
        # 测试记录
        result = memory.record_message(
            'Boss',
            '测试 Neo4j Memory',
            '这是测试回复',
            'main'
        )
        print(f"Record result: {result}")
        
        # 测试检索
        context = memory.retrieve_context('Boss', '测试', 3)
        print(f"Has history: {context['has_history']}")
        if context['context']:
            print(f"Context preview: {context['context'][:100]}...")
    else:
        print("❌ Not connected to Neo4j")
    
    memory.close()
