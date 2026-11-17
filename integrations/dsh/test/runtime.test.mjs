import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { resolvePython, connectionConfig } from '../runtime.mjs';

test('default installer locations and explicit paths with spaces', () => {
  const home = mkdtempSync(join(tmpdir(), 'ftp dsh '));
  try {
    for (const [platform, path] of [
      ['win32', join(home, 'AppData', 'Local', 'ft-ftp-mcp', 'venv', 'Scripts', 'python.exe')],
      ['darwin', join(home, '.ft-ftp-mcp', 'venv', 'bin', 'python')],
    ]) {
      mkdirSync(resolve(path, '..'), { recursive: true });
      writeFileSync(path, 'fixture');
      assert.equal(resolvePython({}, {}, platform, home), path);
      assert.equal(resolvePython({ pythonPath: path }, { FT_FTP_MCP_PYTHON: 'missing' }, platform), path);
      assert.equal(resolvePython({}, { FT_FTP_MCP_PYTHON: path }, platform), path);
    }
    assert.throws(() => resolvePython({}, {}, 'linux', home), /supported product installers/);
    assert.throws(() => resolvePython({ pythonPath: 'python' }), /absolute path/);
    assert.throws(() => resolvePython({ pythonPath: join(home, 'missing') }), /install the standalone/);
  } finally { rmSync(home, { recursive: true, force: true }); }
});

test('real product preflight and narrowly scoped credential forwarding', () => {
  const pythonPath = process.env.FT_FTP_TEST_PYTHON;
  assert.ok(pythonPath, 'Set FT_FTP_TEST_PYTHON to the installed product Python 3.12');
  const home = mkdtempSync(join(tmpdir(), 'ftp dsh config '));
  try {
    const configPath = join(home, 'ftp.json');
    writeFileSync(configPath, '\uFEFF' + JSON.stringify({ servers: [{ credential_env: 'FTP_TEST_PASSWORD' }] }));
    const config = connectionConfig({ pythonPath, configPath }, {
      FTP_TEST_PASSWORD: 'local-fixture', OTHER_TOKEN: 'must-not-be-forwarded',
    });
    assert.equal(config.command, pythonPath);
    assert.deepEqual(config.args, ['-m', 'ft_ftp_mcp_stdio']);
    assert.equal(config.env.FTP_TEST_PASSWORD, 'local-fixture');
    assert.equal(config.env.OTHER_TOKEN, undefined);
    assert.equal(config.env.FT_FTP_MCP_CONFIG, configPath);
    assert.equal(config.failOnStartupError, true);
    assert.throws(() => connectionConfig({ pythonPath, configPath: 'relative.json' }), /must be absolute/);
    writeFileSync(configPath, '{bad-json');
    assert.throws(() => connectionConfig({ pythonPath, configPath }), /cannot read config JSON/);
    assert.throws(() => connectionConfig({ pythonPath: process.execPath }), /Python must be 3.12/);
  } finally { rmSync(home, { recursive: true, force: true }); }
});
