const { app, BrowserWindow, ipcMain } = require('electron')
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
let pythonProcess

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
      nodeIntegration: false
    }
  })

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'))
  if (process.env.DEV_TOOLS === '1') mainWindow.webContents.openDevTools()
}

// ── 실행 중 창 가림 회피 (개선 아이디어 C) ──────────────────────
// 렌더러가 agentState=running 일 때 'agent-busy', idle 일 때 'agent-idle' 를 보낸다.
// mode: 'minimize'(자동 최소화) | 'translucent'(반투명) | 'off'(끄기)
let _busyMode = 'minimize'
let _wasMinimizedByAgent = false

ipcMain.on('agent-busy', (_e, mode) => {
  _busyMode = mode || 'minimize'
  if (!mainWindow || _busyMode === 'off') return
  if (_busyMode === 'minimize') {
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
  if (!mainWindow) return
  // 어떤 모드였든 화면 간섭 상태를 원복
  if (_wasMinimizedByAgent && mainWindow.isMinimized()) {
    mainWindow.restore()
    _wasMinimizedByAgent = false
  }
  mainWindow.setOpacity(1)
  mainWindow.setIgnoreMouseEvents(false)
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
