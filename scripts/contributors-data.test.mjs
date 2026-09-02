import assert from 'node:assert/strict';
import test from 'node:test';

import { fetchContributors } from './contributors-data.mjs';

function githubUser({ id, login, type = 'User' }) {
  return {
    id,
    login,
    type,
    html_url: `https://github.com/${login}`,
    avatar_url: `https://avatars.githubusercontent.com/u/${id}?v=4`,
  };
}

function createFetch({ commits = [], pulls = [], commitPages, pullPages }) {
  return async (input) => {
    const url = new URL(input);
    const page = Number(url.searchParams.get('page'));

    if (url.pathname.endsWith('/commits')) {
      return Response.json(commitPages?.[page - 1] ?? commits);
    }

    if (url.pathname.endsWith('/pulls')) {
      return Response.json(pullPages?.[page - 1] ?? pulls);
    }

    throw new Error(`未预期的 GitHub API 请求：${url}`);
  };
}

test('提交邮箱未关联时仍通过已合并 PR 收录作者', async () => {
  const lin = githubUser({ id: 18351861, login: 'LINxiansheng' });
  const fetchImpl = createFetch({
    commits: [{ sha: 'unlinked', author: null }],
    pulls: [
      {
        number: 100,
        merged_at: '2026-09-02T06:17:29Z',
        user: lin,
      },
    ],
  });

  const contributors = await fetchContributors('datawhalechina/easy-data-x-ai', {
    fetchImpl,
  });

  assert.deepEqual(contributors, [
    {
      login: 'LINxiansheng',
      profileUrl: 'https://github.com/LINxiansheng',
      avatarUrl: 'https://avatars.githubusercontent.com/u/18351861?v=4&s=144',
      commitCount: 0,
      mergedPrCount: 1,
    },
  ]);
});

test('完整读取提交与已关闭 PR 的后续分页', async () => {
  const directAuthor = githubUser({ id: 1, login: 'direct-author' });
  const lin = githubUser({ id: 18351861, login: 'LINxiansheng' });
  const fetchImpl = createFetch({
    commitPages: [
      Array.from({ length: 100 }, (_, index) => ({
        sha: `commit-${index}`,
        author: directAuthor,
      })),
      [{ sha: 'commit-100', author: directAuthor }],
    ],
    pullPages: [
      Array.from({ length: 100 }, (_, index) => ({
        number: index + 1,
        merged_at: null,
        user: lin,
      })),
      [{ number: 101, merged_at: '2026-09-02T06:17:29Z', user: lin }],
    ],
  });

  const contributors = await fetchContributors('datawhalechina/easy-data-x-ai', {
    fetchImpl,
  });

  assert.deepEqual(
    contributors.map(({ login, commitCount, mergedPrCount }) => ({
      login,
      commitCount,
      mergedPrCount,
    })),
    [
      { login: 'direct-author', commitCount: 101, mergedPrCount: 0 },
      { login: 'LINxiansheng', commitCount: 0, mergedPrCount: 1 },
    ],
  );
});

test('同一 GitHub 用户的提交与已合并 PR 合并为一条记录', async () => {
  const author = githubUser({ id: 42, login: 'same-author' });
  const fetchImpl = createFetch({
    commits: [{ sha: 'commit-1', author }],
    pulls: [
      { number: 1, merged_at: '2026-09-02T01:00:00Z', user: author },
      { number: 2, merged_at: '2026-09-02T02:00:00Z', user: author },
    ],
  });

  const contributors = await fetchContributors('datawhalechina/easy-data-x-ai', {
    fetchImpl,
  });

  assert.equal(contributors.length, 1);
  assert.deepEqual(
    {
      login: contributors[0].login,
      commitCount: contributors[0].commitCount,
      mergedPrCount: contributors[0].mergedPrCount,
    },
    { login: 'same-author', commitCount: 1, mergedPrCount: 2 },
  );
});

test('忽略 Bot、删除账号以及未合并的 PR', async () => {
  const bot = githubUser({ id: 99, login: 'automation[bot]', type: 'Bot' });
  const human = githubUser({ id: 100, login: 'not-merged' });
  const fetchImpl = createFetch({
    commits: [
      { sha: 'unlinked', author: null },
      { sha: 'bot', author: bot },
    ],
    pulls: [
      { number: 1, merged_at: '2026-09-02T01:00:00Z', user: null },
      { number: 2, merged_at: '2026-09-02T02:00:00Z', user: bot },
      { number: 3, merged_at: null, user: human },
    ],
  });

  const contributors = await fetchContributors('datawhalechina/easy-data-x-ai', {
    fetchImpl,
  });

  assert.deepEqual(contributors, []);
});

test('任一 GitHub API 请求失败时不返回部分结果', async () => {
  const author = githubUser({ id: 1, login: 'direct-author' });
  const fetchImpl = async (input) => {
    const url = new URL(input);

    if (url.pathname.endsWith('/commits')) {
      return Response.json([{ sha: 'commit-1', author }]);
    }

    return new Response('pull request access denied', {
      status: 403,
      statusText: 'Forbidden',
    });
  };

  await assert.rejects(
    fetchContributors('datawhalechina/easy-data-x-ai', { fetchImpl }),
    /GitHub API 403 Forbidden: pull request access denied/,
  );
});
