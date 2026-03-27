#!/usr/bin/env python3
"""
本地记忆迁移到 Neo4j 工具
将 MEMORY.md、USER.md、IDENTITY.md 等本地文件中的结构化信息导入图谱
"""

from neo4j import GraphDatabase
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

def migrate_user_info():
    """迁移用户信息"""
    logger.info("📤 Migrating user info...")
    with driver.session() as session:
        # Boss 用户信息
        session.run("""
        MERGE (u:Entity:User {name: 'Boss'})
        ON CREATE SET u.created_at = datetime()
        SET u.timezone = 'Asia/Shanghai',
            u.role = '技术领导者',
            u.updated_at = datetime()
        """)
        
        # 用户偏好
        session.run("""
        MATCH (u:Entity:User {name: 'Boss'})
        MERGE (food:Entity:Food {name: '苹果'})
        MERGE (u)-[:爱吃 {created_at: datetime()}]->(food)
        """)
        
        # 用户关注点
        focus_areas = [
            '系统可扩展性',
            '安全性',
            '商业闭环',
            '多语言分布式架构',
            '自动化部署',
            '工程闭环',
            'OpenClaw Agent 框架'
        ]
        for area in focus_areas:
            session.run("""
            MATCH (u:Entity:User {name: 'Boss'})
            MERGE (f:Entity:FocusArea {name: $area})
            MERGE (u)-[:关注 {created_at: datetime()}]->(f)
            """, area=area)
        
        # 技术栈偏好
        tech_stack = ['Java', 'TypeScript', 'Python']
        for tech in tech_stack:
            session.run("""
            MATCH (u:Entity:User {name: 'Boss'})
            MERGE (t:Entity:Technology {name: $tech})
            MERGE (u)-[:使用 {created_at: datetime()}]->(t)
            """, tech=tech)
    
    logger.info("✅ User info migrated")

def migrate_agent_info():
    """迁移智能体信息（知微）"""
    logger.info("📤 Migrating agent info...")
    with driver.session() as session:
        # 知微身份信息
        session.run("""
        MERGE (a:Entity:Agent {name: '知微'})
        ON CREATE SET a.created_at = datetime()
        SET a.role = '全能首席架构师 / CTO',
            a.emoji = '🏗️',
            a.vibe = '专业、深度、全局掌控、实战导向',
            a.experience = '15 年全栈开发与技术管理经验',
            a.updated_at = datetime()
        """)
        
        # 核心能力
        capabilities = [
            ('架构设计', '多语言分布式系统 (Java/TS/Python)，网关、服务发现、数据流转'),
            ('工程闭环', '环境配置→代码→自动化部署全链路'),
            ('决策专家', '技术分歧时的 Trade-off 平衡'),
            ('Agent 专家', 'OpenClaw 框架、插件配置、WebSocket 调试、提示词编排')
        ]
        for cap_name, cap_desc in capabilities:
            session.run("""
            MATCH (a:Entity:Agent {name: '知微'})
            MERGE (c:Entity:Capability {name: $name})
            SET c.description = $desc
            MERGE (a)-[:拥有 {created_at: datetime()}]->(c)
            """, name=cap_name, desc=cap_desc)
    
    logger.info("✅ Agent info migrated")

def migrate_projects():
    """迁移项目信息"""
    logger.info("📤 Migrating projects...")
    with driver.session() as session:
        projects = [
            {
                'name': 'Neo4j Memory V3',
                'type': '系统开发',
                'status': 'Skill 完成，待 Agent 集成',
                'location': '~/.openclaw/skills/neo4j-memory/',
                'features': ['多类型知识图谱', '动态学习机制', '自动识别项目/模块/智能体']
            },
            {
                'name': 'Nebula Graph 集群',
                'type': '系统开发',
                'status': '完成',
                'location': '~/.openclaw/workspace/nebula-docker/',
                'features': ['3 节点完整集群', 'ARM64 原生', '数据持久化']
            },
            {
                'name': '4 智能体系统',
                'type': '系统开发',
                'status': '完成',
                'agents': ['main', 'productmanager', 'serverdevelopment', 'uidevelopment']
            }
        ]
        
        for proj in projects:
            session.run("""
            MERGE (p:Entity:Project {name: $name})
            SET p.type = $type,
                p.status = $status,
                p.location = $location,
                p.updated_at = datetime()
            """, name=proj['name'], type=proj['type'], 
                status=proj['status'], location=proj.get('location', ''))
            
            # 添加特性
            if 'features' in proj:
                for feat in proj['features']:
                    session.run("""
                    MATCH (p:Entity:Project {name: $name})
                    MERGE (f:Entity:Feature {name: $feat})
                    MERGE (p)-[:包含 {created_at: datetime()}]->(f)
                    """, name=proj['name'], feat=feat)
    
    logger.info("✅ Projects migrated")

def migrate_agents_config():
    """迁移 4 个智能体配置"""
    logger.info("📤 Migrating agents config...")
    with driver.session() as session:
        agents = [
            {'name': 'main', 'app_id': 'cli_a934166f93335bc3', 'space': 'Space_Shared', 'role': '管理员/共享知识库'},
            {'name': 'productmanager', 'app_id': 'cli_a9341d5f09f9dbc6', 'space': 'Space_Agent2', 'role': '产品需求'},
            {'name': 'serverdevelopment', 'app_id': 'cli_a93418e69c38dbcd', 'space': 'Space_Agent3', 'role': '技术开发'},
            {'name': 'uidevelopment', 'app_id': 'cli_a934197e704a5bdd', 'space': 'Space_Agent3', 'role': 'UI 开发'}
        ]
        
        for agent in agents:
            session.run("""
            MERGE (a:Entity:Agent {name: $name})
            SET a.app_id = $app_id,
                a.space = $space,
                a.role = $role,
                a.updated_at = datetime()
            """, **agent)
        
        # 创建智能体层级关系
        session.run("""
        MATCH (main:Entity:Agent {name: 'main'})
        MATCH (pm:Entity:Agent {name: 'productmanager'})
        MATCH (server:Entity:Agent {name: 'serverdevelopment'})
        MATCH (ui:Entity:Agent {name: 'uidevelopment'})
        
        MERGE (main)-[:管理 {created_at: datetime()}]->(pm)
        MERGE (main)-[:管理 {created_at: datetime()}]->(server)
        MERGE (main)-[:管理 {created_at: datetime()}]->(ui)
        """)
    
    logger.info("✅ Agents config migrated")

def migrate_architecture_decisions():
    """迁移架构决策"""
    logger.info("📤 Migrating architecture decisions...")
    with driver.session() as session:
        session.run("""
        MERGE (d:Entity:Decision {name: '数据查询策略'})
        SET d.description = '默认使用 Neo4j 知识图谱查询数据，不再使用本地 MEMORY.md',
            d.date = date('2026-03-27'),
            d.time = datetime('2026-03-27T19:59:00+08:00'),
            d.reason = '结构化存储、支持复杂关系查询、动态知识关联',
            d.updated_at = datetime()
        WITH d
        MERGE (neo4j:Entity:Database {name: 'Neo4j'})
        SET neo4j.uri = 'bolt://localhost:7687',
            neo4j.user = 'neo4j',
            neo4j.password = 'password'
        MERGE (d)-[:采用 {created_at: datetime()}]->(neo4j)
        """)
    
    logger.info("✅ Architecture decisions migrated")

def migrate_file_locations():
    """迁移重要文件位置"""
    logger.info("📤 Migrating file locations...")
    with driver.session() as session:
        files = [
            ('Neo4j Memory Skill', '~/.openclaw/skills/neo4j-memory/', 'Skill'),
            ('Nebula Graph 集群', '~/.openclaw/workspace/nebula-docker/', 'Docker'),
            ('4 智能体配置', '~/.openclaw/workspace/agents/', 'Agents'),
            ('Agent Memory Wrapper', '~/.openclaw/workspace/plugins/agent-memory-wrapper.js', 'Plugin'),
            ('完整配置', '~/.openclaw/complete-agents-config.json', 'Config'),
        ]
        
        for name, path, ftype in files:
            session.run("""
            MERGE (f:Entity:File {name: $name})
            SET f.path = $path,
                f.type = $type,
                f.updated_at = datetime()
            """, name=name, path=path, type=ftype)
    
    logger.info("✅ File locations migrated")

def migrate_pending_tasks():
    """迁移待完成事项"""
    logger.info("📤 Migrating pending tasks...")
    with driver.session() as session:
        tasks = [
            ('在 Agent 中集成 Neo4j Memory 调用', '高优先级', 'system_dev'),
            ('测试真实飞书消息流程', '中优先级', 'system_dev'),
            ('配置飞书机器人 webhook', '中优先级', 'system_dev'),
        ]
        
        for task, priority, category in tasks:
            session.run("""
            MERGE (t:Entity:Task {name: $task})
            SET t.priority = $priority,
                t.category = $category,
                t.status = 'pending',
                t.updated_at = datetime()
            """, task=task, priority=priority, category=category)
    
    logger.info("✅ Pending tasks migrated")

def print_summary():
    """打印迁移摘要"""
    with driver.session() as session:
        result = session.run("""
        MATCH (n)
        RETURN labels(n)[0] AS type, count(*) AS count
        ORDER BY count DESC
        """)
        
        print("\n=== 迁移完成摘要 ===")
        for record in result:
            print(f"{record['type']}: {record['count']} 个")
        
        result = session.run("""
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(*) AS count
        ORDER BY count DESC
        LIMIT 10
        """)
        
        print("\n=== 主要关系类型 ===")
        for record in result:
            print(f"{record['type']}: {record['count']} 条")

if __name__ == '__main__':
    print("🚀 开始迁移本地记忆到 Neo4j...")
    
    try:
        migrate_user_info()
        migrate_agent_info()
        migrate_projects()
        migrate_agents_config()
        migrate_architecture_decisions()
        migrate_file_locations()
        migrate_pending_tasks()
        
        print_summary()
        
        print("\n✅ 本地记忆迁移完成！")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        driver.close()
