# Política de dados — Crypto & Binary Intelligence

> Fonte: especificação **v4.1 (13/11/2026), §0, §3, §5, §7, §11 e §17**.
> Fase 0 — GOV-003. Versão 1.0 — 13/11/2026.
> Status: **rascunho aguardando aprovação formal do responsável**
> (ver `governance-checklist.md`).
>
> Esta política é um contrato de dados: define o que o sistema aceita,
> como registra, por quanto tempo guarda e o que faz quando os dados
> são ruins. **Na ausência de dados confiáveis, a decisão correta é
> NÃO OPERAR** (§0, premissa 7; §20, regra final).

## 1. Timestamps

1. **Todos os timestamps internos são UTC.** Nenhum timestamp local
   (de VPS, de cliente ou de exchange sem fuso declarado) entra no
   banco sem conversão explícita para UTC.
2. **Validação obrigatória na ingestão** (§2, camada 2; §5):
   - timestamp ausente, malformado ou fora de faixa plausível →
     registro **rejeitado** e evento registrado em log/auditoria;
   - timestamp no futuro além de uma tolerância documentada por
     conector (a definir por conector na Fase 3/4, nunca presumida) →
     rejeitado;
   - timestamp fora de ordem em relação à sequência do canal →
     tratado como gap/sequência quebrada (ver §5).
3. Cada registro guarda **dois timestamps**: o de origem (da fonte,
   quando existir) e o de recebimento (do sistema). Sinais guardam
   ambos (§9, campos mínimos).
4. Relógio do servidor sincronizado por NTP (§14, INF-002); deriva de
   relógio é métrica de saúde do feed (§5: medir idade da última
   mensagem, sequência, atraso e integridade).

## 2. Granularidade por fonte — não inventar granularidade

1. **Não inventar granularidade** (§3): se a fonte não fornecer
   trades individuais, **não simular ticks nem candles de 1 segundo**.
   Candles próprios só são construídos quando houver trades
   suficientes (§1, objetivo 3).
2. Timeframes suportados (§3): tick/trade; 1s; 5s; 15s; 30s; 1m; 3m;
   5m; 15m; 30m; 1h; 2h; 4h; 6h; 8h; 12h; diário; semanal — **cada
   um só existe para uma fonte se essa fonte o fornecer** (ou se
   puder ser agregado a partir de granularidade mais fina real).
3. Agregação só vai do fino para o grosso (ex.: candles 1m → 5m);
   nunca do grosso para o fino.
4. **API agregadora (ex.: DEX Screener) serve para descoberta e
   triagem; não deve ser presumida como feed de trades em tempo
   real** (§3). Para eventos on-chain, usar RPC, WebSocket ou
   indexador adequado.
5. A granularidade real de cada fonte é registrada na matriz de
   cobertura (GOV-002 / `docs/exchanges.md`) por conector; qualquer
   divergência entre o documentado e o observado é registrada como
   evento de qualidade de dados.

## 3. Retenção (§11)

| Dado | Retenção |
|---|---|
| Trades brutos prioritários | 7 dias |
| Order Book bruto | 2–7 dias |
| Candles 1s | 30 dias |
| Candles 1m | 24 meses |
| Candles 5m | 24 meses |
| Timeframes maiores | 3 anos ou mais |
| Sinais, ordens e auditoria | **permanente**, conforme esta política |

Regras:

1. **Não guardar todos os ticks e books indefinidamente na VPS de
   320 GB** (§1, fora do escopo; §11). Agregação e arquivamento
   externo são necessários; o detalhamento do arquivamento é tarefa
   da Fase 7 (DAT-010).
2. A retenção acima é de **dados brutos prioritários**; nem todos os
   pares/canais precisam ser retidos no nível máximo — o
   monitoramento hierárquico (§4: Discovery até ~2.000 pares, Active
   até ~200 instrumentos, Priority até ~50 ativos) define o que é
   prioritário.
3. Sinais, ordens, fills, posições e trilhas de auditoria têm
   retenção permanente: são a evidência de aceite das fases (§17) e
   a base de reconciliação (§10).
4. Expiração de dados brutos nunca apaga dados agregados (candles)
   nem registros de auditoria.
5. Os prazos acima são os da especificação v4.1 §11; qualquer
   alteração exige revisão desta política e aprovação do responsável.

## 4. Gaps e dados inválidos — rejeitar, nunca presumir

1. **Dados inválidos são rejeitados, nunca presumidos nem
   corrigidos silenciosamente** (§17, Market Data: "Dados inválidos
   rejeitados").
2. Detecção (§5, §7): heartbeat, sequência, snapshot e sincronização
   de Order Book, detecção de gaps, métrica de latência, circuit
   breaker por fonte.
3. Ao detectar gap, latência excessiva ou feed inválido:
   - marcar o feed como **inválido/degradado**;
   - **bloquear novas entradas** (feed inválido bloqueia novas
     entradas — §10; ver `risk-policy.md`);
   - **bloquear sinais** com feed inválido (§5);
   - registrar o evento (gap, mensagens descartadas, atraso de
     candles, qualidade do Order Book — §16);
   - tentar recuperação (reconexão, re-snapshot, backfill a partir
     da fonte, quando a fonte oferecer).
4. **Nunca preencher gaps com dados inventados, interpolados sem
   marcação, ou copiados de outra exchange como se fossem da
   fonte.** Se um backfill for aplicado, o dado reposto é marcado
   como reposto, com origem e instante do reparo registrados.
5. Candles construídos sobre períodos com gaps são marcados como
   incompletos/não confiáveis e não alimentam sinais nem backtests
   sem essa marcação explícita.
6. Uma conexão aberta não significa conexão saudável (§5): saúde é
   medida por idade da última mensagem, sequência, atraso e
   integridade.
7. Preferir **WAIT / NO TRADE** a operar sobre dados ruins (§0,
   premissa 7).

## 5. Normalização e preservação do original

1. Símbolos e mercados normalizados por conector (§2, camada 2;
   §14, CON-003), com o identificador original da fonte preservado.
2. **Payload original preservado** (§14, CEX-005) para auditoria e
   reprocessamento.
3. Erros e respostas padronizados por conector (§14, CON-004);
   deduplicação de trades e eventos (§5, §7, DAT-002).

## 6. Cobertura GOV

Esta política atende **GOV-003** (política de dados: timestamps,
granularidade, retenção, gaps — aceite: contrato de dados).
Mapeamento completo GOV-001 a GOV-007 em
[`governance-checklist.md`](governance-checklist.md).
