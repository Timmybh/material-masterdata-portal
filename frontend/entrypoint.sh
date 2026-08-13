#!/bin/sh
set -eu
: "${API_URL:=/api}"
: "${GOOGLE_CLIENT_ID:=}"
envsubst '${API_URL} ${GOOGLE_CLIENT_ID}' < /usr/share/nginx/html/config.template.js > /usr/share/nginx/html/config.js
exec nginx -g 'daemon off;'
