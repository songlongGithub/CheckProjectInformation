# ---------- 前端构建 ----------
FROM node:18-alpine AS frontend
WORKDIR /app/web_frontend
COPY web_frontend/package*.json ./
RUN npm install
COPY web_frontend/ .
RUN npm run build

# ---------- 后端镜像 ----------
FROM python:3.11-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend /app/web_frontend/dist ./web_frontend/dist
EXPOSE 8000
CMD ["uvicorn", "web_backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
