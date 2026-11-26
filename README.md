# ByteBurguer Cloud Platform 🍔☁️

Projeto Integrado – Tecnologia em DevOps.

Plataforma DevOps que unifica robôs-cozinheiros, sensores IoT, totens e aplicativo das franquias da ByteBurguer.
Este repositório contém o **microsserviço de Pedidos** (prova de conceito), o **pipeline de CI/CD** e a documentação de arquitetura.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `servico-pedidos/app` | Microsserviço de Pedidos (Python + Flask), API REST `/api/v1` |
| `servico-pedidos/tests` | Testes automatizados (pytest) |
| `servico-pedidos/Dockerfile` | Imagem do container (usuário não-root + healthcheck) |
| `.github/workflows/ci.yml` | Pipeline: lint → testes (cobertura ≥ 80%) → segurança (pip-audit) → build Docker |
| `.github/dependabot.yml` | Verificação semanal de dependências vulneráveis |
| `docs/` | Diagramas de arquitetura e EAP (draw.io) |

## Práticas demonstradas

- **Idempotência**: o cabeçalho `Idempotency-Key` impede pedido duplicado (totens/sensores que reenviam dados).
- **Segurança**: robôs só recebem comando dentro do horário de funcionamento; fora disso, bloqueio + log `CRITICA`.
- **Auditoria/Observabilidade**: logs estruturados em JSON com `id_pedido`; endpoints `/health` e `/metrics`.

## Como rodar localmente

```bash
cd servico-pedidos
pip install -r requirements-dev.txt
pytest -v --cov=app
python -m app.main        # API em http://localhost:8080
```

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Verificação de saúde |
| GET | `/metrics` | Métricas (formato Prometheus) |
| POST | `/api/v1/pedidos` | Cria pedido |
| GET | `/api/v1/pedidos/{id}` | Consulta pedido |
| PATCH | `/api/v1/pedidos/{id}/status` | Atualiza status |
| POST | `/api/v1/pedidos/{id}/enviar-cozinha` | Envia ao robô (respeita a janela de operação) |
