// 협업 HUD 창 전용 preload (백로그 H)
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('hudAPI', {
  // 메인 렌더러가 보낸 갱신({hint, state}) 수신
  onUpdate: (cb) => ipcRenderer.on('hud-update', (_e, payload) => cb(payload)),
  // HUD의 사용자 동작을 메인 렌더러로 중계 ({type:'manual'|'stop'})
  emit: (payload) => ipcRenderer.send('hud-event', payload),
})
