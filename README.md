# 片刻

一个面向个人随笔的 Django 博客：后台写作、Markdown、安全预览、分类标签、搜索、RSS、sitemap、明暗主题和响应式杂志排版。

## 本地启动

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

访问 `http://127.0.0.1:8000/`；写作后台位于 `/studio/`。进入后台后先创建“站点设置”，再创建文章。文章状态设为“已发布”且发布时间不晚于当前时间后才会公开。

后台正文使用所见即所得编辑器。截图、本地图片以及从网页复制的图文可以直接粘贴到正文中；图片会上传到本站的 `media/posts/` 目录并立即显示。单张图片上限为 10 MB，支持 JPEG、PNG、GIF 和 WebP。

首次本地开发先运行 `npm install && npm run vendor` 准备编辑器静态资源。前台已有可直接使用的主题 CSS；若要扩展 Tailwind 工具类，运行 `npm run css`，并在模板中引入生成的 `static/css/tailwind.css`。Docker 镜像会自动完成编辑器资源构建。

## 服务器部署

```bash
cp .env.example .env
# 修改域名和密钥；密钥至少 50 个随机字符
mkdir -p deploy/certs
# 把域名证书链保存为 deploy/certs/fullchain.pem
# 把对应私钥保存为 deploy/certs/privkey.pem
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Web 和 Nginx 容器会共同使用 `.env` 中的 `TIME_ZONE`（默认 `Asia/Shanghai`），因此应用时间与访问日志时间保持一致。修改时区后需要重新创建容器：`docker compose up -d --build --force-recreate`。

部署前先把域名解析到服务器，并使用 Certbot、acme.sh 或证书服务商取得证书。Nginx 只启用 TLS 1.2/1.3，会把 HTTP 自动跳转到 HTTPS；证书续期后执行 `docker compose exec nginx nginx -s reload`。配置启用了 HSTS 的 `includeSubDomains` 和 `preload`，因此该域名及其所有子域都必须始终支持 HTTPS；如果做不到，上线前应同时从 Django 设置和 Nginx 配置中关闭这两个参数。

生产环境使用 SQLite，数据库位于 `data` 具名卷，上传图片位于 `media` 卷。至少定期备份这两个卷；SQLite 在线备份应使用 `sqlite3 /path/to/db.sqlite3 ".backup backup.sqlite3"`，不要在写入期间直接复制数据库文件。若从本地迁移现有内容，请在首次启动前或停掉 `web` 服务后把现有 `db.sqlite3` 导入数据卷。

上线前检查：

```bash
docker compose exec web python manage.py check --deploy
docker compose config
```

不要提交 `.env`、证书私钥、SQLite 数据库或媒体文件。服务器防火墙只需对公网开放 80/443，Gunicorn 和 SQLite 不对公网暴露。
