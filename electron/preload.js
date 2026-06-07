const { contextBridge, ipcRenderer } = require('electron')
const fs = require('fs')
const path = require('path')

function readEnvPort() {
  try {
    const envPath = path.join(__dirname, '..', '.env')
    const lines = fs.readFileSync(envPath, 'utf-8').split('\n')
    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed.startsWith('AGENT_PORT=')) {
        return parseInt(trimmed.split('=')[1].trim(), 10)
      }
    }
  } catch {}
  return 8000
}

contextBridge.exposeInMainWorld('electronAPI', {
  serverPort: readEnvPort(),
  onServerReady: (cb) => ipcRenderer.on('server-ready', cb),
  onServerError: (cb) => ipcRenderer.on('server-error', (_, msg) => cb(msg)),
  // 실행 중 창 가림 회피 (개선 아이디어 C)
  agentBusy: (mode) => ipcRenderer.send('agent-busy', mode),
  agentIdle: () => ipcRenderer.send('agent-idle', ),
})
