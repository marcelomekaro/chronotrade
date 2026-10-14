# Chrono Trade: telas e fluxos

As imagens estão em `docs/telas/` e foram tiradas com o **modo demonstração** (dados fictícios).

## Fluxo do cliente (do cadastro à dica do aporte)

```mermaid
flowchart TD
    A[Abre o app] --> B{Já tem conta?}
    B -- Não --> C[Vitrine: pontos fortes, planos e calculadora]
    C --> D[Cria a conta: nome, e-mail, WhatsApp, senha e as duas confirmações legais]
    C --> V[Experimenta com dados fictícios]
    D --> E[Minha conta: escolhe plano e período, vê o PIX]
    E --> F{Mercado Pago ligado?}
    F -- Sim --> G[Paga o PIX gerado] --> H[O app confirma sozinho e libera o plano]
    F -- Não --> I[Paga pela chave marcelomekaro@gmail.com e manda o comprovante no WhatsApp]
    I --> J[Admin libera no painel]
    H --> K[Usa o app conforme o plano]
    J --> K
    B -- Sim --> L[Entra com e-mail e senha] --> K
    K --> M[Cadastra a carteira no Inventário]
    M --> N[Agente Sentinela analisa sozinho]
    N --> O[Dica do próximo aporte: pop-up no app, e-mail e WhatsApp]
    O --> P[Próximo Aporte: confere preços, gráfico e cotas]
    P --> Q[Decide e compra na própria corretora, ou treina na carteira simulada]
```

## Fluxo do administrador

```mermaid
flowchart LR
    A[Painel do admin] --> B[Pendentes: libera plano, dias e valor]
    A --> C[Assinantes: renova, muda plano, bloqueia, gera senha temporária, exclui]
    A --> D[Cobrança: quem vence em 7 dias, botão de cobrar no WhatsApp com PIX]
    A --> E[Pagamentos: receita por mês e CSV]
    A --> F[Agente: roda o Sentinela para todos agora]
    A --> G[Loja e integrações: preços, PIX, WhatsApp, status de Mercado Pago, e-mail, WhatsApp e IA]
```

## O que o agente Sentinela faz a cada hora

```mermaid
flowchart LR
    S[Sentinela] --> P1[Confere PIX do Mercado Pago e libera assinaturas pagas]
    S --> P2[Para quem está na hora: radar de preços, momento técnico, divide o aporte em cotas]
    P2 --> P3[IA redige a dica, sempre com o aviso legal]
    P3 --> P4[Entrega: app, e-mail, WhatsApp]
    S --> P5[Avisa datas com nos próximos 3 dias]
    S --> P6[Executa ordens limitadas da carteira simulada]
```

## Conectar a plataforma de negociação

```mermaid
flowchart TD
    A[Conexões → Plataformas] --> B{Qual plataforma?}
    B -- MetaTrader 5 --> C[Terminal da corretora aberto e logado no Windows]
    B -- Profit --> D[ProfitDLL da Nelogica: caminho da DLL, chave, usuário e senha]
    C --> E[Testar conexão]
    D --> E
    E --> F{Deu certo?}
    F -- Não --> G[Mensagem clara do que falta] --> E
    F -- Sim --> H[Prévia: entra, muda, igual, só no app]
    H --> I[Trazer para o Inventário]
    I --> J[Auto ligado: o Sentinela sincroniza sozinho]
    K[Versão online] --> L[Conector do PC: baixa o .bat com token] --> M[Dois cliques no PC] --> N[Posições chegam na conta a cada 15 min]
```

## Jarvis: da voz à resposta

```mermaid
flowchart LR
    A[Fala no microfone] --> B[OpenJarvis transcreve<br/>ou Gemini, plano B]
    B --> C{Comando do app?}
    C -- Sim --> D[Cotação, dica, proventos, patrimônio, notícias, abrir tela, ordem simulada, WhatsApp]
    C -- Não --> E[Modelo do OpenJarvis com dados da carteira e trava legal]
    D --> F[Resposta em texto e voz]
    E --> F
    G[OpenJarvis no PC] -. MCP: chronotrade-mcp .-> H[Ferramentas da carteira]
```

## Telas

| Tela | Para que serve | Plano |
|---|---|---|
| ![](docs/telas/01_portaria.png) **Vitrine e entrada** | Pontos fortes, calculadora de desconto, planos, comparativo, cadastro com aceite legal, teste grátis | Todos |
| ![](docs/telas/02_portaria_celular.png) **Vitrine no celular** | A mesma tela ajustada ao Android | Todos |
| ![](docs/telas/03_pagamento_celular.png) **Pagamento** | Escolha do plano e período, QR Code, chave PIX, copia e cola, comprovante pelo WhatsApp | Todos |
| ![](docs/telas/04_admin_pendentes.png) **Admin: pendentes** | Liberar cadastros com plano, dias e valor | Admin |
| ![](docs/telas/05_admin_loja.png) **Admin: loja** | Preços, PIX, WhatsApp, teste do PIX e situação das integrações | Admin |
| ![](docs/telas/06_portal.png) **Portal** | Patrimônio, proventos e a linha do tempo até a meta de renda | Básico |
| ![](docs/telas/07_inventario.png) **Inventário** | Cadastro da carteira e raio-x com DY, yield on cost e preço teto | Básico |
| ![](docs/telas/13_tesouro.png) **Tesouro** | Proventos mês a mês, número mágico e constância | Básico |
| ![](docs/telas/09_agenda.png) **Agenda de proventos** | Próximas datas com e quanto deve cair por mês | Básico |
| ![](docs/telas/14_linha_do_tempo.png) **Linha do Tempo** | Projeção com cenários e os marcos da jornada | Básico |
| ![](docs/telas/12_oraculo_ficha.png) **Oráculo: ficha rápida** | Bazin, Graham, P/L, P/VP e checklist | Básico |
| ![](docs/telas/08_proximo_aporte.png) **Próximo Aporte** | Radar de preços, análise técnica com gráfico e divisão do aporte em cotas | Médio |
| ![](docs/telas/10_avisos_sentinela.png) **Avisos** | Dicas do Sentinela, datas com e confirmações; pedir uma dica agora | Básico (e-mail no Médio, WhatsApp no Premium) |
| ![](docs/telas/11_corretora_simulada.png) **Corretora** | Carteira simulada com ordens; MetaTrader 5 no Premium | Médio / Premium |
| ![](docs/telas/16_pregao_ao_vivo.png) **Pregão ao vivo** | Salão em pixel art com quem está online, telão, letreiro e balões de fala | Básico |
| ![](docs/telas/17_pregao_conversa.png) **Pregão: conversa** | Mensagens com etiqueta do ativo, compartilhar, denunciar; avatar e apelido | Básico |
| ![](docs/telas/25_pregao_celular.png) **Pregão no celular** | Salão em duas colunas, conversa e campo de mensagem | Básico |
| ![](docs/telas/18_noticias.png) **Notícias e vídeos** | Notícias por ativo da carteira, mercado e negócios, canais do YouTube; WhatsApp e "Levar ao Pregão" | Básico |
| ![](docs/telas/27_conexoes_mt5_assistente.png) **Conexões: MetaTrader 5** | Assistente: passos, campos, cofre de senhas e teste com mensagem clara | Premium |
| ![](docs/telas/28_conexoes_profit.png) **Conexões: Profit** | Mesmo assistente para a ProfitDLL da Nelogica | Premium |
| ![](docs/telas/19_conexoes_plataformas.png) **Conexões: minhas conexões** | Status, Testar, Auto (sincronização), prévia do que muda e Trazer para o Inventário | Premium (simulada no Médio) |
| ![](docs/telas/20_conexoes_contatos.png) **Contatos do WhatsApp** | Amigo, consultor, família: aparecem em todos os botões de compartilhar | Todos |
| ![](docs/telas/21_conector_do_pc.png) **Conector do PC** | Gera o atalho .bat com token, mostra a última sincronização, revoga | Premium (online) |
| ![](docs/telas/22_conexoes_openjarvis.png) **OpenJarvis** | Endereço, teste, instalação e o trecho MCP para o OpenJarvis | Médio |
| ![](docs/telas/23_jarvis.png) **Jarvis (voz)** | Microfone, sugestões, respostas faladas, ordem simulada com confirmação, WhatsApp | Médio |
| ![](docs/telas/26_jarvis_celular.png) **Jarvis no celular** | O mesmo, no Android | Médio |
| ![](docs/telas/24_admin_comunidade.png) **Admin: Comunidade** | Online agora, moderação de denúncias, TV do Pregão, fontes de notícias, canais, endereço público e OpenJarvis | Admin |
| ![](docs/telas/15_compartilhar.png) **Compartilhar** | Relatório para imprimir ou PDF, com opção de ocultar valores | Médio |

O **Oráculo: conselho de agentes de IA** (vários agentes debatem uma ação) é do plano Premium, com 30 análises por mês.

## Avisos legais no app
- Cadastro só com duas confirmações: termos de uso e "o Chrono Trade não faz recomendação; as decisões e os riscos são meus".
- Aviso legal no fim das telas com números de investimento, na vitrine e na barra lateral.
- Toda dica do Sentinela termina com o aviso, inclusive quando escrita pela IA (o app confere e acrescenta se faltar).
- Ordens pedem confirmação explícita; ordens reais ficam desligadas por padrão; ordens por voz só na carteira simulada.
- O Jarvis recusa pedidos de recomendação ("devo comprar?") e acrescenta o aviso quando o modelo fala em comprar ou vender.
- Pregão e compartilhamentos levam o aviso de que são opiniões pessoais; regras de conduta nos termos (sem promessa de ganho, sem consultoria sem registro na CVM).
- Termos com Resoluções CVM 19 e 20, aviso de risco, direito de arrependimento e LGPD (modelo para revisar com advogado).
