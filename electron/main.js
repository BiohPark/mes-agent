const { app, BrowserWindow, ipcMain, screen } = require('electron')
const path = require('path')
const fs = require('fs')
const crypto = require('crypto')
const { spawn } = require('child_process')
const http = require('http')

// 서버 인증 토큰 (S1) — 매 실행마다 랜덤 생성, Python 서버와 렌더러가 공유
const AUTH_TOKEN = crypto.randomBytes(32).toString('hex')
process.env.AGENT_AUTH_TOKEN = AUTH_TOKEN  // 렌더러(preload)가 process.env로 읽음

function loadDotEnv() {
  const envPath = path.join(__dirname, '..', '.env')
  if (!fs.existsSync(envPath)) return {}
  return Object.fromEntries(
    fs.readFileSync(envPath, 'utf-8').split('\n')
      .map(l => l.trim())
      .filter(l => l && !l.startsWith('#') && l.includes('='))
      .map(l => { const [k, ...v] = l.split('='); return [k.trim(), v.join('=').trim()] })
  )
}

const _envFromFile = loadDotEnv()
const SERVER_PORT = parseInt(_envFromFile.AGENT_PORT || process.env.AGENT_PORT || '8000', 10)

let mainWindow
let hudWindow
let pythonProcess
let _lastHudPayload = null

function startPythonServer() {
  pythonProcess = spawn('python', ['-m', 'agent.server'], {
    cwd: path.join(__dirname, '..'),
    stdio: 'pipe',
    // 시스템 환경변수가 .env보다 우선. AGENT_AUTH_TOKEN(process.env)이 서버로 전달됨
    env: { ..._envFromFile, ...process.env }
  })

  pythonProcess.stdout.on('data', d => console.log('[agent]', d.toString().trim()))
  pythonProcess.stderr.on('data', d => console.error('[agent]', d.toString().trim()))
  pythonProcess.on('close', code => console.log(`[agent] 종료 (code: ${code})`))
}

function waitForServer(retries = 30) {
  return new Promise((resolve, reject) => {
    const check = (n) => {
      http.get(`http://localhost:${SERVER_PORT}/health`, res => {
        if (res.statusCode === 200) resolve()
        else if (n > 0) setTimeout(() => check(n - 1), 500)
        else reject(new Error('서버가 시작되지 않았습니다'))
      }).on('error', () => {
        if (n > 0) setTimeout(() => check(n - 1), 500)
        else reject(new Error('서버에 연결할 수 없습니다'))
      })
    }
    check(retries)
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'MES Agent',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,  // 보안: 샌드박스 유지. preload는 fs 대신 additionalArguments로 값 수신
      // 샌드박스 preload는 fs/path를 require할 수 없으므로 포트·토큰을 argv로 전달
      additionalArguments: [
        `--agent-port=${SERVER_PORT}`,
        `--auth-token=${AUTH_TOKEN}`
      ]
    }
  })

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'))
  if (process.env.DEV_TOOLS === '1') mainWindow.webContents.openDevTools()

  mainWindow.on('closed', () => {
    if (hudWindow && !hudWindow.isDestroyed()) hudWindow.close()
    if (glowWindow && !glowWindow.isDestroyed()) glowWindow.close()
  })
}

// ── 협업모드 플로팅 HUD (백로그 H) ──────────────────────────────
// 포커스 비탈취: focusable:false, alwaysOnTop. 메인창을 안 띄워도 힌트만 떠 있음.
function createHudWindow() {
  if (hudWindow && !hudWindow.isDestroyed()) { hudWindow.show(); return }
  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  hudWindow = new BrowserWindow({
    width: 340, height: 160,
    x: width - 360, y: height - 190,
    frame: false, transparent: true, resizable: false,
    alwaysOnTop: true, focusable: false, skipTaskbar: true,
    webPreferences: {
      preload: path.join(__dirname, 'hud-preload.js'),
      contextIsolation: true, nodeIntegration: false
    }
  })
  hudWindow.setAlwaysOnTop(true, 'screen-saver')
  hudWindow.loadFile(path.join(__dirname, 'renderer', 'hud.html'))
  hudWindow.webContents.on('did-finish-load', () => {
    if (_lastHudPayload && hudWindow && !hudWindow.isDestroyed()) {
      hudWindow.webContents.send('hud-update', _lastHudPayload)
    }
  })
  hudWindow.on('closed', () => { hudWindow = null })
}

// 메인 렌더러가 HUD 표시/숨김·갱신을 제어하고, HUD의 사용자 동작은 메인으로 중계한다.
let _hudOwner = null
ipcMain.on('collab-show-hud', () => { _hudOwner = 'collab'; _lastHudPayload = null; createHudWindow() })
ipcMain.on('collab-hide-hud', () => {
  if (_hudOwner === 'collab') _hudOwner = null
  if (hudWindow && !hudWindow.isDestroyed()) hudWindow.close()
})
ipcMain.on('hud-update-fwd', (_e, payload) => {
  _lastHudPayload = payload
  if (hudWindow && !hudWindow.isDestroyed()) hudWindow.webContents.send('hud-update', payload)
})
ipcMain.on('hud-event', (_e, payload) => {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('collab-command', payload)
})

// ── 화면 테두리 글로우 오버레이 (백로그 X) ──────────────────────
// 에이전트가 화면을 조작하는 동안 모니터 전체 테두리에 "사용 중" 음영을 띄운다.
// 전체 화면을 덮는 투명·클릭 통과·항상 위·포커스 비탈취 창 (createHudWindow 패턴).
let glowWindow = null

function createGlowWindow() {
  if (glowWindow && !glowWindow.isDestroyed()) { glowWindow.show(); return }
  const b = screen.getPrimaryDisplay().bounds  // 작업표시줄 영역까지 포함한 전체 테두리
  glowWindow = new BrowserWindow({
    x: b.x, y: b.y, width: b.width, height: b.height,
    frame: false, transparent: true, resizable: false, movable: false,
    alwaysOnTop: true, focusable: false, skipTaskbar: true, hasShadow: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false }
  })
  glowWindow.setIgnoreMouseEvents(true)   // 순수 장식 — 모든 클릭 통과
  glowWindow.setAlwaysOnTop(true, 'screen-saver')
  glowWindow.loadFile(path.join(__dirname, 'renderer', 'screen-glow.html'))
  glowWindow.on('closed', () => { glowWindow = null })
}

function showGlow() { createGlowWindow() }
function hideGlow() {
  if (glowWindow && !glowWindow.isDestroyed()) glowWindow.close()
}

// ── 실행 중 창 가림 회피 (개선 아이디어 C / 백로그 X) ──────────────
// 렌더러가 agentState=running 일 때 'agent-busy', idle 일 때 'agent-idle' 를 보낸다.
// mode: 'dock-right'(대화만 우측 도킹) | 'dock-keep'(사이드바만 접고 우측 도킹)
//     | 'hud'(작게 비켜 보기) | 'minimize'(자동 최소화) | 'translucent'(반투명) | 'off'(끄기)
const DOCK_WIDTH = 460
let _busyMode = 'dock-right'
let _wasMinimizedByAgent = false
let _savedBounds = null  // 도킹 전 원래 창 위치/크기 (idle 시 복원)

function dockMainWindowRight() {
  if (!mainWindow) return
  if (!_savedBounds) _savedBounds = mainWindow.getBounds()
  // createWindow의 minWidth:800이 좁은 도킹을 막으므로 일시적으로 완화
  mainWindow.setMinimumSize(360, 400)
  const wa = screen.getPrimaryDisplay().workArea
  mainWindow.setBounds({
    x: wa.x + wa.width - DOCK_WIDTH,
    y: wa.y,
    width: DOCK_WIDTH,
    height: wa.height,
  })
}

ipcMain.on('agent-busy', (_e, mode) => {
  _busyMode = mode || 'dock-right'
  if (!mainWindow || _busyMode === 'off') return
  showGlow()  // off가 아닌 모든 모드에서 테두리 글로우 표시
  if (_busyMode === 'dock-right' || _busyMode === 'dock-keep') {
    // 사이드바(±우측 패널) 숨김은 렌더러가 body 클래스로 처리. 창은 우측 도킹.
    dockMainWindowRight()
  } else if (_busyMode === 'hud') {
    if (_hudOwner !== 'collab') {
      _hudOwner = 'agent'
      _lastHudPayload = null
      createHudWindow()
    }
    if (!mainWindow.isMinimized()) {
      _wasMinimizedByAgent = true
      mainWindow.minimize()
    }
  } else if (_busyMode === 'minimize') {
    if (!mainWindow.isMinimized()) {
      _wasMinimizedByAgent = true
      mainWindow.minimize()
    }
  } else if (_busyMode === 'translucent') {
    mainWindow.setOpacity(0.15)
    mainWindow.setIgnoreMouseEvents(true, { forward: true })
  }
})

ipcMain.on('agent-idle', () => {
  hideGlow()
  if (!mainWindow) return
  // 어떤 모드였든 화면 간섭 상태를 원복
  if (_wasMinimizedByAgent && mainWindow.isMinimized()) {
    mainWindow.restore()
    _wasMinimizedByAgent = false
  }
  // 우측 도킹 복원: minWidth 원복 후 원래 bounds로
  if (_savedBounds) {
    mainWindow.setMinimumSize(800, 600)
    mainWindow.setBounds(_savedBounds)
    _savedBounds = null
  }
  mainWindow.setOpacity(1)
  mainWindow.setIgnoreMouseEvents(false)
  if (_hudOwner === 'agent') {
    _hudOwner = null
    if (hudWindow && !hudWindow.isDestroyed()) hudWindow.close()
  }
})

app.whenReady().then(async () => {
  startPythonServer()
  createWindow()

  // 페이지가 완전히 로드된 후에 IPC를 보내야 렌더러가 받을 수 있음
  await new Promise(resolve => mainWindow.webContents.once('did-finish-load', resolve))

  try {
    await waitForServer()
    mainWindow.webContents.send('server-ready')
  } catch (e) {
    mainWindow.webContents.send('server-error', e.message)
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (pythonProcess) pythonProcess.kill()
  if (process.platform !== 'darwin') app.quit()
})
