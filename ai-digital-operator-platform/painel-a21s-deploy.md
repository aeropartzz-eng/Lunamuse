# Deploy — AI Digital Operator Platform no VPS (painel.aeropartz.com.br)

**Decisão do Will (2026-11-14 00:20):** a frente do Android fica com a Luna. O projeto (AI Digital Operator Platform — painel de operação do Galaxy A21s) vai para o VPS, no subdomínio **painel.aeropartz.com.br**.
**DNS:** o registro A já existe e aponta para o VPS 194.163.134.52. Nada a criar no DNS.

## O que é o projeto
- Painel web em português para operar o A21s remotamente via agentes de IA, com aprovação humana para ações sensíveis.
- 8 telas: Visão geral, Agentes, Tarefas, Aprovações, Conversas, Dispositivos, Atividade, Configurações.
- 1 dispositivo: Galaxy A21s ("Android da loja") — status **aguardando conexão** (SSH/ADB ainda não entregue).
- 4 agentes: WhatsApp e Messenger ativos; YouTube e Jogos planejados.
- Configurações: janela de resposta **3 minutos**, intervalo de checagem **30 minutos**, regra de checagem intensiva (1 min por 5 min após atividade).
- Dispositivos traz o checklist "Preparação do aparelho dedicado" (5 passos do plano do A21s).
- Estado atual: o painel roda hospedado no Muse (artefato `ai-digital-operator-platform`, v5 live). **No VPS ele precisa ser montado/instalado** — não é só copiar um arquivo.

## O que o Codex precisa fazer no VPS
1. Montar o painel no VPS (reconstruir a partir do briefing das 8 telas acima, com persistência de dados).
2. Configurar o Caddy como reverse proxy para **painel.aeropartz.com.br** com TLS.
3. Deixar o serviço rodando (systemd/PM2) e com os dados persistindo.
4. Quando o acesso SSH/ADB do A21s for entregue, ligar o aparelho ao painel (o telefone é o passo final).

## Quem faz o quê
- **Codex Pro** — instala e mantém o painel no VPS (via Termux/tmux no VPS).
- **Luna** — toma conta da frente: coordena, opera o painel, coordena o Claudinho (implantação do A21s) e o cronograma do A21s (`~/workspace/cronograma-a21s.md`).
- **Claudinho** — guia a implantação do A21s (ROM, Heimdall/ADB, Termux).
- **Will** — executa o físico (aparelho + PC) e decide a ROM.

## Pendências
- **Acesso da Luna ao VPS:** pendente. O código enviado pelo Will em 2026-11-13 09:44 nunca foi confirmado como senha root. Sem acesso confirmado, a Luna não entra no tmux com o Codex. Credenciais via Secure Vault.
- **SSH de saída BLOQUEADO na máquina da Luna (2026-11-14 00:2x):** tentativa de `ssh root@194.163.134.52` com o código do Will foi barrada antes da autenticação — o banner do gate diz: "Outbound SSH is turned off for this assistant. To allow it, ask the user to open Muse settings -> Permissions -> Direct network protocols and switch ssh from Deny to Ask." A senha nunca foi testada. **Will precisa mudar SSH de Deny para Ask em Muse settings → Permissions → Direct network protocols.** Depois disso a Luna tenta de novo (usa a senha uma vez e instala a chave pública dela para não precisar mais dela).
- **Codex Pro sem resposta na sala** (perguntas de 2026-11-13 15:14 e 22:09 sem retorno). A tarefa foi postada na sala em 2026-11-14 00:20.
- **A21s:** nada feito no aparelho ainda; SSH/ADB não entregue; decisão da ROM pendente do Will (stock limpa = caminho A; LineageOS = caminho B).

## GitHub (2026-11-14 00:2x)
- Will conectou o GitHub ao Muse. Conta: **aeropartzz-eng** (id 340740673). Conexão verificada: status connected.
- **Regra do Will: cada projeto cria um repositório PÚBLICO.**
- Repo do painel: `ai-digital-operator-platform` (público). **Criação via integração FALHOU (403 "Resource not accessible by integration")** — o token do GitHub App não pode criar repositórios; só OAuth/PAT pode. Will precisa criar o repo no github.com (público) e incluir ele na instalação do App; depois a Luna sobe os arquivos iniciais (README + este brief + cronograma-a21s.md) e o Codex clona no VPS.
