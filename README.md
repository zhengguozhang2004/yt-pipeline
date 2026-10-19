# yt-pipeline

GitHub Actions 云端视频下载管道：在 GitHub 的服务器上下载视频（不受本机网络限制），打包发布到 release，本机通过国内镜像（gh-proxy.com）拉回。

## 使用方法

1. 编辑 `downloads/urls.txt`，每行一个视频链接（YouTube/niconico 等）
2. `git add downloads/urls.txt && git commit && git push`
3. 等 Actions 跑完（约 1-3 分钟）
4. 本机拉回：
   ```
   curl -L -C - -o videos.zip "https://gh-proxy.com/https://github.com/<你的用户名>/<仓库名>/releases/download/latest/videos.zip"
   ```

也可以在 GitHub 网页 Actions 页面点 "Run workflow" 手动输入链接运行。
