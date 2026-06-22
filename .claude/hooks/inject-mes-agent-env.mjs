#!/usr/bin/env node
// PreToolUse 훅: Bash/PowerShell 명령에 python/pytest/pip 토큰이 있으면
// 동적으로 찾은 mes-agent conda 환경을 PATH 맨 앞에 주입한다.
//
// 설계 원칙: python/pytest/pip 토큰이 없는 명령은 즉시 통과(conda 호출 안 함,
// 비용 0). conda가 없거나 mes-agent 환경을 못 찾으면 조용히 원본 그대로 통과
// (no-op) — 이 훅이 무관한 명령을 절대 깨면 안 된다. 환경 경로는 하드코딩하지
// 않고 conda 자신이 관리하는 `~/.conda/environments.txt` 레지스트리 파일을 직접
// 읽어서 동적 탐색한다(포터빌리티 — 다른 PC에 클론해도 conda 설치 위치만 다르면
// 그대로 동작). `conda info --envs --json`을 셔틀하는 방식은 실측 결과 3~5초가
// 걸려(Python 인터프리터 기동 비용) python/pytest 호출마다 그 지연이 붙고 내부
// 타임아웃을 간헐적으로 넘겨 플레이키하게 동작해 폐기 — 파일 읽기는 그 비용이 없다.
//
// 커맨드만 재작성하고(updatedInput) permissionDecision은 의도적으로 주지 않는다
// — 권한 승인 여부는 사용자가 기존 permissions 흐름으로 직접 결정해야 한다는
// 사용자 결정(에이전트가 자기 커맨드 실행을 스스로 승인하지 않음).
//
// 로그가 필요하면 반드시 process.stderr.write만 사용할 것 — stdout에 잡음이
// 섞이면 JSON 파싱이 깨져 훅이 "결정 없음"으로 조용히 무시된다.

import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, basename } from "node:path";
import { pathToFileURL } from "node:url";

export const TARGET_ENV_NAME = "mes-agent";
export const TRIGGER_PATTERN = /\b(python|pytest|pip)\b/i;

function readStdin() {
  const chunks = [];
  process.stdin.on("data", (c) => chunks.push(c));
  return new Promise((resolve, reject) => {
    process.stdin.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    process.stdin.on("error", reject);
  });
}

function passthrough() {
  process.exit(0); // 출력 없음 = "이 훅은 결정 없음", 원본 커맨드 그대로 실행
}

function findCondaEnvPath(envName) {
  const registryPath = join(homedir(), ".conda", "environments.txt");
  let raw;
  try {
    raw = readFileSync(registryPath, "utf8");
  } catch {
    return null; // 레지스트리 없음(conda 미사용 등) — graceful no-op
  }
  // environments.txt는 한 줄에 한 환경의 절대경로(conda root 자신 + envs/<name>들).
  // 환경 이름은 conda 표준 레이아웃대로 경로의 마지막 세그먼트와 같다.
  const lines = raw.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  for (const envPath of lines) {
    if (basename(envPath) === envName) return envPath;
  }
  return null;
}

export function toMsysPath(winPath) {
  // D:\foo\bar -> /d/foo/bar (Git Bash/MSYS 규칙)
  const normalized = winPath.replace(/\\/g, "/");
  const match = normalized.match(/^([A-Za-z]):\/(.*)$/);
  if (!match) return normalized; // 드라이브 문자가 없는 비정상 입력 — 그대로 반환
  const [, drive, rest] = match;
  return `/${drive.toLowerCase()}/${rest}`;
}

export function buildPrefixedCommand(toolName, envPath, originalCommand) {
  const scriptsPath = `${envPath}\\Scripts`;
  if (toolName === "PowerShell") {
    return `$env:Path = "${envPath};${scriptsPath};" + $env:Path; ${originalCommand}`;
  }
  if (toolName === "Bash") {
    const posixEnv = toMsysPath(envPath);
    return `export PATH="${posixEnv}:${posixEnv}/Scripts:$PATH"; ${originalCommand}`;
  }
  return null; // matcher가 걸러주지만 방어적으로 한 번 더 체크
}

async function main() {
  let input;
  try {
    input = JSON.parse(await readStdin());
  } catch {
    passthrough(); // stdin이 비어있거나 JSON이 아니면 손대지 않는다
  }

  const toolName = input.tool_name;
  const command = input.tool_input && input.tool_input.command;

  if (typeof command !== "string" || !TRIGGER_PATTERN.test(command)) {
    passthrough(); // python/pytest/pip 토큰 없음 — conda 호출 자체를 건너뛴다
  }

  const envPath = findCondaEnvPath(TARGET_ENV_NAME);
  if (!envPath) {
    passthrough(); // conda 없음 또는 mes-agent 환경 못 찾음 — 원본 동작 유지
  }

  const newCommand = buildPrefixedCommand(toolName, envPath, command);
  if (!newCommand) {
    passthrough();
  }

  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        updatedInput: { command: newCommand },
      },
    })
  );
  process.exit(0);
}

// 직접 실행될 때만 stdin을 읽는다 — 테스트 파일이 위 순수 함수들만 import할 때
// main()이 stdin 대기로 멈춰버리는 걸 방지(node:url의 표준 진입점 판별 패턴).
const isMainModule = import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMainModule) {
  main().catch(() => passthrough());
}
