# apps/api — API FastAPI (esqueleto)

Esqueleto do MVP (especificação v4.1, §13). Implementado:

- `GET /health` — health check (usado pelo Docker Compose).
- `GET /` — identificação do serviço.
- `GET /v1/exchanges` — stub do catálogo do primeiro grupo de CEX.
- `GET /v1/exchanges/status` — stub de status de conexão.
- `GET /v1/system/health` — stub de saúde agregada.
- Demais rotas de mercado/inteligência/estratégias/sinais como stubs
  HTTP 501 (`not_implemented`).
- Rotas de execução (`/v1/execution/preview`, `/orders`, `/cancel`)
  **bloqueadas com HTTP 403** — LIVE desabilitado por padrão (§10).
- `POST /v1/execution/kill-switch` — retorna o estado do kill switch
  (armado, sem posições reais no scaffold).

## Trava de segurança

`EXECUTION_MODE` é lido do ambiente. O scaffold só aceita `RESEARCH`:
qualquer outro valor é ignorado e o modo é forçado para `RESEARCH`.
O sistema nunca muda sozinho para LIVE (EXE-014).

## Rodar local (sem Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
EXECUTION_MODE=RESEARCH uvicorn main:app --reload --port 8000
```

Docs interativas: http://localhost:8000/docs
