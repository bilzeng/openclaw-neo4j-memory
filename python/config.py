import os

def load_env():
    """Simple parser for .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if not os.path.exists(env_path):
        return
        
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip()

load_env()

NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'password')

# For backward compatibility with the user's existing setup, if LLM_API_KEY is not in .env, fallback to openclaw.json
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://coding.dashscope.aliyuncs.com/v1')
LLM_MODEL = os.environ.get('LLM_MODEL', 'qwen3.5-plus')

if not LLM_API_KEY:
    try:
        import json
        config_path = os.path.expanduser('~/.openclaw/openclaw.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                c = json.load(f)
                LLM_API_KEY = c.get('models', {}).get('providers', {}).get('custom-coding-dashscope-aliyuncs-com', {}).get('apiKey', '')
    except Exception:
        pass
