"""Sentinela: o agente que vigia a carteira e avisa sobre o próximo aporte.

A cada ciclo (de hora em hora, por padrão) ele:
  1. Confere pagamentos do Mercado Pago e libera assinaturas pagas.
  2. Para cada pessoa com o aviso vencido (semanal ou diário, conforme o plano),
     monta o radar da carteira: preço justo, preço de entrada, momento técnico e
     proventos, divide o aporte do mês em cotas e escreve a dica (com IA quando o
     plano inclui; senão, com um texto montado pelas regras).
  3. Avisa sobre datas "com" que chegam nos próximos 3 dias.
  4. Executa as ordens limitadas da carteira simulada que alcançaram o preço.
  5. Entrega tudo na caixa de avisos do app e, se configurado, por e-mail e WhatsApp.

Roda sozinho junto do app (``iniciar_automatico``) ou como comando:
    chronotrade-agente agora           # um ciclo, já
    chronotrade-agente agora --forcar  # manda a dica mesmo que não esteja na hora
    chronotrade-agente loop            # fica rodando (para o Docker)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from chronotrade import agenda, avisos, calculos, planos, radar as radar_mod
from chronotrade.calculos import brl, pct
from chronotrade.carteira import Carteira, pasta_dados
from chronotrade.legal import AVISO_CURTO
from chronotrade.mercado import DadosAtivo, carregar_ativo, ticker_curto

log = logging.getLogger("chronotrade.sentinela")
EMAIL_LOCAL = "local"
FREQUENCIA = {"diario": timedelta(hours=20), "semanal": timedelta(days=6, hours=20)}


@dataclass
class Dica:
    titulo: str
    texto: str
    compras: list[dict] = field(default_factory=list)
    sobra: float = 0.0
    proventos: list[agenda.Evento] = field(default_factory=list)
    redigida_por_ia: bool = False


def _carteira_de(pasta: Path) -> Carteira | None:
    arquivo = pasta / "carteira.json"
    if not arquivo.exists():
        return None
    c = Carteira.carregar(arquivo)
    return c if (c.posicoes or c.observar) else None


def montar_dica(carteira: Carteira, obter: Callable[[str], DadosAtivo], hoje: date | None = None,
                usar_tecnica: bool = True) -> Dica:
    """Monta a dica do próximo aporte a partir das mesmas regras da tela Próximo Aporte."""
    hoje = hoje or date.today()
    radar = radar_mod.montar(carteira, obter, hoje=hoje)
    dinheiro = carteira.aporte_mensal + carteira.caixa
    base = radar if usar_tecnica or radar.empty else radar.drop(columns="fator_tecnico")
    compras, sobra = calculos.dividir_aporte(base, dinheiro, carteira.metas_classe) if not radar.empty else (pd.DataFrame(), dinheiro)

    eventos: list[agenda.Evento] = []
    for p in carteira.posicoes:
        d = obter(p.ticker)
        eventos += [e for e in agenda.prever(p.ticker, d.dividendos, p.quantidade, hoje, meses=1,
                                             confirmado=d.proximo_provento)
                    if e.data <= hoje + timedelta(days=30)]
    eventos.sort(key=lambda e: e.data)

    linhas = [f"Aporte do mês: {brl(dinheiro, 0)} (aporte de {brl(carteira.aporte_mensal, 0)} + caixa)."]
    if compras.empty:
        linhas.append("Nenhum ativo do seu radar está abaixo do preço justo agora. "
                      "Uma opção é guardar o dinheiro em caixa e esperar preços melhores.")
    else:
        linhas.append("Divisão sugerida pelas suas regras:")
        for _, c in compras.iterrows():
            info = radar[radar["ativo"] == c["ativo"]].iloc[0]
            motivo = f"{pct(info['potencial'], 0)} abaixo do preço justo" if pd.notna(info["potencial"]) else ""
            if usar_tecnica and info["momento"] != "Sem histórico":
                motivo += f", momento técnico {info['momento'].lower()}"
            cotas = int(c["cotas"])
            linhas.append(f"• {cotas} {'cota' if cotas == 1 else 'cotas'} de {c['ativo']} ({brl(c['valor_compra'])}): {motivo}")
        if sobra > 1:
            linhas.append(f"Sobra para o caixa: {brl(sobra)}.")
    atencao = radar[(radar["na_carteira"]) & (radar["situacao"] == calculos.ACIMA_JUSTO)]
    if not atencao.empty:
        linhas.append("Acima do preço justo (evite reforçar agora): " + ", ".join(atencao["ativo"].head(4)) + ".")
    if eventos:
        linhas.append("Próximos proventos (data com): " + "; ".join(
            f"{ticker_curto(e.ticker)} em {e.data:%d/%m} (~{brl(e.total)}, {e.situacao.lower()})" for e in eventos[:5]) + ".")
    linhas.append(AVISO_CURTO)
    return Dica(titulo=f"Dica do próximo aporte, {hoje:%d/%m}", texto="\n".join(linhas),
                compras=compras.to_dict("records") if not compras.empty else [], sobra=sobra, proventos=eventos)


def redigir_com_ia(dica: Dica, nome: str = "") -> str | None:
    """Pede ao modelo de IA um texto curto e claro com os mesmos números. Devolve None se não der."""
    try:
        from chronotrade.motor_ia import chave_configurada, configuracao_do_ambiente
        from tradingagents.llm_clients.factory import create_llm_client

        cfg = configuracao_do_ambiente()
        if not chave_configurada(cfg.provedor) or not cfg.modelo_rapido:
            return None
        llm = create_llm_client(cfg.provedor, cfg.modelo_rapido).get_llm()
        pedido = (
            "Você escreve a mensagem semanal de um app de carteira de dividendos para um investidor brasileiro "
            f"leigo{', chamado ' + nome.split()[0] if nome else ''}. Reescreva os dados abaixo numa mensagem "
            "curta (até 900 caracteres), em português do Brasil, tom amigável e direto. Use exatamente os números "
            "e ativos dados, sem inventar nada, sem prometer ganhos e sem dizer 'compre' como ordem: apresente "
            "como o resultado das regras que a própria pessoa configurou. Termine com esta frase, sem mudar: "
            f'"{AVISO_CURTO}"\n\nDados:\n{dica.texto}'
        )
        resposta = llm.invoke(pedido)
        texto = resposta.content if isinstance(resposta.content, str) else str(resposta.content)
        texto = texto.strip()
        if AVISO_CURTO not in texto:  # o aviso legal nunca pode faltar
            texto += "\n\n" + AVISO_CURTO
        return texto if len(texto) > 80 else None
    except Exception as erro:
        log.info("IA indisponível para redigir a dica: %s", erro)
        return None


# ---------------------------------------------------------------------------
# Ciclo
# ---------------------------------------------------------------------------


@dataclass
class Pessoa:
    email: str
    nome: str
    plano: str
    pasta: Path
    whatsapp: str = ""
    aviso_email: bool = False
    aviso_whatsapp: bool = False
    admin: bool = False


def _pessoas(contas) -> list[Pessoa]:
    if contas is None:  # modo pessoal: um usuário só, com tudo liberado
        destino = os.environ.get("CHRONOTRADE_AVISO_EMAIL", "")
        return [Pessoa(EMAIL_LOCAL, "", "premium", pasta_dados(), aviso_email=bool(destino))]
    pessoas = []
    for u in contas.listar():
        if not u.pode_usar():
            continue
        pessoas.append(Pessoa(u.email, u.nome, u.plano_efetivo, pasta_dados() / "usuarios" / u.id_pasta,
                              u.whatsapp, u.aviso_email, u.aviso_whatsapp, u.admin))
    return pessoas


def _entregar(caixa: avisos.CaixaDeAvisos, p: Pessoa, tipo: str, titulo: str, texto: str, canais: bool = True) -> None:
    id_ = caixa.criar(p.email, tipo, titulo, texto)
    if not canais:
        return
    envios = []
    destino_email = os.environ.get("CHRONOTRADE_AVISO_EMAIL") if p.email == EMAIL_LOCAL else p.email
    if p.aviso_email and destino_email and planos.libera(p.plano, "avisos_email"):
        envios.append("e-mail: " + avisos.enviar_email(destino_email, f"Chrono Trade: {titulo}", texto))
    if p.aviso_whatsapp and p.whatsapp and planos.libera(p.plano, "avisos_whatsapp"):
        envios.append("WhatsApp: " + avisos.enviar_whatsapp(p.whatsapp, f"{titulo}\n\n{texto}"))
    if envios:
        caixa.anotar_envio(id_, "; ".join(envios))


def ciclo(contas=None, caixa: avisos.CaixaDeAvisos | None = None, cobrancas=None, agora: datetime | None = None,
          obter: Callable[[str], DadosAtivo] | None = None, forcar: bool = False, so_email: str | None = None,
          usar_ia: bool = True, so_pagamentos: bool = False) -> dict:
    """Um ciclo completo do agente. Devolve um resumo do que foi feito."""
    agora = agora or datetime.now()
    caixa = caixa or avisos.CaixaDeAvisos(pasta_dados() / "contas.db")
    memoria: dict[str, DadosAtivo] = {}

    def buscar(ticker: str) -> DadosAtivo:
        if ticker not in memoria:
            memoria[ticker] = (obter or carregar_ativo)(ticker)
        return memoria[ticker]

    resumo = {"liberadas": 0, "dicas": 0, "proventos": 0, "ordens": 0, "erros": 0}

    # 1. Pagamentos
    if cobrancas is not None and contas is not None:
        for cob in cobrancas.verificar(contas):
            resumo["liberadas"] += 1
            u = contas.buscar(cob.email)
            texto = (f"Recebemos o seu pagamento de {brl(cob.valor)}. O plano {planos.NOMES[cob.plano]} está "
                     f"liberado até {u.validade:%d/%m/%Y}. Bons aportes!")
            caixa.criar(cob.email, "assinatura", "Pagamento confirmado", texto)
            avisos.enviar_email(cob.email, "Chrono Trade: pagamento confirmado", texto)
            from chronotrade.contas import email_admin

            caixa.criar(email_admin(), "admin", f"Assinatura paga: {cob.email}",
                        f"{u.nome} pagou {brl(cob.valor)} ({planos.NOMES[cob.plano]}, {cob.periodo}). "
                        "Liberado automaticamente.")

    if so_pagamentos:
        return resumo

    # 2 a 4. Cada pessoa
    for p in _pessoas(contas):
        if so_email and p.email != so_email:
            continue
        carteira = _carteira_de(p.pasta)
        if carteira is None:
            continue
        try:
            frequencia = FREQUENCIA[planos.LIMITES[p.plano].sentinela]
            ultimo = caixa.ultimo(p.email, "sentinela")
            if forcar or ultimo is None or agora - ultimo >= frequencia:
                dica = montar_dica(carteira, buscar, agora.date(), planos.libera(p.plano, "tecnica"))
                texto = None
                if usar_ia and planos.nivel(p.plano) >= planos.nivel("medio"):
                    texto = redigir_com_ia(dica, p.nome)
                _entregar(caixa, p, "sentinela", dica.titulo, texto or dica.texto)
                resumo["dicas"] += 1

            hoje = agora.date()
            for pos in carteira.posicoes:
                d = buscar(pos.ticker)
                for e in agenda.prever(pos.ticker, d.dividendos, pos.quantidade, hoje, meses=1,
                                       confirmado=d.proximo_provento):
                    if e.data <= hoje + timedelta(days=3):
                        titulo = f"Data com de {ticker_curto(e.ticker)} em {e.data:%d/%m}"
                        if not caixa.ja_avisado(p.email, "provento", titulo):
                            caixa.criar(p.email, "provento", titulo,
                                        f"Quem tiver {ticker_curto(e.ticker)} até {e.data:%d/%m} recebe cerca de "
                                        f"{brl(e.valor_por_cota)} por cota ({e.situacao.lower()}). "
                                        f"Com {e.quantidade:.0f} cotas, uns {brl(e.total)}. {AVISO_CURTO}")
                            resumo["proventos"] += 1

            if (p.pasta / "corretora_simulada.json").exists():
                from chronotrade.corretoras.simulada import CorretoraSimulada

                for r in CorretoraSimulada(p.pasta, preco=lambda t: buscar(t).preco).processar_pendentes():
                    caixa.criar(p.email, "ordem", f"Ordem simulada executada: {ticker_curto(r.ordem.ticker)}",
                                f"{r.ordem.lado.capitalize()} de {r.ordem.quantidade} cotas a {brl(r.preco)} "
                                "na carteira simulada.")
                    resumo["ordens"] += 1
        except Exception as erro:
            resumo["erros"] += 1
            log.exception("Sentinela falhou para %s: %s", p.email, erro)
    return resumo


# ---------------------------------------------------------------------------
# Rodar sozinho
# ---------------------------------------------------------------------------

_iniciado = threading.Event()


def _trava(caminho: Path, validade: timedelta) -> bool:
    """Garante um agente só por servidor, mesmo com o app e o comando rodando juntos."""
    agora = datetime.now()
    try:
        dados = json.loads(caminho.read_text())
        if agora - datetime.fromisoformat(dados["em"]) < validade and dados.get("pid") != os.getpid():
            return False
    except (OSError, ValueError, KeyError):
        pass
    caminho.write_text(json.dumps({"pid": os.getpid(), "em": agora.isoformat()}))
    return True


def _abrir_servicos():
    from chronotrade import contas as contas_mod, pagamentos

    banco = pasta_dados() / "contas.db"
    contas = contas_mod.Contas(banco) if contas_mod.modo_servidor() else None
    cobrancas = pagamentos.Cobrancas(banco) if (contas is not None and pagamentos.automatico()) else None
    return contas, avisos.CaixaDeAvisos(banco), cobrancas


def rodar_para_sempre(minutos: int | None = None) -> None:
    minutos = minutos or int(os.environ.get("CHRONOTRADE_AGENTE_MINUTOS", "60"))
    trava = pasta_dados() / "agente.trava"
    while True:
        if _trava(trava, timedelta(minutes=minutos * 2)):
            try:
                contas, caixa, cobrancas = _abrir_servicos()
                resumo = ciclo(contas, caixa, cobrancas)
                log.info("Sentinela: %s", resumo)
            except Exception:
                log.exception("Ciclo do Sentinela falhou")
        # pagamentos são conferidos com mais frequência que as dicas
        for _ in range(max(1, minutos // 5)):
            time.sleep(300)
            try:
                contas, caixa, cobrancas = _abrir_servicos()
                if cobrancas is not None:
                    ciclo(contas, caixa, cobrancas, so_pagamentos=True)
            except Exception:
                log.exception("Conferência de pagamentos falhou")


def iniciar_automatico() -> bool:
    """Liga o agente numa linha de execução separada, uma vez por processo."""
    if _iniciado.is_set() or os.environ.get("CHRONOTRADE_AGENTE_AUTOMATICO", "1").strip() in ("0", "nao", "false"):
        return False
    _iniciado.set()
    threading.Thread(target=rodar_para_sempre, name="sentinela", daemon=True).start()
    return True


def main() -> None:
    import argparse

    import tradingagents  # noqa: F401  (carrega o .env)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(prog="chronotrade-agente", description="Agente Sentinela do Chrono Trade.")
    sub = parser.add_subparsers(dest="acao", required=True)
    agora = sub.add_parser("agora", help="Roda um ciclo agora.")
    agora.add_argument("--forcar", action="store_true", help="Manda a dica mesmo que não esteja na hora.")
    agora.add_argument("--email", help="Só para esta conta.")
    agora.add_argument("--sem-ia", action="store_true", help="Não usa IA para redigir.")
    sub.add_parser("loop", help="Fica rodando (para servidor/Docker).")
    args = parser.parse_args()
    if args.acao == "loop":
        rodar_para_sempre()
    else:
        contas, caixa, cobrancas = _abrir_servicos()
        print(ciclo(contas, caixa, cobrancas, forcar=args.forcar, so_email=args.email, usar_ia=not args.sem_ia))


if __name__ == "__main__":
    main()
