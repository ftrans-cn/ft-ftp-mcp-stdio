import * as mcpClient from '@deepseek-ai/dsh-mcp-client';
import Schema from '@deepseek-ai/schemastery';
import { connectionConfig } from './runtime.mjs';

export const name = 'ft-ftp';
export const inject = mcpClient.inject;
export const Config = Schema.object({
  pythonPath: Schema.string().description('Absolute path to the installed product Python 3.12. Empty selects the standard product installation.'),
  configPath: Schema.string().description('Optional absolute FTP config path. Empty preserves the standalone product default.'),
  toolCallTimeoutMs: Schema.number().min(1000).max(3600000).default(120000),
});

export async function apply(ctx, config = {}) {
  // The child fiber belongs to this plugin: disable/uninstall disposes the MCP connection.
  await ctx.plugin(mcpClient, connectionConfig(config));
}
