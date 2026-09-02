import assert from 'node:assert/strict';
import test from 'node:test';

import { buildWall } from './contributor-wall.mjs';

test('为仅有已合并 PR 的贡献者显示 PR 数量', () => {
  const wall = buildWall([
    {
      login: 'LINxiansheng',
      profileUrl: 'https://github.com/LINxiansheng',
      avatarUrl: 'https://avatars.githubusercontent.com/u/18351861?v=4&s=144',
      commitCount: 0,
      mergedPrCount: 3,
    },
  ]);

  assert.match(wall, /title="LINxiansheng"/);
  assert.match(wall, /3 merged PRs/);
  assert.doesNotMatch(wall, /0 commits/);
});

test('同时显示提交与已合并 PR 数量并处理单复数', () => {
  const wall = buildWall([
    {
      login: 'same-author',
      profileUrl: 'https://github.com/same-author',
      avatarUrl: 'https://avatars.githubusercontent.com/u/42?v=4&s=144',
      commitCount: 1,
      mergedPrCount: 1,
    },
  ]);

  assert.match(wall, /<sub>1 commit<br \/>1 merged PR<\/sub>/);
});
