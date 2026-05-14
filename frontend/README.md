# 前端目录说明

`frontend/` 是前端工程的外层目录，真正的 Vite 项目位于 `frontend/vite/`。这样保留外层目录，是为了后续如果拆分管理端、移动端或设计资源时仍有扩展空间。

## 目录约定

- `vite/`：当前正式前端项目。
- `dist/`：`npm run build` 后生成的生产构建产物，由 Docker 中的 Nginx 读取。

## 开发入口

```bash
cd frontend/vite
npm install
npm run dev
```

## 生产构建

```bash
cd frontend/vite
npm run build
```

构建结果会输出到 `frontend/dist`，与 `docker-compose.yml` 中 Nginx 的挂载路径保持一致。
