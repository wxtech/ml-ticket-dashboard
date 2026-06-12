# Act 本地运行 GitHub Actions 完整指南

## 什么是 Act？

[nektos/act](https://github.com/nektos/act) 是一个在本地运行 GitHub Actions 的工具。它用 Docker 容器模拟 GitHub 的运行环境，在本地执行 `.github/workflows/` 中定义的 CI 流程。

**核心价值**：不用 push 到 GitHub，就能在本地验证 CI 是否通过。

## 安装

### 方式一：conda 安装（推荐）

```bash
conda install -y -c conda-forge act
```

验证：
```bash
act --version
# act version 0.2.89
```

### 方式二：直接下载二进制

```bash
# Linux x86_64
curl -fsSL https://github.com/nektos/act/releases/latest/download/act_Linux_x86_64.tar.gz | tar -xz -C /usr/local/bin act

# macOS
brew install act
```

### 方式三：从源码编译（需要 Go）

```bash
go install github.com/nektos/act@latest
```

## 前置条件

- Docker 必须安装并运行：`docker --version`
- 首次运行会拉取 Docker 镜像（~2GB），需要网络通畅

## 基本用法

### 运行默认 workflow

```bash
cd /path/to/your/repo
act
```

### 指定 event 触发

```bash
act push              # 模拟 push 事件
act pull_request      # 模拟 PR 事件
act schedule          # 模拟定时触发
act workflow_dispatch  # 模拟手动触发
```

### 选择 job 运行

```bash
act -j build          # 只运行名为 build 的 job
act -j test           # 只运行名为 test 的 job
```

### 列出可用的 workflow 和 job

```bash
act -l                # 列出所有 workflow
act -l --list        # 详细列表
```

## 镜像选择

Act 使用 Docker 镜像来模拟 GitHub Actions 运行环境：

| 镜像 | 大小 | 说明 |
|------|------|------|
| `catthehacker/ubuntu:act-latest` | ~2GB | 完整 Ubuntu，最接近 GitHub 环境 |
| `catthehacker/ubuntu:act-22.04` | ~1.5GB | Ubuntu 22.04 版本 |
| `catthehacker/ubuntu:act-20.04` | ~1.2GB | Ubuntu 20.04 版本 |
| `catthehacker/ubuntu:act-micro` | ~200MB | 精简版，无 Node.js |
| `catthehacker/ubuntu:act-nosync` | ~1GB | 不同步文件系统 |

### 指定镜像

```bash
# 使用指定镜像
act -P ubuntu-latest=catthehacker/ubuntu:act-latest

# 使用精简镜像（需要 Node.js 的 action 会失败）
act -P ubuntu-latest=catthehacker/ubuntu:act-micro

# 不同 OS 使用不同镜像
act -P ubuntu-latest=catthehacker/ubuntu:act-latest -P ubuntu-22.04=catthehacker/ubuntu:act-22.04
```

### 预拉取镜像

```bash
docker pull catthehacker/ubuntu:act-latest
```

## 常用参数

```bash
# 详细输出（调试用）
act -v

# 非交互模式（CI/脚本中使用）
act -n

# 绑定当前目录到容器（避免文件复制）
act --bind

# 使用容器网络
act --network host

# 忽略已缓存的 action
act --no-cache-dir

# 设置环境变量
act -s MY_VAR=value

# 使用 secret
act --secret-file .env
act -s GITHUB_TOKEN=xxx

# 模拟特定平台
act -P ubuntu-latest=catthehacker/ubuntu:act-latest --container-architecture linux/amd64
```

## 常见问题及解决

### 问题1：Docker 镜像拉取失败

**症状**：
```
Error response from daemon: failed to resolve reference "docker.io/catthehacker/ubuntu:act-latest"
```

**原因**：网络无法访问 Docker Hub，或国内镜像源不可用。

**解决方案**：

方案A — 换镜像源：
```bash
sudo tee /etc/docker/daemon.json << 'EOF'
{
    "registry-mirrors": [
        "https://docker.1ms.run",
        "https://docker.xuanyuan.me"
    ]
}
EOF
sudo systemctl restart docker
```

方案B — 手动拉取后离线使用：
```bash
# 在能联网的机器上拉取
docker pull catthehacker/ubuntu:act-latest
docker save catthehacker/ubuntu:act-latest -o act-latest.tar

# 在目标机器上加载
docker load -i act-latest.tar

# 使用本地镜像
act -P ubuntu-latest=catthehacker/ubuntu:act-latest --pull=false
```

方案C — 使用其他镜像源的版本：
```bash
docker pull ghcr.io/catthehacker/ubuntu:act-latest
act -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:act-latest
```

### 问题2：容器内无法访问外网

**症状**：`git clone` 超时，无法下载 action。

**原因**：Docker 容器网络配置问题。

**解决方案**：

方案A — 使用宿主机网络：
```bash
act --network host
```

方案B — 配置 Docker DNS：
```bash
sudo tee /etc/docker/daemon.json << 'EOF'
{
    "dns": ["8.8.8.8", "114.114.114.114"]
}
EOF
sudo systemctl restart docker
```

### 问题3：`node` 命令找不到

**症状**：
```
exec: "node": executable file not found in $PATH
```

**原因**：使用了精简镜像（act-micro），没有 Node.js。

**解决方案**：
```bash
# 换用完整镜像
act -P ubuntu-latest=catthehacker/ubuntu:act-latest
```

### 问题4：文件权限问题

**症状**：容器内文件权限错误，无法写入。

**解决方案**：
```bash
# 使用 --bind 直接挂载当前目录
act --bind

# 或在 workflow 中添加权限设置
# 在 .github/workflows/ci.yml 的 job 级别添加：
# permissions:
#   contents: write
```

### 问题5：缓存导致旧代码运行

**症状**：修改代码后 act 仍运行旧版本。

**解决方案**：
```bash
# 清除 act 缓存
act --no-cache-dir

# 或清除 Docker 缓存
docker system prune -f
```

### 问题6：ARM 架构（Apple Silicon）问题

**症状**：在 M1/M2 Mac 上运行报架构不兼容。

**解决方案**：
```bash
# 指定平台
act --container-architecture linux/amd64

# 或使用 ARM 兼容镜像
act -P ubuntu-latest=catthehacker/ubuntu:act-latest --container-architecture linux/arm64
```

## 本项目使用示例

### 首次运行

```bash
cd /opt/devenv/ML/004

# 1. 安装 act
conda install -y -c conda-forge act

# 2. 拉取镜像（需要网络通畅）
docker pull catthehacker/ubuntu:act-latest

# 3. 运行 CI
act -P ubuntu-latest=catthehacker/ubuntu:act-latest
```

### 日常使用

```bash
# 运行完整 CI
act -P ubuntu-latest=catthehacker/ubuntu:act-latest --pull=false

# 跳过 Docker 拉取（镜像已缓存）
act -P ubuntu-latest=catthehacker/ubuntu:act-latest --pull=false

# 调试模式（详细输出）
act -v -P ubuntu-latest=catthehacker/ubuntu:act-latest
```

### 本项目的 CI 流程

`.github/workflows/ci.yml` 定义了以下步骤：

```
1. checkout          — 检出代码
2. setup-python      — 安装 Python 3.12
3. install deps      — pip install -r requirements.txt
4. generate data     — python scripts/generate_data.py
5. anomaly detection — python src/anomaly_detection.py
6. risk scoring      — python src/risk_scoring.py
7. inventory forecast — python src/inventory_forecast.py
8. dashboard         — python scripts/dashboard.py
9. verify outputs    — 检查输出文件存在
10. verify data      — 检查数据完整性
11. charts           — python scripts/visualize.py
12. verify charts    — 检查图表文件
```

## Act vs GitHub Actions 对比

| | Act（本地） | GitHub Actions（线上） |
|---|---|---|
| **运行环境** | 本地 Docker 容器 | GitHub 云端 VM |
| **网络** | 依赖本地网络 | GitHub 网络 |
| **速度** | 取决于本地机器 | GitHub 服务器 |
| **费用** | 免费 | 免费（公开仓库） |
| **适合场景** | 调试 CI 配置 | 日常 CI/CD |

## 参考链接

- Act 官方文档：https://nektos.github.io/act/
- Act GitHub 仓库：https://github.com/nektos/act
- GitHub Actions 文档：https://docs.github.com/en/actions
- Docker Hub 镜像：https://hub.docker.com/r/catthehacker/ubuntu
