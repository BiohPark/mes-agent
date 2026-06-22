import assert from "node:assert";
import {
  TRIGGER_PATTERN,
  toMsysPath,
  buildPrefixedCommand,
} from "../../.claude/hooks/inject-mes-agent-env.mjs";

{
  // python/pytest/pip 토큰이 있으면 트리거됨
  assert.equal(TRIGGER_PATTERN.test("python --version"), true);
  assert.equal(TRIGGER_PATTERN.test("python -m pytest tests/"), true);
  assert.equal(TRIGGER_PATTERN.test("pip install -r requirements.txt"), true);
}

{
  // 무관한 명령은 트리거 안 됨
  assert.equal(TRIGGER_PATTERN.test("git status"), false);
  assert.equal(TRIGGER_PATTERN.test("Get-ChildItem"), false);
}

{
  // Windows 경로 -> MSYS POSIX 경로 변환
  assert.equal(
    toMsysPath("D:\\programs\\miniconda3\\envs\\mes-agent"),
    "/d/programs/miniconda3/envs/mes-agent"
  );
}

{
  // 드라이브 문자가 없는 비정상 입력은 그대로 반환(안전한 폴백)
  assert.equal(toMsysPath("relative\\path"), "relative/path");
}

{
  // PowerShell: $env:Path 선주입 후 원본 커맨드
  const cmd = buildPrefixedCommand(
    "PowerShell",
    "D:\\programs\\miniconda3\\envs\\mes-agent",
    "python --version"
  );
  assert.equal(
    cmd,
    '$env:Path = "D:\\programs\\miniconda3\\envs\\mes-agent;D:\\programs\\miniconda3\\envs\\mes-agent\\Scripts;" + $env:Path; python --version'
  );
}

{
  // Bash: export PATH 선주입 후 원본 커맨드(POSIX 경로로 변환됨)
  const cmd = buildPrefixedCommand(
    "Bash",
    "D:\\programs\\miniconda3\\envs\\mes-agent",
    "pytest -q"
  );
  assert.equal(
    cmd,
    'export PATH="/d/programs/miniconda3/envs/mes-agent:/d/programs/miniconda3/envs/mes-agent/Scripts:$PATH"; pytest -q'
  );
}

{
  // 알려지지 않은 tool_name은 null(matcher가 걸러주지만 방어적으로 한 번 더 체크)
  assert.equal(
    buildPrefixedCommand("UnknownTool", "D:\\envs\\mes-agent", "python --version"),
    null
  );
}

console.log("inject-mes-agent-env fixtures passed");
