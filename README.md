# ⏳ Chrono Trade

**Carteira de buy and hold da B3 com agentes de IA, simulador de crises e comunidade ao vivo.**

Aplicação web em Python que ajuda o investidor pessoa física a acompanhar a carteira, decidir o próximo aporte e enxergar quanto tempo falta para chegar à renda mensal que ele quer viver de proventos.

> Ferramenta de estudo. Não é recomendação de investimento.

## 🎬 Demonstração

<!-- Para o vídeo tocar aqui: edite este arquivo no GitHub, apague esta linha e arraste o arquivo docs/video/ChronoTrade_demo.mp4 para cá. -->

▶️ [Assistir ao vídeo de demonstração (2 min)](docs/video/ChronoTrade_demo.mp4)

<p align="center">
  <img src="docs/telas/61_portal_moderno.png" width="49%" alt="Portal com a meta de renda mensal">
  <img src="docs/telas/62_estresse.png" width="49%" alt="Simulador de crises da B3">
</p>
<p align="center">
  <img src="docs/telas/12_oraculo_ficha.png" width="49%" alt="Oráculo: ficha da ação e conselho dos agentes de IA">
  <img src="docs/telas/33_pregao_salao.png" width="49%" alt="Pregão ao vivo com avatares">
</p>

## 💡 O problema

Quem investe a longo prazo costuma acompanhar a carteira em planilhas, sem saber se está no caminho da meta, qual ativo comprar no próximo aporte ou como a carteira se comportaria numa crise como a de 2008 ou a da Covid. O Chrono Trade junta essas respostas em um só lugar, com uma interface que transforma a jornada de longo prazo em algo visual e motivador.

## ✨ Principais funcionalidades

- **Portal e Linha do Tempo**: patrimônio, proventos dos últimos 12 meses e projeção até a meta de renda, com cenários pessimista, base e otimista.
- **Próximo Aporte**: preço teto (Bazin e Graham), análise técnica (médias de 50 e 200 dias, IFR) e divisão do aporte em cotas respeitando as metas por classe.
- **Oráculo com agentes de IA**: análise de cada ação por um time de agentes (analistas, pesquisadores, trader e gestor de risco) orquestrado com LangGraph.
- **Simulador de mercado**: teste de estresse com crises reais da B3 e projeções de Monte Carlo.
- **Agente Sentinela**: roda sozinho, vigia a carteira e avisa por app, e-mail, WhatsApp ou Telegram.
- **Imposto de renda**: cálculo de day trade e swing trade, FIIs e geração do DARF.
- **Pregão ao vivo**: salão com avatares, chat e gráficos compartilhados entre os usuários.
- **Modo servidor**: cadastro por e-mail, aprovação pelo administrador e assinaturas via PIX.
- **Jarvis**: comandos de voz em português e um servidor MCP para assistentes de IA consultarem a carteira.

A lista completa está em [docs/FUNCIONALIDADES.md](docs/FUNCIONALIDADES.md) e o mapa de telas em [TELAS_E_FLUXOS.md](TELAS_E_FLUXOS.md).

## 🧰 Tecnologias

| Camada | Ferramentas |
|---|---|
| Interface | Streamlit, Plotly, componentes em HTML/JavaScript, PWA para celular |
| Agentes de IA | LangGraph, LangChain (Gemini, OpenAI ou Claude), servidor MCP |
| Dados de mercado | yfinance (Yahoo Finance), pandas, stockstats |
| Back-end e dados | Python 3.11+, FastAPI, SQLite |
| Qualidade e deploy | pytest (mais de 100 testes do Chrono Trade), Ruff, GitHub Actions, Docker, Render |

## 🏗️ Arquitetura

```
chronotrade/
├── app.py            # entrada do Streamlit e navegação
├── paginas/          # uma tela por arquivo (portal, inventário, oráculo, pregão...)
├── calculos.py       # Bazin, Graham, yield on cost, número mágico
├── simulador.py      # crises históricas e Monte Carlo
├── ir.py             # regras de imposto de renda
├── motor_ia.py       # ponte com os agentes do TradingAgents
├── agentes/          # agente Sentinela (roda em segundo plano)
├── corretoras/       # interface comum para corretora simulada, MetaTrader 5 e Profit
└── mcp_servidor.py   # servidor MCP para assistentes de IA
tradingagents/        # framework de agentes original (Tauric Research)
tests/                # testes automatizados
```

As corretoras seguem uma interface comum (`corretoras/base.py`), então uma nova integração só precisa implementar os mesmos métodos.

## 🚀 Como rodar

Requisitos: Python 3.11 ou superior.

```bash
git clone https://github.com/marcelomekaro/chronotrade.git
cd chronotrade
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/Mac: source .venv/bin/activate
pip install -e .
chronotrade
```

O navegador abre em `http://localhost:8501`. Ligue o **Modo demonstração** na barra lateral para ver o app com dados fictícios, sem precisar de chave de API.

Para usar os agentes de IA, copie `.env.example` para `.env` e preencha o provedor e a chave (por exemplo `TRADINGAGENTS_LLM_PROVIDER=google` e `GOOGLE_API_KEY`).

No Windows também dá para instalar com dois cliques em `instalar_windows.bat`. O passo a passo para publicar online está em [DEPLOY.md](DEPLOY.md).

Rodar os testes:

```bash
pip install -e ".[dev]"
pytest tests -k chronotrade
```

## 🙏 Créditos

O Chrono Trade é um fork do [TradingAgents](https://github.com/TauricResearch/TradingAgents), da Tauric Research, que fornece o framework de agentes de IA para análise de ações. Todo o código da pasta `chronotrade/` (interface, cálculos, simulador, comunidade, contas e integrações) foi construído sobre ele. O projeto segue a mesma licença, [Apache 2.0](LICENSE).

O desenvolvimento contou com apoio de assistentes de IA para programação.

## 👤 Autor

**Marcelo Shinyu Mekaro**, estudante de Análise e Desenvolvimento de Sistemas no IFSP.
[LinkedIn](https://linkedin.com/in/marcelo-mekaro-063527121) · [Portfólio](https://mekaro.netlify.app)
