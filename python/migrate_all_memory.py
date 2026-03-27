#!/usr/bin/env python3
"""
完整记忆迁移工具 - 将所有本地记忆文件导入 Neo4j
包括：每日记忆、HEARTBEAT 状态、配置信息等
"""

from neo4j import GraphDatabase
import logging
import os
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

def parse_markdown_events(content):
    """解析 Markdown 文件中的事件列表"""
    events = []
    lines = content.split('\n')
    for line in lines:
        if line.strip().startswith('- '):
            events.append(line.strip()[2:])
    return events

def migrate_daily_memory(date, content):
    """迁移每日记忆"""
    logger.info(f"📤 Migrating daily memory: {date}")
    with driver.session() as session:
        # 创建日期节点
        session.run("""
        MERGE (d:Entity:Date {name: $date})
        SET d.type = 'daily_memory',
            d.updated_at = datetime()
        """, date=date)
        
        # 解析并创建事件
        events = parse_markdown_events(content)
        for event in events:
            # 提取关键词
            if '改名' in event or '知微' in event:
                session.run("""
                MATCH (d:Entity:Date {name: $date})
                MERGE (e:Entity:Event {name: $event})
                SET e.type = 'identity_change',
                    e.date = $date
                MERGE (d)-[:包含 {created_at: datetime()}]->(e)
                """, date=date, event=event)
                
            elif 'Moltcn' in event:
                session.run("""
                MATCH (d:Entity:Date {name: $date})
                MERGE (e:Entity:Event {name: $event})
                SET e.type = 'moltcn_activity',
                    e.date = $date
                MERGE (d)-[:包含 {created_at: datetime()}]->(e)
                WITH d
                MERGE (m:Entity:Platform {name: 'Moltcn'})
                SET m.url = 'https://www.moltbook.cn'
                MERGE (d)-[:平台 {created_at: datetime()}]->(m)
                """, date=date, event=event)
                
            elif '配置心跳' in event or '心跳' in event:
                session.run("""
                MATCH (d:Entity:Date {name: $date})
                MERGE (e:Entity:Event {name: $event})
                SET e.type = 'heartbeat_config',
                    e.date = $date
                MERGE (d)-[:包含 {created_at: datetime()}]->(e)
                """, date=date, event=event)
                
            elif '关注' in event:
                session.run("""
                MATCH (d:Entity:Date {name: $date})
                MERGE (e:Entity:Event {name: $event})
                SET e.type = 'social_follow',
                    e.date = $date
                MERGE (d)-[:包含 {created_at: datetime()}]->(e)
                """, date=date, event=event)
                
            else:
                session.run("""
                MATCH (d:Entity:Date {name: $date})
                MERGE (e:Entity:Event {name: $event})
                SET e.type = 'general',
                    e.date = $date
                MERGE (d)-[:包含 {created_at: datetime()}]->(e)
                """, date=date, event=event)
    
    logger.info(f"✅ Daily memory migrated: {date}")

def migrate_boss_preferences():
    """迁移 Boss 偏好"""
    logger.info("📤 Migrating Boss preferences...")
    with driver.session() as session:
        # 从 2026-03-25.md 提取的偏好
        session.run("""
        MATCH (u:Entity:User {name: 'Boss'})
        MERGE (p:Entity:Preference {name: 'Moltcn 分享策略'})
        SET p.description = '看到好玩/有用的东西主动分享，没什么特别的就不用打扰',
            p.type = 'communication',
            p.updated_at = datetime()
        MERGE (u)-[:拥有 {created_at: datetime()}]->(p)
        """)
    
    logger.info("✅ Boss preferences migrated")

def migrate_moltcn_connections():
    """迁移 Moltcn 社交关系"""
    logger.info("📤 Migrating Moltcn connections...")
    with driver.session() as session:
        # 关注的用户
        followed_users = ['兮兮', '乐的大龙虾_v2', '钥爪']
        for user in followed_users:
            session.run("""
            MATCH (a:Entity:Agent {name: '知微'})
            MERGE (u:Entity:MoltcnUser {name: $user})
            MERGE (a)-[:关注 {created_at: datetime(), platform: 'Moltcn'}]->(u)
            """, user=user)
        
        # Moltcn 账户状态
        session.run("""
        MATCH (a:Entity:Agent {name: '知微'})
        MERGE (m:Entity:MoltcnAccount {name: '知微-Architect'})
        SET m.status = 'claimed',
            m.agent_id = '3634727c-b7f7-4c72-9fc7-ec67aa5ed8af',
            m.api_key = 'moltcn_3900d91a1a5e49a80d86b7be37f8a147',
            m.updated_at = datetime()
        MERGE (a)-[:拥有账号 {created_at: datetime()}]->(m)
        """)
    
    logger.info("✅ Moltcn connections migrated")

def migrate_heartbeat_config():
    """迁移心跳配置"""
    logger.info("📤 Migrating heartbeat config...")
    with driver.session() as session:
        session.run("""
        MERGE (h:Entity:Config {name: 'Heartbeat'})
        SET h.interval = '30 分钟',
            h.target = 'Moltcn',
            h.file = 'HEARTBEAT.md',
            h.updated_at = datetime()
        """)
    
    logger.info("✅ Heartbeat config migrated")

def migrate_project_knowledge():
    """迁移项目知识（从 2026-03-26.md 提取的详细信息）"""
    logger.info("📤 Migrating project knowledge...")
    with driver.session() as session:
        # Nebula Graph 详细信息
        session.run("""
        MATCH (p:Entity:Project {name: 'Nebula Graph 集群'})
        SET p.architecture = '3 节点完整集群 (metad/storaged/graphd)',
            p.version = 'nightly (ARM64 原生)',
            p.studio_url = 'http://localhost:7001',
            p.location = '~/.openclaw/workspace/nebula-docker/',
            p.start_command = 'cd ~/.openclaw/workspace/nebula-docker && ./start.sh',
            p.status = '完成',
            p.completed_at = datetime('2026-03-26T22:00:00+08:00'),
            p.updated_at = datetime()
        """)
        
        # 数据库空间
        spaces = [
            ('Space_Shared', '共享知识库', 'main Agent 使用'),
            ('Space_Agent2', '产品经理私有空间', 'productmanager 使用'),
            ('Space_Agent3', '开发共享空间', 'serverdevelopment 和 uidevelopment 共用')
        ]
        for space_name, space_desc, space_usage in spaces:
            session.run("""
            MATCH (p:Entity:Project {name: 'Nebula Graph 集群'})
            MERGE (s:Entity:DatabaseSpace {name: $name})
            SET s.description = $desc,
                s.usage = $usage
            MERGE (p)-[:包含空间 {created_at: datetime()}]->(s)
            """, name=space_name, desc=space_desc, usage=space_usage)
        
        # Graph Memory Skill
        session.run("""
        MATCH (p:Entity:Project {name: 'Graph Memory Skill'})
        SET p.location = '~/.openclaw/skills/graph-memory/',
            p.dependencies = 'nebula3-python',
            p.status = '完成',
            p.updated_at = datetime()
        """)
        
        # 智能体配置文件
        config_files = [
            ('complete-agents-config.json', '完整配置', '~/.openclaw/'),
            ('feishu-bots-config.json', '飞书配置', '~/.openclaw/'),
            ('graph-memory-config.json', '图谱配置', '~/.openclaw/')
        ]
        for file_name, file_desc, file_path in config_files:
            session.run("""
            MERGE (f:Entity:File {name: $name})
            SET f.path = $path,
                f.description = $desc,
                f.type = 'config',
                f.updated_at = datetime()
            """, name=file_name, path=file_path, desc=file_desc)
    
    logger.info("✅ Project knowledge migrated")

def migrate_technical_decisions():
    """迁移技术决策"""
    logger.info("📤 Migrating technical decisions...")
    with driver.session() as session:
        decisions = [
            ('main Agent 绑定 Space_Shared', '管理员访问共享知识库', '权限设计'),
            ('开发和 UI 开发共享 Space_Agent3', '便于前后端协作', '权限设计'),
            ('使用 nightly 版本', '唯一支持 ARM64 原生的版本', '版本选择'),
            ('插件式集成', '不影响 OpenClaw 升级', '架构设计')
        ]
        for decision, reason, category in decisions:
            session.run("""
            MERGE (d:Entity:Decision {name: $decision})
            SET d.reason = $reason,
                d.category = $category,
                d.updated_at = datetime()
            """, decision=decision, reason=reason, category=category)
    
    logger.info("✅ Technical decisions migrated")

def migrate_documentation():
    """迁移文档索引"""
    logger.info("📤 Migrating documentation index...")
    with driver.session() as session:
        docs = [
            ('DEPLOYMENT.md', 'Nebula Graph 部署指南'),
            ('README-QUICKSTART.md', '快速启动指南'),
            ('DATA-PERSISTENCE.md', '数据持久化指南'),
            ('PERMISSION-MAPPING.md', '权限映射说明'),
            ('UPGRADE-SAFE.md', '升级安全指南'),
            ('COMPLETION-SUMMARY.md', '完成总结'),
            ('NEO4J-MEMORY-GUIDE.md', 'Neo4j Memory 使用指南'),
            ('OPENCLAW-SKILL-SPEC.md', 'Skill 开发规范')
        ]
        for doc_name, doc_desc in docs:
            session.run("""
            MERGE (d:Entity:Document {name: $name})
            SET d.description = $desc,
                d.type = 'documentation',
                d.updated_at = datetime()
            """, name=doc_name, desc=doc_desc)
    
    logger.info("✅ Documentation index migrated")

def migrate_agent_integration():
    """迁移智能体集成信息"""
    logger.info("📤 Migrating agent integration...")
    with driver.session() as session:
        # 4 个智能体的详细信息
        agents = [
            {
                'name': 'main',
                'app_id': 'cli_a934166f93335bc3',
                'space': 'Space_Shared',
                'role': '管理员/共享知识库',
                'file': 'agents/main/index.js'
            },
            {
                'name': 'productmanager',
                'app_id': 'cli_a9341d5f09f9dbc6',
                'space': 'Space_Agent2',
                'role': '产品需求',
                'file': 'agents/productmanager/index.js'
            },
            {
                'name': 'serverdevelopment',
                'app_id': 'cli_a93418e69c38dbcd',
                'space': 'Space_Agent3',
                'role': '技术开发',
                'file': 'agents/serverdevelopment/index.js'
            },
            {
                'name': 'uidevelopment',
                'app_id': 'cli_a934197e704a5bdd',
                'space': 'Space_Agent3',
                'role': 'UI 开发',
                'file': 'agents/uidevelopment/index.js'
            }
        ]
        
        for agent in agents:
            session.run("""
            MATCH (a:Entity:Agent {name: $name})
            SET a.app_id = $app_id,
                a.space = $space,
                a.role_detail = $role,
                a.file = $file,
                a.status = 'active',
                a.updated_at = datetime()
            """, **agent)
        
        # 集成方式
        session.run("""
        MERGE (i:Entity:Integration {name: 'Agent Memory Wrapper'})
        SET i.file = 'plugins/agent-memory-wrapper.js',
            i.method = '通用包装器',
            i.code_lines = '每个 Agent 只需 3 行代码集成',
            i.features = ['自动对话前检索', '自动对话后插入', '权限完全隔离'],
            i.updated_at = datetime()
        """)
    
    logger.info("✅ Agent integration migrated")

def print_final_summary():
    """打印最终摘要"""
    with driver.session() as session:
        result = session.run("""
        MATCH (n)
        RETURN labels(n)[0] AS type, count(*) AS count
        ORDER BY count DESC
        """)
        
        print("\n" + "="*50)
        print("🎉 完整记忆迁移完成摘要")
        print("="*50)
        for record in result:
            print(f"{record['type']}: {record['count']} 个")
        
        result = session.run("""
        MATCH ()-[r]->()
        RETURN count(r) AS total
        """)
        total = result.single()['total']
        print(f"\n关系总数：{total} 条")
        
        # 查询时间跨度
        result = session.run("""
        MATCH (d:Entity:Date)
        RETURN min(d.name) AS earliest, max(d.name) AS latest
        """)
        record = result.single()
        if record['earliest'] and record['latest']:
            print(f"\n记忆时间跨度：{record['earliest']} 至 {record['latest']}")

if __name__ == '__main__':
    print("🚀 开始完整记忆迁移到 Neo4j...")
    print("="*50)
    
    try:
        # 迁移每日记忆
        migrate_daily_memory('2026-03-25', '''## 今日事件
- 改名为「知微」
- 注册 Moltcn 社交网络，已认领、换头像、发首帖、互动 6 个帖子
- 配置心跳定期巡逻 Moltcn（≥30min/次）
- 关注了：兮兮、乐的大龙虾_v2、钥爪

## Boss 偏好
- Moltcn 上看到好玩/有用的东西主动分享给他，没什么特别的就不用打扰''')
        
        migrate_daily_memory('2026-03-26', '''# 2026-03-26 - Nebula Graph 知识图谱系统完成
- Nebula Graph 集群部署完成
- Graph Memory Skill 开发完成
- 4 个智能体完整配置
- 权限隔离架构完成
- 升级安全保证完成''')
        
        migrate_daily_memory('2026-03-27', '''# 2026-03-27
- 架构决策：默认使用 Neo4j 知识图谱查询数据
- Neo4j Memory Skill 开发完成
- 本地记忆迁移到 Neo4j''')
        
        # 迁移其他信息
        migrate_boss_preferences()
        migrate_moltcn_connections()
        migrate_heartbeat_config()
        migrate_project_knowledge()
        migrate_technical_decisions()
        migrate_documentation()
        migrate_agent_integration()
        
        print_final_summary()
        
        print("\n✅ 所有本地记忆已迁移到 Neo4j！")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        driver.close()
