import fs from 'fs';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
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
      
      const proc = spawn('python3', args);
      
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
      if (!userMsg) return;
      
      userMsg = sanitizeMessage(userMsg);
      
      debugLog(`Checking RAG... prompt length: ${userMsg.length}, text: ${userMsg.substring(0, 30)}`);
      
      if (userMsg.length > 0) {
          try {
              const scriptPath = path.join(__dirname, 'python', 'retrieve.py');
              if (fs.existsSync(scriptPath)) {
                  debugLog(`RAG retrieving context for: ${userMsg.substring(0, 20)}...`);
                  const child = spawn('python3', [scriptPath, userMsg]);
                  let stdoutData = '';
                  child.stdout.on('data', (d) => { stdoutData += d.toString(); });
                  
                  await new Promise((resolve) => {
                      child.on('close', resolve);
                      setTimeout(() => { child.kill(); resolve(); }, 60000); 
                  });
                  
                  const contextText = stdoutData.trim();
                  if (contextText && contextText.length > 5 && !contextText.includes('NO_CONTEXT_FOUND')) {
                      debugLog(`✅ Injected RAG Context into prependContext & appendSystemContext`);
                      return {
                          appendSystemContext: "=== NEO4J GRAPH MEMORY ===\nYou are connected to a Neo4j Knowledge Graph. All user preferences, relationship facts, and relevant historical context are securely stored there.\nIMPORTANT: Do NOT use the `memory_search` tool! Do NOT rely on local MEMORY.md files! Your memory is automatically fetched from Neo4j and injected straight into your prompt under the heading 【来自 Neo4j 大脑深处】.\nAlways rely directly on the facts provided in the injected section rather than searching locally.",
                          prependContext: `【来自 Neo4j 大脑深处的过往客观事实/尝试过的方案 (用于辅助分析推理和避坑)】:\n${contextText}\n\n【真实客观状态结束。】`
                      };
                  }

              }
          } catch (err) {
              debugLog('RAG Retrieval failed: ' + err.message);
          }
      }
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
