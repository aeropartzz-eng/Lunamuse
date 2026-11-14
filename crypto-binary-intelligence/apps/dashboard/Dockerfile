FROM nginx:alpine

# Página placeholder estática (Fase 14 — SIG-006 implementa o painel real)
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
