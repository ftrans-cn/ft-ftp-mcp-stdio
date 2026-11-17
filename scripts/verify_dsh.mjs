// Run with Node >=24.9. Dependencies are resolved only from an isolated DSH install.
// Usage: node scripts/verify_dsh.mjs <DSH runtime directory> <product python>
// Install pyftpdlib into the Python fixture environment (or set PYTHONPATH).
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { resolve, join, dirname } from 'node:path';
import { mkdtempSync, writeFileSync, readFileSync, rmSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

if (process.argv.length !== 4) throw new Error('Usage: node scripts/verify_dsh.mjs <DSH runtime directory> <product python>');
const runtime = resolve(process.argv[2]);
const pythonPath = resolve(process.argv[3]);
const require = createRequire(join(runtime, 'package.json'));
const load = (name) => import(pathToFileURL(require.resolve(name)).href);
const { Context } = await load('@deepseek-ai/cordis');
const { default: SystemPrompt } = await load('@deepseek-ai/dsh-system-prompt');
const { ToolsService } = await load('@deepseek-ai/dsh-tools');
const executor = await load('@deepseek-ai/dsh-tool-executor-native');
const plugin = await load('dsh-ft-ftp'); // installed tarball, never source import
const home = mkdtempSync(join(tmpdir(), 'ft-ftp dsh verification '));
const fixture = spawn(pythonPath, ['-u', join(dirname(fileURLToPath(import.meta.url)), 'dsh_ftp_fixture.py'), home], {
  stdio: ['ignore', 'pipe', 'inherit'], windowsHide: true,
});
const lines = createInterface({ input: fixture.stdout });
const ctx = new Context();
const deadline = setTimeout(() => {
  console.error('DSH verification exceeded 90s');
  process.exitCode = 1;
  fixture.kill();
  void ctx.fiber.dispose();
}, 90000);
const oldPythonPath = process.env.PYTHONPATH;
try {
  const info = await new Promise((accept, reject) => {
    lines.once('line', (line) => { try { accept(JSON.parse(line)); } catch (error) { reject(error); } });
    fixture.once('exit', (code) => reject(new Error(`FTP fixture exited: ${code}`)));
    fixture.once('error', reject);
  });
  process.env.FT_FTP_DSH_TEST_PASSWORD = 'disposable-test-only';
  // Observe only our own MCP process, without changing the product entry point.
  const pidFile = join(home, 'mcp.pid');
  writeFileSync(join(home, 'sitecustomize.py'),
    'import os, sys\nfrom pathlib import Path\n' +
    `if "-m" in sys.orig_argv and "ft_ftp_mcp_stdio" in sys.orig_argv: Path(${JSON.stringify(pidFile)}).write_text(str(os.getpid()))\n`);
  process.env.PYTHONPATH = home;
  await ctx.plugin(SystemPrompt, {});
  await ctx.plugin(ToolsService, {});
  await ctx.plugin(executor);
  let fiber = ctx.plugin(plugin, { pythonPath, configPath: info.configPath });
  await fiber;
  const prefix = 'mcp__ft-ftp-mcp-stdio__';
  const expected = ['delete', 'download_dir', 'download_file', 'get_file_info', 'list_dir', 'list_servers', 'make_dir', 'move', 'read_text_preview', 'rename', 'search_files', 'test_connection', 'upload_dir', 'upload_file'];
  const names = () => ctx.tools.definitions().filter((tool) => tool.name.startsWith(prefix)).map((tool) => tool.name.slice(prefix.length)).sort();
  assert.deepEqual(names(), expected);
  let count = 0;
  async function call(name, args = {}, success = true) {
    const batch = await ctx.tools.execute({
      calls: [{ type: 'tool-call', id: `fixture-${++count}`, name: prefix + name, arguments: JSON.stringify(args) }],
      signal: AbortSignal.timeout(15000),
    });
    const result = batch.results[0].result;
    assert.equal(Boolean(result.isError), !success, JSON.stringify({ name, result }));
    return success ? result.value.structuredContent : result;
  }
  assert.equal((await call('list_servers')).servers.length, 2);
  await call('test_connection');
  await call('list_dir', { path: '/' });
  await call('get_file_info', { path: '/hello.txt' });
  await call('search_files', { path: '/', pattern: '*.txt' });
  await call('read_text_preview', { path: '/hello.txt' });
  const downloaded = await call('download_file', { remote_path: '/hello.txt' });
  assert.equal(downloaded.sha256.length, 64);
  assert.equal(readFileSync(downloaded.local_path, 'utf8'), readFileSync(join(home, 'remote', 'hello.txt'), 'utf8'));
  const local = join(home, 'upload 中文.txt');
  writeFileSync(local, 'uploaded through real DSH');
  await call('make_dir', { path: '/destination' });
  await call('upload_file', { local_path: local, remote_path: '/uploaded.txt' });
  assert.equal(readFileSync(join(home, 'remote', 'uploaded.txt'), 'utf8'), 'uploaded through real DSH');
  await call('rename', { path: '/uploaded.txt', new_name: 'renamed.txt' });
  await call('move', { from_path: '/renamed.txt', to_path: '/destination/moved.txt' });
  await call('delete', { path: '/destination/moved.txt', confirm: false }, false);
  await call('delete', { path: '/destination/moved.txt', confirm: true });
  const folder = join(home, 'local-folder');
  mkdirSync(folder);
  writeFileSync(join(folder, 'nested.txt'), 'directory roundtrip');
  await call('upload_dir', { local_path: folder, remote_path: '/directory' });
  await call('download_dir', { remote_path: '/directory' });
  await call('make_dir', { path: '/forbidden', server: 'readonly' }, false);
  await call('list_dir', { path: '/../escape' }, false);
  const firstPid = Number(readFileSync(pidFile, 'utf8'));
  process.kill(firstPid);
  let recovered = false;
  for (let i = 0; i < 100; i++) {
    await new Promise((done) => setTimeout(done, 100));
    if (Number(readFileSync(pidFile, 'utf8')) === firstPid || names().length !== 14) continue;
    // The bridge retains schemas during reconnect; a real read-only call proves readiness.
    try { await call('test_connection'); recovered = true; break; } catch { /* not connected yet */ }
  }
  assert.ok(recovered, 'read-only tool succeeds again after the child crash');
  assert.notEqual(Number(readFileSync(pidFile, 'utf8')), firstPid, 'crash creates a new MCP child');
  assert.deepEqual(names(), expected, 'reconnect re-registers all tools');
  const replacementPid = Number(readFileSync(pidFile, 'utf8'));
  await fiber.dispose();
  assert.deepEqual(names(), [], 'disabling plugin unregisters all tools');
  assert.throws(() => process.kill(replacementPid, 0), /ESRCH/, 'disable terminates the owned MCP child');
  fiber = ctx.plugin(plugin, { pythonPath, configPath: info.configPath });
  await fiber;
  assert.deepEqual(names(), expected, 'reload releases namespace for next activation');
  await call('list_servers');
  await fiber.dispose();
  const bad = ctx.plugin(plugin, { pythonPath: join(home, 'missing-python') });
  await assert.rejects(async () => { await bad; }, /standalone product|absolute path/);
  assert.deepEqual(names(), [], 'failed startup does not leave stale tools');
  await bad.dispose();
  console.log(JSON.stringify({ dsh: '0.2.2-rc.1', tools: expected.length, calls: count, lifecycle: 'passed', reconnect: 'passed', realFtp: 'passed' }));
} finally {
  if (oldPythonPath === undefined) delete process.env.PYTHONPATH;
  else process.env.PYTHONPATH = oldPythonPath;
  await ctx.fiber.dispose();
  fixture.kill();
  lines.close();
  clearTimeout(deadline);
  delete process.env.FT_FTP_DSH_TEST_PASSWORD;
  await new Promise((done) => fixture.exitCode !== null ? done() : fixture.once('exit', done));
  rmSync(home, { recursive: true, force: true });
}
