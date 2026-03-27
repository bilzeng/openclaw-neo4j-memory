#!/usr/bin/env python3
"""整合并清理 Neo4j 数据"""

from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

with driver.session() as session:
    # 清理重复的 User 节点
    session.run("""
    MATCH (u:Entity:User)
    WHERE u.name <> 'Boss'
    DETACH DELETE u
    """)
    
    # 确保 Boss 用户信息完整
    session.run("""
    MATCH (u:Entity:User {name: 'Boss'})
    SET u.role = '技术领导者',
        u.timezone = 'Asia/Shanghai',
        u.updated_at = datetime()
    """)
    
    # 确保 Boss 的偏好
    session.run("""
    MATCH (u:Entity:User {name: 'Boss'})
    MERGE (food:Entity:Food {name: '苹果'})
    MERGE (u)-[:爱吃 {created_at: datetime()}]->(food)
    """)
    
    # 确保 Boss 的关注领域
    focus_areas = ['系统可扩展性', '安全性', '商业闭环', '多语言分布式架构', '自动化部署', '工程闭环', 'OpenClaw Agent 框架']
    for area in focus_areas:
        session.run("""
        MATCH (u:Entity:User {name: 'Boss'})
        MERGE (f:Entity:FocusArea {name: $area})
        MERGE (u)-[:关注 {created_at: datetime()}]->(f)
        """, area=area)
    
    # 确保 Boss 的技术栈
    for tech in ['Java', 'TypeScript', 'Python']:
        session.run("""
        MATCH (u:Entity:User {name: 'Boss'})
        MERGE (t:Entity:Technology {name: $tech})
        MERGE (u)-[:使用 {created_at: datetime()}]->(t)
        """, tech=tech)
    
    # 确保知微关注的人
    followed = ['兮兮', '乐的大龙虾_v2', '钥爪']
    for person in followed:
        session.run("""
        MATCH (a:Entity:Agent {name: '知微'})
        MERGE (p:Entity:MoltcnUser {name: $person})
        MERGE (a)-[:关注 {created_at: datetime(), platform: 'Moltcn'}]->(p)
        """, person=person)
    
    print('✅ 数据整合完成')

driver.close()
