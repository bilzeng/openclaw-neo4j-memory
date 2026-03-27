import sys
import os
import json
import urllib.request
from neo4j import GraphDatabase
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def extract_keywords(query: str):
    try:
        if not LLM_API_KEY: return []
        data = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": "提取用户语句中最核心的名词或专有名词概念，最多提取3个词，用逗号分隔。不要输出其他任何解释性文字！例如：如何清理docker容器镜像 -> 镜像,docker,清理"},
                {"role": "user", "content": query}
            ], "temperature": 0.1, "max_tokens": 50
        }
        req = urllib.request.Request(f"{LLM_BASE_URL}/chat/completions", data=json.dumps(data).encode('utf-8'))
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {LLM_API_KEY}')
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return [k.strip() for k in content.split(',') if len(k.strip()) > 1]
    except Exception as e:
        # Local keyword extraction fallback if API fails or times out
        stopwords = ['的', '了', '是', '在', '有', '怎么', '什么', '哪些', '如何', '帮我', '查一下', '一下', '这个', '那个', '啊', '呢', '我', '你', '他', '她']
        text = query
        for w in stopwords:
            text = text.replace(w, ' ')
        words = text.split()
        words.sort(key=len, reverse=True)
        return [w.strip() for w in words[:3] if len(w.strip()) > 1]

def retrieve_context(query: str):
    try:
        keywords = extract_keywords(query)
        if not keywords:
            print("NO_CONTEXT_FOUND")
            return
            
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        graph_facts = []
        with driver.session() as session:
            for kw in keywords:
                # Retrieve surrounding facts related to the keyword (including solutions and failed tags)
                cypher = """
                MATCH (s:Entity)-[r]->(o:Entity)
                WHERE s.name CONTAINS $kw OR o.name CONTAINS $kw OR type(r) CONTAINS $kw
                   OR (size(s.name) > 1 AND $kw CONTAINS s.name)
                   OR (size(o.name) > 1 AND $kw CONTAINS o.name)
                   OR (size(type(r)) > 1 AND $kw CONTAINS type(r))
                RETURN s.name, type(r), o.name
                ORDER BY elementId(r) DESC
                LIMIT 10
                """
                results = session.run(cypher, kw=kw)
                for record in results:
                    fact = f"已知客观情况或曾被尝试的方案：[{record[0]}] ---({record[1]})---> [{record[2]}]"
                    graph_facts.append(fact)
                    
        graph_facts = list(set(graph_facts)) # deduplicate
        if graph_facts:
            # Output directly to stdout for Node JS to consume
            print("\n".join(graph_facts[:8]))
        else:
            print("NO_CONTEXT_FOUND")
            
        driver.close()
    except Exception as e:
        print("NO_CONTEXT_FOUND")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        retrieve_context(sys.argv[1])
    else:
        print("NO_CONTEXT_FOUND")
