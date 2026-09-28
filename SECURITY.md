# Security Policy

## Supported Versions

This project is currently in the `0.x` line. Security fixes are expected to target the latest published version unless maintainers state otherwise.

## Reporting a Vulnerability

Please report vulnerabilities privately to the project maintainers. Do not open a public issue containing passwords, private keys, hostnames, account names, host-key fingerprints, or server paths.

When reporting, include:

- A short description of the issue.
- A minimal reproduction when possible.
- The affected version or commit.
- Whether the issue requires FTP, SFTP, keyring, or MCP client interaction.

## Sensitive Data

Never commit:

- `~/.ft-ftp-mcp/config.json`
- `known_hosts`
- key files such as `.pem`, `.key`, or `.ppk`
- logs or staging files
- real FTP/SFTP hostnames, usernames, passwords, or host-key fingerprints

Live tests must run only against isolated, authorized test servers.

