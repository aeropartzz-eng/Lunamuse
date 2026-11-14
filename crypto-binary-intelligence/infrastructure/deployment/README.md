# infrastructure/deployment — Deploy na VPS (Fase 1)

Referência do documento (§11): VPS Linux, 4 vCPU, 8 GB RAM, SSD ~320 GB,
Ubuntu Server LTS, Docker Engine + Docker Compose. Estimativa: ~US$ 84/mês
(VPS) + ~US$ 3/mês (Object Storage 100 GB) — confirmar plano, região,
franquia, impostos e câmbio antes de contratar.

Checklist (INF-001…INF-008):
1. Contratar a VPS e confirmar expansão.
2. Ubuntu LTS atualizado, usuário não root, NTP.
3. Segurança: SSH por chave, root por senha desabilitado, firewall,
   portas limitadas (INF-003).
4. Domínio + HTTPS (Caddy) — INF-004. (O Caddy entra no compose quando
   houver domínio; em desenvolvimento as portas ficam em 127.0.0.1.)
5. Docker Engine + Compose (INF-005).
6. Repositório Git privado com este scaffold (INF-006).
7. Ambientes development/staging/production com credenciais separadas
   (INF-007).
8. Backup do banco + Object Storage + teste de restauração (INF-008).
