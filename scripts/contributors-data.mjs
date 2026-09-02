const PAGE_SIZE = 100;

function contributorKey(user) {
  return user.id ? `user:${user.id}` : `login:${user.login.toLowerCase()}`;
}

function ensureContributor(byUser, user) {
  const key = contributorKey(user);
  const existing = byUser.get(key);
  if (existing) {
    return existing;
  }

  const contributor = {
    login: user.login,
    profileUrl: user.html_url,
    avatarUrl: `${user.avatar_url}${user.avatar_url.includes('?') ? '&' : '?'}s=144`,
    commitCount: 0,
    mergedPrCount: 0,
  };
  byUser.set(key, contributor);
  return contributor;
}

async function requestPage(url, { fetchImpl, headers }) {
  const response = await fetchImpl(url, { headers });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`GitHub API ${response.status} ${response.statusText}: ${body}`);
  }

  const items = await response.json();
  if (!Array.isArray(items)) {
    throw new Error(`GitHub API 返回了无效列表：${url}`);
  }

  return items;
}

async function fetchAllPages(url, options) {
  const items = [];

  for (let page = 1; ; page += 1) {
    const separator = url.includes('?') ? '&' : '?';
    const pageItems = await requestPage(
      `${url}${separator}per_page=${PAGE_SIZE}&page=${page}`,
      options,
    );
    items.push(...pageItems);

    if (pageItems.length < PAGE_SIZE) {
      return items;
    }
  }
}

export async function fetchContributors(
  repoSlug,
  {
    fetchImpl = fetch,
    token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN,
  } = {},
) {
  const headers = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'easy-data-x-ai-contributor-wall',
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const apiRoot = `https://api.github.com/repos/${repoSlug}`;
  const [commits, pulls] = await Promise.all([
    fetchAllPages(`${apiRoot}/commits`, { fetchImpl, headers }),
    fetchAllPages(
      `${apiRoot}/pulls?state=closed&sort=created&direction=asc`,
      { fetchImpl, headers },
    ),
  ]);
  const byUser = new Map();

  for (const commit of commits) {
    const author = commit?.author;
    if (!author?.login || author.type !== 'User') {
      continue;
    }

    ensureContributor(byUser, author).commitCount += 1;
  }

  for (const pull of pulls) {
    const author = pull?.user;
    if (!pull?.merged_at || !author?.login || author.type !== 'User') {
      continue;
    }

    ensureContributor(byUser, author).mergedPrCount += 1;
  }

  return [...byUser.values()].sort(
    (a, b) => b.commitCount - a.commitCount
      || b.mergedPrCount - a.mergedPrCount
      || a.login.localeCompare(b.login),
  );
}
