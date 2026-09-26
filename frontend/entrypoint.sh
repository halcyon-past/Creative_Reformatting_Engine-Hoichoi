#!/bin/sh
set -e

if [ -f /etc/letsencrypt/live/cre-hoichoi.aritro.cloud/fullchain.pem ]; then
  echo "Found SSL certificate; enabling HTTPS configuration."
  cp /etc/nginx/conf.d/nginx-ssl.conf /etc/nginx/conf.d/default.conf
else
  echo "No SSL certificate found; running standard HTTP configuration."
fi
