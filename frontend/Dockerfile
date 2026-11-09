# ---------------------------------------------------------------------------
# RentEase - Web tier (static site + reverse proxy on Nginx)
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine

# Where /api requests are forwarded. Override at run time, e.g.
#   docker run -e BACKEND_URL=http://internal-alb-xxxx.elb.amazonaws.com ...
ENV BACKEND_URL=http://backend:5000 \
    NGINX_RESOLVER=127.0.0.11

# The nginx image renders /etc/nginx/templates/*.template into conf.d at start-up.
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Static site.
COPY . /usr/share/nginx/html
RUN rm -f /usr/share/nginx/html/nginx.conf.template
# In the container the browser always calls the API through this Nginx,
# so force API_BASE to "/api" regardless of the local development setting.
RUN printf 'window.RENTEASE_CONFIG = {\n  API_BASE: "/api",\n};\n' > /usr/share/nginx/html/assets/js/config.js

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
