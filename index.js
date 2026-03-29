import fs from 'fs';
import os from 'os';
import { spawn, spawnSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function detectPython() {
  try {
    if (spawnSync('python3', ['--version']).status === 0) return 'python3';
  } catch (e) {}
  try {
    if (spawnSync('python', ['--version']).status === 0) return 'python';
  } catch (e) {}
  return os.platform() === 'win32' ? 'python' : 'python3';
}
const pythonCmd = detectPython();
let logger = console;
const debugLog = (msg) => {
  try { fs.appendFileSync('/tmp/openclaw_neo4j_debug.log', new Date().toISOString() + ' ' + msg + '\n'); } catch(e){}
};

debugLog('Plugin file evaluated!');

class Neo4jMemoryNativePlugin {
  constructor() {
    this.enabled = true;
    logger.info('[Neo4jMemoryNative] Initializing native node plugin V4 (RAG mode)...');
  }

  async recordInteraction(userId, message, response, agentId) {
    if (!this.enabled) return;
    try {
      debugLog(`Executing unified recordInteraction (Via Python Subprocess) for ${userId}!`);
      
      const args = [
        path.join(__dirname, 'python', 'hook.py'),
        userId || 'unknown',
        message || '',
        response || '',
        agentId || 'main'
      ];
      const proc = spawn(pythonCmd, args, { env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
      
      proc.stdout.on('data', (data) => {
        debugLog(`Python stdout: ${data}`);
      });
      proc.stderr.on('data', (data) => {
        debugLog(`Python stderr: ${data}`);
      });
      proc.on('close', (code) => {
        if (code === 0) {
            logger.info(`[Neo4jMemoryNative] ✅ Record inserted successfully via Python script for User ${userId}`);
        } else {
            logger.error(`[Neo4jMemoryNative] ❌ Python script exited with code ${code}`);
        }
      });
    } catch(e) {
      logger.error('[Neo4jMemoryNative] recordInteraction error:', e);
    }
  }
}

const pluginInstance = new Neo4jMemoryNativePlugin();

export function register(api) {
  if (api && api.logger) logger = api.logger;
  
  debugLog('register() called by OpenClaw');
  logger.info('[Neo4jMemoryNative] Registering hooks with native neo4j driver...');
  debugLog('api.on signature: ' + String(api.on));

  const extractText = (content) => {

      if (!content) return '';
      if (typeof content === 'string') return content;
      if (Array.isArray(content)) {
          return content.map(part => typeof part === 'string' ? part : (part.text || '')).join('\n');
      }
      return '';
  };
  
  const sanitizeMessage = (text) => {
      if (!text) return '';
      let clean = text.trim();
      const msgIdIdx = clean.lastIndexOf('[message_id:');
      if (msgIdIdx !== -1) {
          const endBracket = clean.indexOf(']', msgIdIdx);
          if (endBracket !== -1) {
              clean = clean.substring(endBracket + 1);
          }
      }
      clean = clean.trim();
      clean = clean.replace(/^ou_[a-zA-Z0-9]+:\s*/, '');
      return clean.trim();
  };

  // V4 PRE-CHAT RAG RETRIEVAL (All agents have full read access)
  api.on('before_prompt_build', async (event, ctx) => {
      debugLog(`before_prompt_build hook fired for agent ${ctx.agentId || 'unknown'}`);
      
      let userMsg = event.prompt;
      
      // Fallback: If prompt is empty (e.g., during memory refresh/new session), try to get the last user message from conversation history
      if (!userMsg && event.messages && Array.isArray(event.messages)) {
          const lastMsgs = event.messages.filter(m => m.role === 'user');
          if (lastMsgs.length > 0) {
              userMsg = extractText(lastMsgs[lastMsgs.length - 1].content);
          }
      }
      
      if (!userMsg) return;
      
      userMsg = sanitizeMessage(userMsg);
      debugLog(`Checking RAG... prompt length: ${userMsg.length}, text: ${userMsg.substring(0, 30)}`);
      
      // We ALWAYS inject the system guidance to constantly remind the agent about Neo4j,
      // preventing it from falling back to local memory files during empty resets.
      const currentTimestamp = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
      const systemGuidance = `=== NEO4J GRAPH MEMORY ===\nYou are connected to a Neo4j Knowledge Graph. All facts and historical context are injected below.
IMPORTANT RULES:
1. Do NOT use \`memory_search\` tool or rely on local MEMORY files. Your memory is ONLY the injected Neo4j content.
2. ⚠️ TEMPORAL REASONING ⚠️: The injected facts contain absolute timestamps (e.g., [2026-03-28T15:07 记录]). The REAL current time right now is 【${currentTimestamp}】. If a historical record says things like "今天"(today) or "昨天"(yesterday), you MUST evaluate them relative to the record's timestamp! (e.g. if a March 28th record says "今天吃地锅鸡", it means they ate it on March 28th. If today is March 29th, then they ate it "昨天" yesterday!) NEVER blindly repeat "今天" from an old record!`;
      let injectedContext = "【来自 Neo4j 大脑深处】: 当前查询上下文中没有提取到相关的历史记忆。";

      if (userMsg.length > 0) {
          try {
              const scriptPath = path.join(__dirname, 'python', 'retrieve.py');
              if (fs.existsSync(scriptPath)) {
                  debugLog(`RAG retrieving context for: ${userMsg.substring(0, 20)}...`);
                  const child = spawn(pythonCmd, [scriptPath, userMsg], { env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
                  let stdoutData = '';
                  child.stdout.on('data', (d) => { stdoutData += d.toString(); });
                  
                  await new Promise((resolve) => {
                      child.on('close', resolve);
                      setTimeout(() => { child.kill(); resolve(); }, 60000); 
                  });
                  
                  const contextText = stdoutData.trim();
                  if (contextText && contextText.length > 5 && !contextText.includes('NO_CONTEXT_FOUND')) {
                      debugLog(`✅ Injected RAG Context into prependContext & appendSystemContext`);
                      injectedContext = `【来自 Neo4j 大脑深处的过往客观事实/尝试过的方案 (用于辅助分析推理和避坑)】:\n${contextText}\n\n【真实客观状态结束。】`;
                  }
              }
          } catch (err) {
              debugLog('RAG Retrieval failed: ' + err.message);
          }
      }
      
      return {
          appendSystemContext: systemGuidance,
          prependContext: injectedContext
      };
  });
  
  // V4 POST-CHAT RECORDING
  api.on('agent_end', async (event, ctx) => {
     debugLog(`agent_end hook fired, sessionKey=${ctx.sessionKey}, success=${event.success}`);
     
     if (event.success && event.messages && event.messages.length >= 2) {
       let userMsg = extractText(event.messages.filter(m => m.role === 'user').pop()?.content);
       userMsg = sanitizeMessage(userMsg);
       
       let asstMsg = extractText(event.messages.filter(m => m.role === 'assistant').pop()?.content);
       asstMsg = sanitizeMessage(asstMsg);
       
       if (!asstMsg) {
         asstMsg = "Triggered Tool Call / Internal Action";
       }
       
       let userId = 'Boss';
       
       if (userMsg) {
          debugLog(`Executing unified recordInteraction from agent_end for ${userId}!`);
          await pluginInstance.recordInteraction(userId, userMsg, asstMsg, ctx.agentId || 'main');
       }
     }
  });
  
  logger.info('[Neo4jMemoryNative] Plugin Hooks Registered successfully (V4 SCHEMA).');
}

export default {
  id: 'neo4j-memory',
  name: 'Neo4j Memory (Native JS)',
  register
};
