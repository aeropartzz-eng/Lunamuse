# Cronograma — Android dedicado (Galaxy A21s) — AeroPartz

**Objetivo:** um celular Android sempre ligado, em casa, só para o atendimento da AeroPartz — para a Luna atender sem depender do S22 Ultra do Will e sem WhatsApp Web.
**Aparelho:** Samsung Galaxy A21s, com o Will. **Status em 2026-11-13: nada foi feito no aparelho ainda — só existe o plano.**
**Painel:** AI Digital Operator Platform — o A21s está lá como "aguardando conexão". O telefone é o passo final.

## Quem faz o quê
- **Will** — está com o aparelho e o PC fisicamente; executa os passos no celular e no PC; decide a ROM e as contas.
- **Claudinho** — não tem o aparelho e não mexe nele; guia, monta o plano e os comandos (Heimdall/ADB/Termux).
- **Luna** — coordena, opera pelo painel quando o acesso SSH/ADB estiver entregue; atende os compradores.

## O que vai rodar no aparelho
- WhatsApp da loja (85) 99233-3378 — Will responde pelo app quando pode; a Luna/IA só responde se ele não responder em 2–3 minutos. Sem migração total, sem plataforma paga.
- OLX e Mercado Livre (apps).
- Navegador para sites de promoções.
- Depois: multiplicar por 10 agentes em várias frentes (cronograma do Will, a definir).

## Fase 0 — Decisões e pré-requisitos (trava tudo o resto)
Responder antes de tocar no aparelho:
1. Quem está com o aparelho e tem PC (Windows ou Linux) para Heimdall e ADB?
2. Modelo exato do A21s (SM-A217F, /M, /DS...) e versão atual do firmware?
3. O que o agente vai fazer no celular? (WhatsApp da loja, OLX, Mercado Livre, navegador de promoções — confirmado acima.)
4. **Decisão da ROM (pendente do Will):** o combinado é **ROM stock Samsung limpa via ADB, sem root**. O plano do Claudinho é **LineageOS (com suporte oficial pro A21s), sem GApps** — que é o caminho B, só se o Will decidir. Motivo do combinado: ROM customizada pode quebrar o Play Integrity e o WhatsApp recusar o login.
5. Qual número/conta vai no WhatsApp do aparelho (o da loja ou outro)?

## Fase 1 — Preparar o aparelho
- Backup do que houver no A21s; deixar carregando.
- Confirmar modelo e firmware (resposta da Fase 0).
- Ativar opções de desenvolvedor e depuração USB; testar o ADB com o PC.
- Definir onde o aparelho vai ficar ligado (tomada + Wi-Fi estável).

## Fase 2 — ROM (só depois da decisão da Fase 0)
- **Caminho A (combinado):** manter a ROM stock, debloat via ADB (remover apps Samsung desnecessários), sem root, sem custom ROM.
- **Caminho B (se o Will decidir):** instalar LineageOS via Heimdall, sem GApps. Atenção: há relato de bug de rede local nos builds de LineageOS do A21s — testar logo após instalar. Sem GApps não há Play Store.
- Em qualquer caminho: testar o login do WhatsApp antes de seguir.

## Fase 3 — Conectividade
- Wi-Fi configurado; ADB por Wi-Fi; Termux + SSH no aparelho.
- IP fixo/reserva no roteador; carregador sempre ligado.
- Entregar o acesso SSH/ADB para a Luna (o painel sai de "aguardando conexão").
- Teste de reboot: o aparelho volta sozinho e reconecta.

## Fase 4 — Apps e contas
- Instalar e logar: WhatsApp Business, OLX, Mercado Livre, navegador.
- Confirmar que as contas entram e as notificações chegam.

## Fase 5 — Ligar ao painel
- A21s conectado no Operator Platform; agentes (WhatsApp, Messenger) ativos no painel.
- Regras do painel: janela de resposta 3 minutos; checagem a cada 30 minutos; aprovação humana para ações sensíveis.

## Fase 6 — Testes de atendimento
- Responder um comprador de teste pelo WhatsApp e confirmar a resposta no thread.
- Testar queda de Wi-Fi/bateria e volta.
- Confirmar que o Will continua podendo responder pelo app dele (convivência).

## Fase 7 — Operação e escala
- Entrar em operação no atendimento da loja.
- Depois, escalar para os 10 agentes (plano do Will).

## Riscos e notas
- Nada de emulador/virtualização: o WhatsApp detecta e pode banir; aparelho físico em Fortaleza é o caminho.
- A21s não tem DeX — para DeX vai precisar de um S ou A90 pra cima depois.
- Sem root em qualquer caminho.
- O telefone é o passo final do painel — o resto do Operator Platform já está pronto.
