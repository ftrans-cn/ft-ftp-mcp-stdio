// Test-only overlay for a real `dsh --profile ...` launch. No model/API key needed.
import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';

export const inject = ['tools'];
export async function apply(ctx, config = {}) {
  const prefix = 'mcp__ft-ftp-mcp-stdio__';
  const tools = () => ctx.tools.definitions().filter((tool) => tool.name.startsWith(prefix));
  for (let i = 0; i < 150 && tools().length !== 14; i++) {
    await new Promise((done) => setTimeout(done, 100));
  }
  assert.equal(tools().length, 14);
  const { results } = await ctx.tools.execute({
    calls: [{ type: 'tool-call', id: 'profile-probe', name: prefix + 'list_servers', arguments: '{}' }],
    signal: AbortSignal.timeout(10000),
  });
  assert.equal(Boolean(results[0].result.isError), false, JSON.stringify(results[0].result));
  assert.equal(results[0].result.value.structuredContent.ok, true);
  const report = { profileBoot: 'passed', toolCount: 14, listServers: 'passed', serverCount: results[0].result.value.structuredContent.servers.length };
  if (config.verifyRemote && report.serverCount > 0) {
    for (const [name, args] of [['test_connection', {}], ['list_dir', { path: '/' }]]) {
      const batch = await ctx.tools.execute({
        calls: [{ type: 'tool-call', id: 'desktop-' + name, name: prefix + name, arguments: JSON.stringify(args) }],
        signal: AbortSignal.timeout(30000),
      });
      report[name] = batch.results[0].result.isError ? 'failed' : 'passed';
    }
  }
  writeFileSync(config.reportPath || process.env.FT_FTP_DSH_PROBE_REPORT, JSON.stringify(report));
}
