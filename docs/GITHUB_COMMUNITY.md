# GitHub community surfaces (Wiki · Pages · Discussions)

QorTroller is the **parent / truth-plane** project. Qoresence is the sibling **observation-plane** product.

In-repo content lives under:

- `site/` — GitHub Pages landing (do **not** point Pages at the whole `docs/` tree)
- `docs/wiki/` — wiki source
- `docs/discussions/` — discussion drafts

## 1. Enable features (repo owner) — required once

**https://github.com/ConWan30/QorTroller/settings**

| Feature | Path | Action |
|---------|------|--------|
| **Wiki** | General → Features | ☑ Wikis |
| **Discussions** | General → Features | ☑ Discussions |
| **Pages** | Pages | Source: **GitHub Actions** |

With an admin-scoped token (env-only, never committed):

```powershell
gh repo edit ConWan30/QorTroller --enable-wiki --enable-discussions --homepage "https://conwan30.github.io/QorTroller/"
```

## 2. Publish Wiki from `docs/wiki/`

```powershell
.\scripts\publish_wiki.ps1
```

## 3. Publish Discussions

```powershell
.\scripts\publish_discussions.ps1
```

## 4. Pages

Site URL: **https://conwan30.github.io/QorTroller/**

Landing file: `site/index.html`. Workflow: `.github/workflows/pages.yml` uploads `site/` only so operator runbooks in `docs/` are not the public homepage.

## 5. Secrets

Set `GH_TOKEN` or `GITHUB_TOKEN` in the local environment. Never write a PAT into the repo, README, Pages, or a discussion.
