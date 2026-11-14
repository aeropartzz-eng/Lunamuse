# Memória QG (MCP)

Protótipo da memória central ("QG do Zero") — interface de tarefas + busca de memória + revisão de propostas.

- Auditoria feita em 2026-11-13: demo com dados falsos, sem backend real; 14 gaps no relatório (workspace/auditoria-memoria-qg.md).
- Regras: FastAPI/Mongo, sem LLM/embeddings/GPU no caminho de leitura, só dados sintéticos nos testes.
- Integração: os 15 MCPs mais estrelados (Context7, Serena, GitHub MCP, etc.), Obsidian, RAG, A2A, Cartographer, claude-mem, Paperclip AI.
- Status: auditoria pronta; o servidor MCP real ainda precisa ser construído.
