FROM node:22-alpine AS build

WORKDIR /app
COPY services/frontend-dashboard/package.json ./
COPY services/frontend-dashboard/package-lock.json ./
COPY services/frontend-dashboard/tsconfig.json ./
COPY services/frontend-dashboard/vite.config.ts ./
COPY services/frontend-dashboard/index.html ./
COPY services/frontend-dashboard/src ./src
RUN npm ci
RUN npm run build

FROM nginx:1.27-alpine
COPY services/frontend-dashboard/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
