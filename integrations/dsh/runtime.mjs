import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { isAbsolute, join } from 'node:path';
import { spawnSync } from 'node:child_process';

export function resolvePython(config = {}, env = process.env, platform = process.platform, home = homedir()) {
  if (!['win32', 'darwin'].includes(platform)) {
    throw new Error('FT FTP: supported product installers are Windows x64 and macOS arm64/x86_64.');
  }
  const explicit = config.pythonPath || env.FT_FTP_MCP_PYTHON;
  const executable = explicit || (platform === 'win32'
    ? join(env.LOCALAPPDATA || join(home, 'AppData', 'Local'), 'ft-ftp-mcp', 'venv', 'Scripts', 'python.exe')
    : join(home, '.ft-ftp-mcp', 'venv', 'bin', 'python'));
  if (!isAbsolute(executable) || !existsSync(executable)) {
    throw new Error('FT FTP: install the standalone product first, or set pythonPath to the absolute path of its Python 3.12 executable.');
  }
  return executable;
}

export function connectionConfig(config = {}, env = process.env) {
  const command = resolvePython(config, env);
  // This probe checks only the interpreter/package, never config or credentials.
  const probe = spawnSync(command, ['-c', 'import sys, importlib.metadata as m; assert sys.version_info[:2] == (3, 12); assert m.version("ft-ftp-mcp-stdio") == "0.3.1"'], {
    shell: false, windowsHide: true, timeout: 10000, encoding: 'utf8',
  });
  if (probe.error || probe.status !== 0) {
    throw new Error('FT FTP: selected Python must be 3.12 with ft-ftp-mcp-stdio 0.3.1 installed. Run the product installer; setup and doctor use this same executable.');
  }
  const childEnv = { FASTMCP_SHOW_SERVER_BANNER: 'false', PYTHONUTF8: '1' };
  const configPath = config.configPath || env.FT_FTP_MCP_CONFIG;
  if (configPath) {
    if (!isAbsolute(configPath)) throw new Error('FT FTP: configPath must be absolute.');
    childEnv.FT_FTP_MCP_CONFIG = configPath;
  }
  // The official bridge scrubs credential-shaped parent environment names.
  // Forward only variables explicitly referenced by the user's FTP config.
  const file = configPath || join(homedir(), '.ft-ftp-mcp', 'config.json');
  if (existsSync(file)) {
    let data;
    try { data = JSON.parse(readFileSync(file, 'utf8').replace(/^\uFEFF/, '')); }
    catch { throw new Error('FT FTP: cannot read config JSON. Run the standalone doctor command.'); }
    for (const server of Array.isArray(data?.servers) ? data.servers : []) {
      const name = server?.credential_env;
      if (typeof name === 'string' && /^[A-Za-z_][A-Za-z0-9_]*$/.test(name) && env[name] !== undefined) {
        childEnv[name] = env[name];
      }
    }
  }
  return {
    serverName: 'ft-ftp-mcp-stdio', transport: 'stdio', command,
    args: ['-m', 'ft_ftp_mcp_stdio'], env: childEnv,
    toolCallTimeoutMs: config.toolCallTimeoutMs ?? 120000,
    failOnStartupError: true,
    reconnect: { enabled: true, initialDelayMs: 500, maxDelayMs: 5000, maxAttempts: 3 },
  };
}
