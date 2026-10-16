# Chrono Trade: telas e fluxos

**Buy and hold diário. Prosperidade no longo prazo.**

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

## O salão do Pregão

```mermaid
flowchart LR
    A[Entra no Pregão] --> B[Seu avatar aparece no salão]
    B --> C[Clica no chão ou usa as setas: anda]
    B --> D[Clica em alguém]
    D --> E[Mensagem privada]
    D --> F[Ver o gráfico da pessoa]
    B --> G[Botão Gráfico ou /grafico TAEE11]
    G --> H[Monitor na sua mesa + telão + conversa]
    B --> I[Conversa: responder, reagir, @mencionar, /cotacao]
    I --> J[Quem foi citado recebe aviso]
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

| ![](docs/telas/30_vitrine_slogan.png) **Vitrine nova** | Novo posicionamento: buy and hold diário, prosperidade no longo prazo | Todos |
| ![](docs/telas/31_portal_primeiros_passos.png) **Primeiros passos** | Checklist no Portal: carteira, corretora ou B3, alerta, perfil e Pregão | Todos |
| ![](docs/telas/32_perfil_foto.png) **Meu perfil** | Foto (enviar ou câmera, estilo pixel), apelido único, bio e bonequinho | Todos |
| ![](docs/telas/33_pregao_salao.png) **Salão interativo** | Avatares andando, telão com o último gráfico, monitores nas mesas, balões | Básico |
| ![](docs/telas/35_menu_avatar.png) **Clique em alguém** | Mensagem privada, ver o gráfico da pessoa, ir até ela | Básico |
| ![](docs/telas/36_grafico_no_salao.png) **Gráfico compartilhado** | Abre grande dentro do salão, com variação, mínimo, máximo e comentário | Básico |
| ![](docs/telas/37_chat_bot.png) **Conversa e robô** | Respostas, reações, @menções com aviso, $ativos, comandos /cotacao /grafico /proventos | Básico |
| ![](docs/telas/38_privadas.png) **Mensagens privadas** | Conversa um a um, aviso de mensagem nova, denúncia | Básico |
| ![](docs/telas/42_pregao_celular.png) **Salão no celular** | Toque para andar; balões e telão ajustados à tela | Básico |
| ![](docs/telas/50_admin_conta_teste.png) **Criar conta de teste** | Usuário, senha, dias e plano; convite pronto para o WhatsApp | Admin |
| ![](docs/telas/51_admin_pontos.png) **Admin: pontos** | Confirmar pacotes pagos pelo PIX e dar pontos ou itens de presente | Admin |
| ![](docs/telas/52_teste_logado.png) **Cliente em teste** | Entrou com "Teste"; contagem de dias e link para assinar | Teste |
| ![](docs/telas/53_teste_minha_conta.png) **Minha conta (teste)** | Até quando vale o teste e os planos para continuar | Teste |
| ![](docs/telas/54_loja_avatar.png) **Pontos e loja** | Check-in, sequência, loja de trajes, chapéus, acessórios e molduras | Básico |
| ![](docs/telas/55_tema_verde.png) **Tema Verde investidor** | Paleta verde comercial | Todos |
| ![](docs/telas/56_tema_laranja.png) **Tema Laranja energia** | Paleta laranja | Todos |
| ![](docs/telas/57_tema_classico.png) **Tema Clássico** | Azul-marinho e dourado, títulos com serifa | Todos |
| ![](docs/telas/58_perfil_temas.png) **Aparência do app** | Escolha do tema em Meu perfil | Todos |
| ![](docs/telas/59_pregao_terno.png) **Avatar de terno no Pregão** | Itens comprados aparecem no salão | Básico |
| ![](docs/telas/60_webhook.png) **Webhook** | Avisos no Discord, Slack, Teams, Google Chat, Zapier ou Make | Médio |
| ![](docs/telas/61_portal_moderno.png) **Portal no tema moderno** | Atalhos rápidos, cartões de vidro, barra de meta com brilho | Todos |
| ![](docs/telas/62_estresse.png) **Teste de estresse** | Crises da B3 aplicadas à carteira, com e sem aportes | Médio |
| ![](docs/telas/63_intencoes.png) **Simular intenções** | Compras e vendas antes de fazer: pesos, concentração, proventos | Médio |
| ![](docs/telas/64_futuros.png) **Futuros possíveis** | Faixa provável do patrimônio e chance de prejuízo | Médio |
| ![](docs/telas/65_jarvis.png) **Jarvis** | Mãos livres, conversa contínua e confirmação por voz | Médio |
| ![](docs/telas/67_maos_livres_checkin.png) **Mãos livres: check-in** | “Jarvis, fazer o check-in do dia” em qualquer tela | Médio |
| ![](docs/telas/68_maos_livres_crise.png) **Mãos livres: crise** | “Jarvis, e se vier uma crise como a de 2008?” abre o simulador e responde falando | Médio |
| ![](docs/telas/66_perfil_frases.png) **Frases do avatar** | Gravar com a sua voz, voz do Jarvis ou do navegador | Básico |
| ![](docs/telas/69_temas.png) **Temas** | Seis temas, com o Esmeralda moderno como padrão | Todos |
| ![](docs/telas/70_pregao_emoji.png) **Emojis no salão** | Barra de emojis; eles sobem do avatar para todos verem | Básico |
| ![](docs/telas/72_pregao_frase_falada.png) **Frase falada** | O avatar fala a frase com balão 🔊 | Básico |
| ![](docs/telas/39_alertas.png) **Alertas de preço** | Preço-alvo abaixo ou acima; zona de compra automática; Telegram grátis | Básico (Telegram no Médio) |
| ![](docs/telas/40_importar_b3.png) **Importar da B3** | Posição de todas as corretoras pela Área do Investidor, com prévia | Todos |
| ![](docs/telas/41_agenda_ics.png) **Agenda no calendário** | Arquivo .ics com as datas com e lembrete um dia antes | Básico |

O **Oráculo: conselho de agentes de IA** (vários agentes debatem uma ação) é do plano Premium, com 30 análises por mês.

## Avisos legais no app
- Simulador: crises com quedas aproximadas, para estudo; não é previsão nem recomendação. Mãos livres não guarda áudio; frases do avatar são públicas e moderadas.
- Pontos e itens do avatar não têm valor monetário nem são prêmio por desempenho; pacotes têm 7 dias de arrependimento enquanto não usados.
- Cadastro só com duas confirmações: termos de uso e "o Chrono Trade não faz recomendação; as decisões e os riscos são meus".
- Aviso legal no fim das telas com números de investimento, na vitrine e na barra lateral.
- Toda dica do Sentinela termina com o aviso, inclusive quando escrita pela IA (o app confere e acrescenta se faltar).
- Ordens pedem confirmação explícita; ordens reais ficam desligadas por padrão; ordens por voz só na carteira simulada.
- O Jarvis recusa pedidos de recomendação ("devo comprar?") e acrescenta o aviso quando o modelo fala em comprar ou vender.
- Pregão e compartilhamentos levam o aviso de que são opiniões pessoais; regras de conduta nos termos (sem promessa de ganho, sem consultoria sem registro na CVM).
- Termos com Resoluções CVM 19 e 20, aviso de risco, direito de arrependimento e LGPD (modelo para revisar com advogado).
