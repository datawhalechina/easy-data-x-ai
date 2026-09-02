import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { buildWall } from './contributor-wall.mjs';
import { fetchContributors } from './contributors-data.mjs';

const rootDir = resolve(import.meta.dirname, '..');
const readmePath = resolve(rootDir, 'README.md');
const markerStart = '<!-- contributors:start -->';
const markerEnd = '<!-- contributors:end -->';

function resolveRepoSlug() {
  if (process.env.GITHUB_REPOSITORY) {
    return process.env.GITHUB_REPOSITORY;
  }

  const remote = execFileSync('git', ['remote', 'get-url', 'origin'], {
    cwd: rootDir,
    encoding: 'utf8',
  }).trim();

  const match = remote.match(/github\.com[:/](.+?)(?:\.git)?$/);
  if (!match) {
    throw new Error(`Unable to infer GitHub repository from remote: ${remote}`);
  }

  return match[1];
}

function updateReadme(wallMarkup) {
  const readme = readFileSync(readmePath, 'utf8');
  const pattern = new RegExp(`${markerStart}[\\s\\S]*?${markerEnd}`);

  if (!pattern.test(readme)) {
    throw new Error('Contributor wall markers were not found in README.md');
  }

  const next = readme.replace(pattern, wallMarkup);
  if (next !== readme) {
    writeFileSync(readmePath, next);
  }
}

const repoSlug = resolveRepoSlug();
const contributors = await fetchContributors(repoSlug);
const wallMarkup = buildWall(contributors);
updateReadme(wallMarkup);
