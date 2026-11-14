# Revisão regulatória — Crypto & Binary Intelligence

> Fonte: especificação **v4.1 (13/11/2026), §0 (premissa 5), §1, §3,
> §10, §14 (Fase 0, GOV-007; semana 22) e §18**.
> Fase 0 — GOV-007. Versão 1.0 — 13/11/2026.
> Status: **rascunho aguardando aprovação formal do responsável e
> validação jurídica externa** (ver `governance-checklist.md`).
>
> **Este documento não é parecer jurídico.** É um mapa de
> verificações e bloqueios. A decisão jurídica final cabe a
> profissional habilitado, antes de qualquer execução real — em
> especial no segmento de binárias.

## 1. Princípios

1. **A presença de uma plataforma no catálogo não garante
   disponibilidade regional de todos os produtos** (§3): cada
   conector precisa verificar documentação, permissões,
   elegibilidade, rate limits e condições de uso.
2. **Não contornar termos de uso, bloqueios ou controles das
   plataformas** (§1, fora do escopo inicial).
3. Execução real exige aprovação **regulatória**, além de técnica,
   estatística e operacional, mais autorização expressa do
   responsável (§0, premissa 4).
4. Na dúvida, o padrão é **bloquear a integração** e manter o
   segmento em pesquisa/simulação.

## 2. Matriz de verificação por plataforma (GOV-007)

Para **cada** plataforma antes de qualquer integração ativa
(conexão de dados com potencial de execução, ou qualquer uso além
de leitura pública documentada), verificar e registrar:

| Item | O que verificar | Evidência |
|---|---|---|
| Oferta | Quais produtos a plataforma oferece e se o produto pretendido existe de fato | Link da documentação oficial + data da consulta |
| Elegibilidade | Se o produto está disponível para a jurisdição do responsável (Brasil) e para o tipo de conta | Termos da plataforma / página de elegibilidade |
| Termos de uso | Se o uso via API é permitido, e em que condições (rate limits, uso comercial, automação) | Trecho dos termos + versão/data |
| API oficial | Se existe API oficial documentada para a operação pretendida | Link da documentação da API |
| Custódia/conta | Requisitos de conta, KYC e permissões de chave | Documentação da plataforma |
| Status | APROVADA / EM REVISÃO / BLOQUEADA para integração | Registro com data e responsável |

**Regra: plataforma sem verificação registrada = BLOQUEADA para
integração.** Nenhuma integração irregular é ativada para "testar
depois".

### 2.1 Plataformas do primeiro grupo (CEX — §3)

Binance, Bybit, OKX, Coinbase Advanced, Kraken, Bitget, Gate.io —
a verificação é feita por conector, nas Fases 4–5, e registrada na
matriz de conectores (CEX-012).

### 2.2 Expansão (CEX — §3)

KuCoin, MEXC, BingX, Bitfinex, HTX, Crypto.com Exchange — mesma
verificação antes de qualquer conector (CEX-011).

### 2.3 DEX / on-chain (§3)

DEX Screener, PancakeSwap, Raydium, Uniswap, Jupiter, RPCs (BNB
Chain, Solana, Ethereum, Base), Birdeye, Helius e outros — verificar
termos de uso dos provedores e a licitude da interação (ex.: swaps
via contrato) antes da integração; execução DEX segue as regras da
`execution-policy.md` (serviço e carteira separados, Crypto Shield
obrigatório).

## 3. Opções binárias — isolamento e bloqueio

1. **Binárias isoladas do motor cripto** (§0, premissa 5; §1; §10).
   O módulo de binárias é de **pesquisa e validação**; estratégias
   BIN-001 a BIN-016 (§6) são de pesquisa/simulação.
2. **Execução real só após validação jurídica** da plataforma, da
   API, da origem do preço e das regras de liquidação (§0,
   premissa 5).
3. Antes de qualquer execução em binárias, validar e documentar
   (§10): legalidade, plataforma, API oficial, origem do preço,
   feed de liquidação, timestamp, arredondamento, vencimento,
   payout, empate e cancelamento.
4. **Se não for possível validar, permitir pesquisa e simulação, mas
   bloquear execução** (§10).
5. **Automação de binárias por navegador como substituto de API
   oficial está fora do escopo** (§1) — proibida.
6. Semana 22 da expansão: relatório de viabilidade do feed binário
   (admissibilidade da plataforma, origem do preço, payout,
   vencimento, liquidação); **execução bloqueada se houver
   lacunas**.
7. Feed de plataforma binária só é usado se **legítimo, documentado
   e verificável** (§2, camada 1).

## 4. Referências regulatórias (§18)

- **CVM** (Comissão de Valores Mobiliários — Brasil):
  <https://www.gov.br/cvm/pt-br>
- **CFTC** (Commodity Futures Trading Commission — EUA):
  <https://www.cftc.gov/>

Estas referências são pontos de partida para consulta. A
aplicabilidade de cada norma ao caso concreto (oferta de produtos,
jurisdição, tipo de conta, distribuição de sinais) deve ser avaliada
por profissional habilitado — **não presumir** que um produto
ofertado no exterior seja ofertável no Brasil, nem que a ausência de
vedação expressa seja autorização.

## 5. Distribuição de sinais

Sinais distribuídos por Telegram, WhatsApp Business oficial e painel
web (§9) não são recomendação de investimento. Qualquer texto de
sinal ou material de divulgação deve:

1. apresentar a precisão sempre acompanhada de cobertura,
   expectativa, custos, intervalo de confiança e desempenho fora da
   amostra (ver `protocol-85.md`);
2. nunca apresentar a meta de 85% como promessa de acerto, lucro ou
   rentabilidade;
3. identificar o sinal como resultado de pesquisa/sistema
   automatizado, com validade e risco explícitos (§9, campos
   mínimos).

## 6. Cobertura GOV

Esta revisão atende **GOV-007** (revisão regulatória: identificar
plataformas, verificar oferta e elegibilidade, bloquear integração
irregular — aceite: matriz jurídica).
Mapeamento completo GOV-001 a GOV-007 em
[`governance-checklist.md`](governance-checklist.md).
