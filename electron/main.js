const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const fs = require('fs')
const { spawn } = require('child_process')
const http = require('http')

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
    env: { ..._envFromFile, ...process.env }  // 시스템 환경변수가 .env보다 우선
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
