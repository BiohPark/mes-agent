const { contextBridge, ipcRenderer } = require('electron')

// 샌드박스 preload에서는 fs/path를 require할 수 없다(Error: module not found: fs).
// 메인 프로세스가 webPreferences.additionalArguments로 전달한 값을 process.argv에서 읽는다.
function argv(prefix, fallback) {
  const hit = (process.argv || []).find(a => a.startsWith(prefix))
  return hit ? hit.slice(prefix.length) : fallback
}

contextBridge.exposeInMainWorld('electronAPI', {
  serverPort: parseInt(argv('--agent-port=', '8000'), 10) || 8000,
  authToken: argv('--auth-token=', ''),  // 서버 인증 토큰 (S1)
  onServerReady: (cb) => ipcRenderer.on('server-ready', cb),
  onServerError: (cb) => ipcRenderer.on('server-error', (_, msg) => cb(msg)),
  // 실행 중 창 가림 회피 (개선 아이디어 C)
  agentBusy: (mode) => ipcRenderer.send('agent-busy', mode),
  agentIdle: () => ipcRenderer.send('agent-idle'),
  // 협업모드 HUD (백로그 H) — 메인 렌더러가 HUD를 제어
  collabShowHud: () => ipcRenderer.send('collab-show-hud'),
  collabHideHud: () => ipcRenderer.send('collab-hide-hud'),
  collabUpdateHud: (payload) => ipcRenderer.send('hud-update-fwd', payload),
  onCollabCommand: (cb) => ipcRenderer.on('collab-command', (_e, payload) => cb(payload)),
})
