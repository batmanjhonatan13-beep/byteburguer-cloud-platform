"""
ByteBurguer Cloud Platform - Microsservico de Pedidos

Responsavel por criar e acompanhar os pedidos das franquias.
Demonstra praticas do Projeto Integrado:
  - API REST versionada (/api/v1)                     -> Projeto de Software
  - Idempotencia por chave unica (sem pedido duplicado) -> Arquitetura/Resiliencia
  - Janela de operacao dos robos                      -> Seguranca e Auditoria
  - Logs estruturados em JSON com id_pedido           -> Observabilidade/Auditoria
  - /health e /metrics                                -> Observabilidade
"""
import json
import logging
import uuid
from datetime import datetime, time, timezone

from flask import Flask, jsonify, request

# ---------------------------------------------------------------- logs (JSON)
logger = logging.getLogger("pedidos")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_evento(evento, **dados):
    """Registra um evento de auditoria em formato JSON estruturado."""
    registro = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "servico": "pedidos",
        "evento": evento,
        **dados,
    }
    logger.info(json.dumps(registro, ensure_ascii=False))


# ------------------------------------------------------------ regras de negocio
CARDAPIO = {
    "byte-classico": 29.90,
    "byte-duplo": 37.90,
    "byte-vegano": 32.90,
    "batata-binaria": 12.90,
    "refri-cloud": 8.90,
}

STATUS_VALIDOS = ["RECEBIDO", "EM_PREPARO", "PRONTO", "ENTREGUE", "CANCELADO"]

# horario de funcionamento padrao da franquia
ABERTURA = time(10, 0)
FECHAMENTO = time(23, 0)


def calcular_total(itens):
    """Soma o valor dos itens do pedido. Lanca ValueError se houver item invalido."""
    if not itens:
        raise ValueError("O pedido precisa ter pelo menos um item.")
    total = 0.0
    for item in itens:
        produto = item.get("produto")
        quantidade = item.get("quantidade", 1)
        if produto not in CARDAPIO:
            raise ValueError(f"Produto inexistente no cardapio: {produto}")
        if not isinstance(quantidade, int) or quantidade <= 0:
            raise ValueError("A quantidade deve ser um inteiro maior que zero.")
        total += CARDAPIO[produto] * quantidade
    return round(total, 2)


def robo_pode_operar(agora, abertura=ABERTURA, fechamento=FECHAMENTO):
    """Seguranca: robos so recebem comandos dentro do horario de funcionamento."""
    return abertura <= agora <= fechamento


# ------------------------------------------------------------------ aplicacao
def create_app():
    app = Flask(__name__)
    app.pedidos = {}          # id_pedido -> pedido (em memoria, apenas para a demo)
    app.chaves = {}           # chave de idempotencia -> id_pedido
    app.metricas = {"pedidos_criados": 0, "pedidos_duplicados_bloqueados": 0,
                    "comandos_robo_bloqueados": 0}

    @app.get("/health")
    def health():
        return jsonify(status="ok", servico="pedidos")

    @app.get("/metrics")
    def metrics():
        linhas = [f"byteburguer_{nome} {valor}" for nome, valor in app.metricas.items()]
        return "\n".join(linhas) + "\n", 200, {"Content-Type": "text/plain"}

    @app.post("/api/v1/pedidos")
    def criar_pedido():
        dados = request.get_json(silent=True) or {}
        chave = request.headers.get("Idempotency-Key")

        # Idempotencia: o mesmo pedido enviado duas vezes nao vira dois lanches
        if chave and chave in app.chaves:
            app.metricas["pedidos_duplicados_bloqueados"] += 1
            existente = app.pedidos[app.chaves[chave]]
            log_evento("pedido_duplicado_bloqueado", id_pedido=existente["id"])
            return jsonify(existente), 200

        try:
            total = calcular_total(dados.get("itens", []))
        except ValueError as erro:
            log_evento("pedido_rejeitado", motivo=str(erro), franquia=dados.get("franquia"))
            return jsonify(erro=str(erro)), 400

        pedido = {
            "id": str(uuid.uuid4()),
            "franquia": dados.get("franquia", "desconhecida"),
            "itens": dados["itens"],
            "total": total,
            "status": "RECEBIDO",
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        app.pedidos[pedido["id"]] = pedido
        if chave:
            app.chaves[chave] = pedido["id"]
        app.metricas["pedidos_criados"] += 1
        log_evento("pedido_criado", id_pedido=pedido["id"], franquia=pedido["franquia"],
                   total=total)
        return jsonify(pedido), 201

    @app.get("/api/v1/pedidos/<id_pedido>")
    def consultar_pedido(id_pedido):
        pedido = app.pedidos.get(id_pedido)
        if not pedido:
            return jsonify(erro="Pedido nao encontrado."), 404
        return jsonify(pedido)

    @app.patch("/api/v1/pedidos/<id_pedido>/status")
    def atualizar_status(id_pedido):
        pedido = app.pedidos.get(id_pedido)
        if not pedido:
            return jsonify(erro="Pedido nao encontrado."), 404
        novo = (request.get_json(silent=True) or {}).get("status")
        if novo not in STATUS_VALIDOS:
            return jsonify(erro=f"Status invalido. Use: {STATUS_VALIDOS}"), 400
        anterior = pedido["status"]
        pedido["status"] = novo
        log_evento("status_alterado", id_pedido=id_pedido, de=anterior, para=novo)
        return jsonify(pedido)

    @app.post("/api/v1/pedidos/<id_pedido>/enviar-cozinha")
    def enviar_para_robo(id_pedido):
        pedido = app.pedidos.get(id_pedido)
        if not pedido:
            return jsonify(erro="Pedido nao encontrado."), 404
        agora = app.config.get("HORA_ATUAL") or datetime.now().time()
        if not robo_pode_operar(agora):
            app.metricas["comandos_robo_bloqueados"] += 1
            log_evento("comando_robo_bloqueado", id_pedido=id_pedido,
                       horario=agora.strftime("%H:%M"), severidade="CRITICA")
            return jsonify(erro="Robo fora da janela de operacao."), 403
        pedido["status"] = "EM_PREPARO"
        log_evento("comando_robo_enviado", id_pedido=id_pedido)
        return jsonify(pedido)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
