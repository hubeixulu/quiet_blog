FROM nginx:1.30.3-alpine

RUN sed -i 's|https*://dl-cdn.alpinelinux.org/alpine|https://mirrors.aliyun.com/alpine|g' /etc/apk/repositories \
    && apk add --no-cache tzdata
