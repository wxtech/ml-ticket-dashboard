# 工单数据分析仪表盘 - 部署备忘录

## 线上地址

https://wxtech.github.io/ml-ticket-dashboard/

## 仓库

https://github.com/wxtech/ml-ticket-dashboard

## 部署步骤

### 1. 安装 GitHub CLI

```bash
conda install -y -c conda-forge gh
```

### 2. 登录 GitHub

```bash
gh auth login
# 选择 GitHub.com → HTTPS → 粘贴 Personal Access Token
# Token 需要 repo 权限
# https://github.com/settings/tokens
```

### 3. 创建仓库并推送

```bash
cd /opt/devenv/ML/004
gh repo create ml-ticket-dashboard --public --source=. --push
```

### 4. 启用 GitHub Pages

```bash
curl -X POST \
  -H "Authorization: token <YOUR_TOKEN>" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/wxtech/ml-ticket-dashboard/pages \
  -d '{"source":{"branch":"main","path":"/"}}'
```

或在 GitHub 仓库 Settings → Pages → Source 选择 main 分支 / root。

### 5. 将仪表盘设为首页

```bash
git mv output/dashboard.html index.html
git add index.html
git commit -m "feat: add dashboard as index.html for GitHub Pages"
git push
```

## 更新流程

```bash
# 重新生成数据和仪表盘
python scripts/generate_data.py
python scripts/run_all.py

# 提交更新
git add index.html
git commit -m "update dashboard data"
git push
```

页面会在 1-2 分钟内自动更新。

## 注意事项

- `index.html` 是自包含文件（数据已内嵌），无需服务器
- 依赖 CDN 加载 Chart.js 和 DataTables，需联网
- GitHub Pages 免费，无流量限制
- 如需自定义域名，在仓库 Settings → Pages → Custom domain 填写域名
- 访问 https://wxtech.github.io/ml-ticket-dashboard/
