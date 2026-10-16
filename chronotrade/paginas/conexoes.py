"""Conexões: MetaTrader 5, Profit, contatos do WhatsApp, Conector do PC e OpenJarvis num lugar só."""

import os

import pandas as pd
import streamlit as st

from chronotrade import api, compartilhar_whats, conexoes as cx, estado, jarvis, tema
from chronotrade.calculos import brl
from chronotrade.carteira import pasta_dados
from chronotrade.mercado import ticker_curto

st.title("Conexões")
tema.fala("Ligue aqui a sua <b>plataforma de negociação</b>, os <b>contatos</b> para compartilhar ideias e o "
          "<b>Jarvis</b> de voz. Três passos por plataforma: escolher, preencher, testar.")

servidor = estado.servidor()
pasta = estado.pasta()
pasta_sim = pasta or (pasta_dados() / "visitantes" / estado.email_avisos().split(":")[-1])
perfis = cx.carregar(pasta) if pasta else st.session_state.setdefault("perfis_visitante", [])
c = estado.carteira()
tickers = [p.ticker for p in c.posicoes] + list(c.observar)

aba_plat, aba_b3, aba_contatos, aba_ponte, aba_jarvis = st.tabs(
    ["🔌 Plataformas", "📥 Importar da B3", "💬 Contatos do WhatsApp", "🖥️ Conector do PC", "🎙️ OpenJarvis"])


def _cofre():
    if servidor or pasta is None:
        return None
    try:
        return cx.Cofre(pasta)
    except Exception:
        return None


def _guardar(perfil: cx.Perfil) -> None:
    if pasta:
        cx.guardar(pasta, perfil)
    else:
        st.session_state.perfis_visitante = [p for p in perfis if p.id != perfil.id] + [perfil]


def _mostrar_teste(perfil: cx.Perfil, teste: cx.Teste, registrar: bool = True) -> None:
    if not teste.ok:
        st.error(teste.mensagem)
        return
    st.success(teste.mensagem + (f" Saldo: {brl(teste.saldo)}." if teste.saldo else "").replace("$", "\\$"))
    if not teste.posicoes:
        st.caption("Nenhuma posição aberta nesta plataforma ainda, então nada muda no Inventário.")
        return
    mudancas = cx.comparar(c, teste.posicoes)
    icones = {"novo": "🆕 entra", "alterado": "✏️ muda", "igual": "✅ igual", "fora da corretora": "⚠️ só no app"}
    st.dataframe(pd.DataFrame([{"Ativo": ticker_curto(m.ticker), "O que acontece": icones[m.tipo],
                                "Hoje no app": f"{m.antes:g}", "Na plataforma": f"{m.depois:g}",
                                "Preço médio": brl(m.preco_medio)} for m in mudancas]),
                 hide_index=True, width="stretch")
    remover = st.checkbox("Tirar do Inventário o que não está na plataforma", key=f"rem_{perfil.id}")
    if st.button("Trazer para o Inventário", type="primary", key=f"apl_{perfil.id}"):
        mudou = cx.aplicar(c, teste.posicoes, remover)
        if estado.salvar() and pasta and registrar:
            cx.marcar(pasta, perfil, sincronizou=True)
        elif pasta:
            (pasta / "importou_b3").write_text(perfil.apelido, encoding="utf-8")
        st.session_state.pop(f"teste_{perfil.id}", None)
        st.toast(f"Inventário atualizado: {mudou} ativo(s) mudaram.", icon="✅")
        st.rerun()


# --- Plataformas -------------------------------------------------------------------------
with aba_plat:
    if perfis:
        st.subheader("Minhas conexões")
        for perfil in perfis:
            info = cx.PLATAFORMAS[perfil.tipo]
            cor = {"Conectada": "🟢", "Com erro": "🔴"}.get(perfil.situacao, "⚪")
            with st.container(border=True):
                col1, col2 = st.columns([3, 2], vertical_alignment="center")
                col1.markdown(f"**{info['icone']} {perfil.apelido}**  \n{cx.descrever(perfil)}  \n"
                              f"{cor} {perfil.situacao}"
                              + (f", sincronizada em {perfil.ultima_sincronizacao[:16].replace('T', ' ')}"
                                 if perfil.ultima_sincronizacao else ""))
                b1, b2, b3 = col2.columns(3)
                if b1.button("Testar", key=f"tst_{perfil.id}", width="stretch"):
                    cofre = _cofre()
                    segredos = cofre.ler(perfil.id) if cofre else st.session_state.get(f"seg_{perfil.id}", {})
                    with st.spinner(f"Conectando ao {info['nome']}…"):
                        teste = cx.testar(perfil, segredos, pasta_sim, tickers,
                                          fabrica=lambda t, p, **o: cx.abrir(t, p, preco=lambda x: estado.ativo(x).preco)
                                          if t == "simulada" else cx.abrir(t, p, **o))
                    if pasta:
                        cx.marcar(pasta, perfil, teste)
                    st.session_state[f"teste_{perfil.id}"] = teste
                auto = b2.toggle("Auto", value=perfil.auto_sincronizar, key=f"auto_{perfil.id}",
                                 help="O agente Sentinela traz as posições sozinho a cada ciclo (app instalado no PC).")
                if auto != perfil.auto_sincronizar:
                    perfil.auto_sincronizar = auto
                    _guardar(perfil)
                with b3.popover("🗑️", width="stretch"):
                    st.caption("Apagar esta conexão e a senha guardada?")
                    if st.button("Apagar", key=f"del_{perfil.id}", type="primary"):
                        if pasta:
                            cx.remover(pasta, perfil.id, _cofre())
                        else:
                            st.session_state.perfis_visitante = [p for p in perfis if p.id != perfil.id]
                        st.rerun()
                teste = st.session_state.get(f"teste_{perfil.id}")
                if teste:
                    _mostrar_teste(perfil, teste)

    st.subheader("Nova conexão")
    escolha = st.radio("Plataforma", list(cx.PLATAFORMAS), horizontal=True, key="nova_plat",
                       format_func=lambda k: f"{cx.PLATAFORMAS[k]['icone']} {cx.PLATAFORMAS[k]['nome']}")
    info = cx.PLATAFORMAS[escolha]
    real = escolha != "simulada"
    if real and not estado.liberado("corretora"):
        pass
    elif real and servidor:
        tema.fala(f"Na versão online, o <b>{info['nome']}</b> roda no <b>seu computador</b>, não no nosso servidor. "
                  "Use a aba <b>Conector do PC</b>: baixe o atalho pronto, dê dois cliques e as suas posições "
                  "chegam aqui sozinhas. A sua senha nunca sai do seu PC.")
    else:
        col_passos, col_form = st.columns([2, 3])
        with col_passos:
            st.markdown(f"**{info['resumo']}**")
            for i, passo in enumerate(info["passos"], 1):
                st.markdown(f"**{i}.** {passo}")
            if escolha == "profit":
                tema.legenda("A ProfitDLL é paga e licenciada pela Nelogica; o conector Python é um projeto da "
                             "comunidade. Teste primeiro no simulador da Nelogica.")
        with col_form, st.form(f"form_{escolha}"):
            apelido = st.text_input("Nome desta conexão", value={"mt5": "Minha corretora", "profit": "Meu Profit",
                                                                 "simulada": "Treino"}[escolha], max_chars=30)
            valores, segredos = {}, {}
            for campo in info["campos"]:
                destino = segredos if campo.secreto else valores
                destino[campo.chave] = st.text_input(campo.rotulo + (" *" if campo.obrigatorio else ""),
                                                     help=campo.ajuda or None,
                                                     type="password" if campo.secreto else "default")
            lembrar = st.checkbox("Lembrar as senhas neste computador (cofre criptografado)", value=False,
                                  disabled=servidor or pasta is None or not info["campos"])
            enviar = st.form_submit_button("Salvar e testar conexão", type="primary")
        if enviar:
            faltando = [cp.rotulo for cp in info["campos"] if cp.obrigatorio and not (valores.get(cp.chave) or segredos.get(cp.chave))]
            if faltando:
                st.error("Preencha: " + ", ".join(faltando))
            else:
                perfil = cx.Perfil(escolha, apelido.strip() or info["nome"], {k: v for k, v in valores.items() if v})
                _guardar(perfil)
                cofre = _cofre()
                if lembrar and cofre:
                    cofre.gravar(perfil.id, segredos)
                st.session_state[f"seg_{perfil.id}"] = {k: v for k, v in segredos.items() if v}
                with st.spinner(f"Conectando ao {info['nome']}…"):
                    teste = cx.testar(perfil, segredos, pasta_sim, tickers,
                                      fabrica=lambda t, p, **o: cx.abrir(t, p, preco=lambda x: estado.ativo(x).preco)
                                      if t == "simulada" else cx.abrir(t, p, **o))
                if pasta:
                    cx.marcar(pasta, perfil, teste)
                st.session_state[f"teste_{perfil.id}"] = teste
                st.rerun()
    tema.legenda("O Chrono Trade só lê posições para montar o Inventário. Ordens com dinheiro real ficam desligadas "
                 "até você ligar no seu computador (CHRONOTRADE_PERMITIR_ORDENS_REAIS=1) e confirmar cada uma.")

# --- Contatos ----------------------------------------------------------------------------
with aba_b3:
    from chronotrade import b3

    tema.fala("O jeito mais simples e <b>gratuito</b>: a B3 junta as posições de <b>todas as suas corretoras</b>. "
              "Baixe o Excel em <b>investidor.b3.com.br → Extratos → Posição</b> e solte aqui.")
    arquivo = st.file_uploader("Arquivo de posição da B3 (Excel ou CSV)", type=["xlsx", "xls", "csv"], key="arq_b3")
    if arquivo is not None:
        try:
            linhas = b3.ler_posicao(arquivo.getvalue(), arquivo.name)
            posicoes_b3, sem_pm = b3.para_posicoes(linhas, c)
            st.success(f"{len(linhas)} ativos encontrados no arquivo.")
            if sem_pm:
                tema.aviso("A B3 não informa o preço médio. Para " + ", ".join(sem_pm[:12]) +
                           " usei o preço de fechamento como ponto de partida; ajuste no Inventário.")
            _mostrar_teste(cx.Perfil("simulada", "B3"), cx.Teste(True, "Arquivo lido.", None, posicoes_b3), registrar=False)
        except b3.ErroB3 as erro:
            st.error(str(erro))
    tema.legenda("O arquivo é lido aqui e não é guardado. Só as quantidades vão para o seu Inventário quando você confirmar.")

with aba_contatos:
    st.markdown("Cadastre quem recebe as suas ideias: um amigo, o seu consultor, a família. Em qualquer tela, o botão "
                "**💬 WhatsApp** abre a conversa com a mensagem pronta; você revisa e envia.")
    contatos = compartilhar_whats.carregar(estado.pasta_social())
    with st.form("novo_contato", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        nome = c1.text_input("Nome")
        numero = c2.text_input("WhatsApp com DDD", placeholder="19 99999-0000")
        tipo = c3.selectbox("Quem é", compartilhar_whats.TIPOS)
        if st.form_submit_button("Adicionar contato"):
            if nome.strip() and sum(ch.isdigit() for ch in numero) >= 10:
                contatos.append({"nome": nome.strip(), "numero": numero.strip(), "tipo": tipo})
                compartilhar_whats.salvar(estado.pasta_social(), contatos)
                st.rerun()
            else:
                st.error("Informe o nome e o número com DDD.")
    for i, contato in enumerate(contatos):
        col1, col2, col3 = st.columns([4, 2, 1], vertical_alignment="center")
        col1.markdown(f"**{contato['nome']}** ({contato['tipo']}), {contato['numero']}")
        col2.link_button("Abrir conversa", compartilhar_whats.link("Oi! Te mando ideias do Chrono Trade por aqui.",
                                                                   contato["numero"]), width="stretch")
        if col3.button("Remover", key=f"rmct{i}"):
            contatos.pop(i)
            compartilhar_whats.salvar(estado.pasta_social(), contatos)
            st.rerun()
    if not contatos:
        st.caption("Nenhum contato ainda.")
    tema.legenda("O app não lê nem guarda as suas conversas: ele só abre o WhatsApp com o texto pronto.")

# --- Conector do PC ----------------------------------------------------------------------
with aba_ponte:
    tema.fala("O <b>Conector do PC</b> leva as posições do MetaTrader 5 ou do Profit, que rodam no seu Windows, "
              "para a sua conta online. Ele só <b>lê</b> posições; não envia ordens.")
    if not servidor:
        st.info("Você está usando o app instalado no seu computador: as plataformas se conectam direto pela aba "
                "Plataformas. O Conector serve para a versão online.")
    elif estado.liberado("ponte"):
        u = estado.usuario()
        url = (estado.config_loja().get("url_publica") or os.environ.get("CHRONOTRADE_URL") or "https://seu-dominio").rstrip("/")
        status = api.status_ponte(pasta)
        if status:
            st.success(f"Última sincronização: {status['recebido_em'].replace('T', ' ')[:16]}, "
                       f"{status['posicoes']} posições do {cx.PLATAFORMAS.get(status['plataforma'], {}).get('nome', status['plataforma'])}.")
        else:
            st.caption("Ainda não recebemos nada do seu computador.")
        st.markdown("**1.** No PC com o MetaTrader 5 (ou o Profit), instale o Chrono Trade com o "
                    "`instalar_windows.bat`.  \n**2.** Gere o seu atalho abaixo e salve na pasta do Chrono Trade.  \n"
                    "**3.** Dê dois cliques. Ele envia as posições a cada 15 minutos enquanto estiver aberto.")
        plataforma = st.radio("Plataforma do seu PC", ["mt5", "profit"], horizontal=True,
                              format_func=lambda k: cx.PLATAFORMAS[k]["nome"])
        if st.button("Gerar meu atalho do Conector", type="primary"):
            st.session_state.token_novo = estado.banco().gerar_token(u.email, f"Conector {cx.PLATAFORMAS[plataforma]['nome']}")
        token = st.session_state.get("token_novo")
        if token:
            ativos = ",".join(ticker_curto(t) for t in tickers[:40])
            bat = ("@echo off\r\ntitle Chrono Trade - Conector do PC\r\ncd /d \"%~dp0\"\r\n"
                   "call .venv\\Scripts\\activate.bat\r\n"
                   f"chronotrade-ponte --servidor {url} --token {token} --plataforma {plataforma} "
                   f"--tickers {ativos or 'PETR4'} --minutos 15\r\npause\r\n")
            st.download_button("Baixar conector_chronotrade.bat", bat, "conector_chronotrade.bat", "application/octet-stream")
            tema.aviso("Guarde o atalho só no seu computador: o token dentro dele dá acesso para enviar posições "
                       "à sua conta. Se perder, revogue abaixo e gere outro.")
        lista = estado.banco().tokens(u.email)
        if lista:
            st.markdown("**Atalhos ativos**")
            for t in lista:
                col1, col2 = st.columns([4, 1], vertical_alignment="center")
                col1.markdown(f"{t['nome']}, criado em {t['criado_em'][:10]}"
                              + (f", usado em {t['ultimo_uso'][:16].replace('T', ' ')}" if t["ultimo_uso"] else ", nunca usado"))
                if col2.button("Revogar", key=f"rev{t['token_hash'][:10]}"):
                    estado.banco().revogar_token(u.email, t["token_hash"])
                    st.session_state.pop("token_novo", None)
                    st.rerun()

# --- OpenJarvis --------------------------------------------------------------------------
with aba_jarvis:
    tema.fala("O <b>OpenJarvis</b> é um assistente de IA que roda no seu computador (código aberto). Ligado ao "
              "Chrono Trade, ele ouve os seus comandos de voz, responde falando e pode consultar a sua carteira.")
    padrao = estado.config_loja().get("openjarvis_url") or os.environ.get("OPENJARVIS_URL") or jarvis.URL_PADRAO
    url_oj = st.text_input("Endereço do OpenJarvis", value=st.session_state.get("openjarvis_url", padrao))
    st.session_state.openjarvis_url = url_oj
    if st.button("Testar OpenJarvis"):
        st.session_state.saude_oj = jarvis.Cliente(url_oj).saude()
    saude = st.session_state.get("saude_oj")
    if saude:
        (st.success if saude["online"] else st.warning)(saude["detalhe"])
    st.markdown("**Instalar (uma vez, no seu PC):**")
    st.code("# PowerShell do Windows (instala uv, Ollama e um modelo inicial)\n"
            "irm https://open-jarvis.github.io/OpenJarvis/install.ps1 | iex\n\n"
            "# depois, para o Chrono Trade conversar com ele:\njarvis serve --port 8000", language="powershell")
    st.markdown("**Dar ao OpenJarvis as ferramentas do Chrono Trade** (resumo da carteira, proventos, dica do "
                "aporte, cotação, notícias). Cole no arquivo `~/.openjarvis/config.toml`:")
    st.code(jarvis.config_mcp(), language="toml")
    st.page_link("paginas/jarvis.py", label="Abrir o Jarvis", icon="🎙️")
