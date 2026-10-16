# Guia do Chrono Trade

**Buy and hold diário. Prosperidade no longo prazo.**

Há dois jeitos de usar o app:

| | Instalação local | Online (servidor) |
|---|---|---|
| Para quem | Só você, no seu computador | Você e os seus assinantes, pela internet |
| Login | Não tem | E-mail e senha, com aprovação do administrador |
| Celular | Na mesma rede Wi-Fi de casa | Em qualquer lugar |
| Configuração | `CHRONOTRADE_MODO=pessoal` (padrão) | `CHRONOTRADE_MODO=servidor` |

---

## 1. Instalação local no Windows (dois cliques)

1. Instale o Python em https://www.python.org/downloads/ marcando **Add python.exe to PATH**.
2. Na pasta do projeto, dê dois cliques em **`instalar_windows.bat`**. Ele cria o ambiente,
   instala tudo e põe um atalho **Chrono Trade** na área de trabalho.
3. Abra pelo atalho. O navegador abre em `http://localhost:8501`.

Para usar a IA, preencha a chave no arquivo `.env` (por exemplo `GOOGLE_API_KEY=` para o Gemini).

### Abrir no celular dentro de casa
Com o app aberto no computador, a janela preta mostra um endereço **Network URL**
(algo como `http://192.168.0.15:8501`). Digite esse endereço no Chrome do celular
conectado ao mesmo Wi-Fi. Se o Windows perguntar sobre o firewall, permita em **redes privadas**.

---

## 2. Online, para vender assinaturas

### Do que você precisa
- Um servidor que rode **Docker** e guarde arquivos de forma permanente (um VPS Linux
  barato serve; serviços de nuvem com "volume" ou "disco persistente" também).
- Um domínio (opcional, mas recomendado para ter HTTPS), apontado para o IP do servidor.

> Serviços gratuitos que apagam os arquivos a cada reinício (como o Streamlit Community
> Cloud) **não servem** para a versão com contas: os cadastros e carteiras sumiriam.

### Passo a passo no servidor
```bash
git clone https://github.com/marcelomekaro-code/TradingAgents.git
cd TradingAgents
git checkout chronotrade
cp .env.example .env
nano .env
```
No `.env`, preencha pelo menos:
```
CHRONOTRADE_MODO=servidor
CHRONOTRADE_ADMIN_EMAIL=marcelomekaro@gmail.com
CHRONOTRADE_ADMIN_SENHA=UmaSenhaForte123
GOOGLE_API_KEY=sua-chave
TRADINGAGENTS_LLM_PROVIDER=google
CHRONOTRADE_DOMINIO=chronotrade.seudominio.com.br
```
Depois:
```bash
docker compose --profile https up -d chronotrade agente caddy
```
Pronto: o app fica em `https://chronotrade.seudominio.com.br`, com certificado automático.
Sem domínio, use `docker compose up -d chronotrade agente` e acesse `http://IP-DO-SERVIDOR:8501`
(sem HTTPS, as senhas trafegam abertas; use só para testar).

### Primeiro acesso do administrador
1. Entre com o e-mail do administrador e a senha de `CHRONOTRADE_ADMIN_SENHA`.
2. Vá em **Minha conta** e troque a senha.
3. Vá em **Painel do admin → Loja e integrações** e confira preços (Básico, Médio, Premium e o desconto
   anual), a chave PIX (já vem `marcelomekaro@gmail.com`), o nome do recebedor, a cidade e o WhatsApp
   de atendimento (já vem 19 99965-0436). Tudo pode ser mudado depois.
4. Use o **Teste do PIX** (R$ 0,01) para conferir se o dinheiro cai na sua conta.

Esqueceu a senha do administrador? No servidor:
```bash
docker compose exec chronotrade chronotrade-admin senha marcelomekaro@gmail.com
```

### Planos
| | Básico | Médio | Premium |
|---|---|---|---|
| Preço sugerido | R$ 19,90/mês | R$ 39,90/mês | R$ 79,90/mês |
| Ativos | até 15 | ilimitados | ilimitados |
| Portal, Tesouro, Agenda, Linha do Tempo, Ficha rápida | ✅ | ✅ | ✅ |
| Próximo Aporte com análise técnica, Compartilhar, Carteira simulada | | ✅ | ✅ |
| Agente Sentinela | semanal, no app | semanal, app e e-mail | diário, app, e-mail e WhatsApp |
| Pregão ao vivo, Notícias e vídeos, contatos do WhatsApp | ✅ | ✅ | ✅ |
| Jarvis (comando de voz com OpenJarvis) | | ✅ | ✅ |
| Oráculo de IA | | | 30 análises por mês |
| Corretora real (MetaTrader 5 e Profit) e Conector do PC | | | ✅ |

A tabela de recursos fica em `chronotrade/planos.py`; mudar um plano é mudar ali.

### Como funciona a assinatura
**Com liberação automática (recomendado):** crie uma conta no Mercado Pago, gere o *Access Token* de
produção (Seu negócio → Configurações → Credenciais) e coloque em `MERCADOPAGO_ACCESS_TOKEN` no `.env`.
1. O cliente cria a conta, escolhe o plano e o período e toca em **Gerar PIX**.
2. Paga pelo app do banco. O Chrono Trade confere o pagamento (na hora, se ele tocar em "Já paguei",
   ou sozinho a cada 5 minutos) e **libera o plano automaticamente**.
3. Você recebe um aviso no painel. O cliente recebe um aviso no app e por e-mail.

**Sem Mercado Pago:** o app mostra o QR Code e a chave `marcelomekaro@gmail.com` com o valor, e o botão
de mandar o comprovante pelo WhatsApp. Você confere no banco e libera em **Painel do admin → Pendentes**.

Renovações seguem o mesmo caminho: os dias novos são somados à validade atual. Perto do vencimento, a aba
**Cobrança** mostra quem vence e um botão que abre o WhatsApp com a mensagem e o PIX prontos.

Cliente esqueceu a senha: em **Assinantes**, clique em **Gerar senha temporária** e envie pelo botão do WhatsApp.

### Agente Sentinela
Roda sozinho (o serviço `agente` do Docker, ou junto com o app) de hora em hora:
- confere pagamentos e libera assinaturas;
- manda a **dica do próximo aporte** (semanal no Básico e no Médio, diária no Premium): quais ativos estão
  abaixo do preço justo, o momento técnico, quantas cotas de cada um e os próximos proventos;
- avisa as **datas com** que chegam em 3 dias;
- executa as ordens limitadas da carteira simulada;
- confere os **alertas de preço** que cada pessoa criou ("TAEE11 abaixo de R$ 34") e avisa uma vez quando bate;
- avisa quando um ativo do radar **entra na zona de compra** pelas regras da própria pessoa (planos Médio e Premium);
- sincroniza as conexões marcadas como **Auto** (app instalado) e vincula quem ligou o **Telegram**.

Os avisos aparecem como pop-up no app e na tela **Avisos**; por e-mail e WhatsApp, conforme o plano e a
escolha de cada cliente em **Minha conta**. Nos planos Médio e Premium a dica é redigida pela IA (com os
mesmos números, sempre com o aviso legal). Para rodar na hora: **Painel do admin → Agente**, ou
`docker compose exec chronotrade chronotrade-agente agora --forcar`.

### Integrações (no `.env` do servidor)
- **E-mail**: `CHRONOTRADE_SMTP_HOST=smtp.gmail.com`, `CHRONOTRADE_SMTP_PORTA=587`,
  `CHRONOTRADE_SMTP_USUARIO=marcelomekaro@gmail.com` e `CHRONOTRADE_SMTP_SENHA` com uma
  **senha de app** do Google (Conta Google → Segurança → Senhas de app).
- **WhatsApp**: exige conta no WhatsApp Business Platform da Meta. Preencha `WHATSAPP_TOKEN`,
  `WHATSAPP_PHONE_ID` e `WHATSAPP_MODELO` (um modelo aprovado com uma variável de texto). A Meta cobra
  por mensagem enviada fora de uma conversa aberta pelo cliente.
- **Telegram (grátis, recomendado)**: no Telegram, fale com **@BotFather**, crie um bot e copie o token.
  No `.env`: `TELEGRAM_BOT_TOKEN=...` e `TELEGRAM_BOT_USUARIO=nome_do_bot`. Cada cliente liga em
  **Avisos → Onde receber**: toca no link, aperta "Começar" no Telegram e o Sentinela vincula sozinho.
  Diferente do WhatsApp Cloud API, não há custo por mensagem.
- **IA**: a mesma do TradingAgents (`GOOGLE_API_KEY` e `TRADINGAGENTS_LLM_PROVIDER=google`, por exemplo).
  No servidor, só o administrador escolhe o modelo, porque é ele quem paga.

A situação de cada integração aparece em **Painel do admin → Loja e integrações**.

### Corretora: MetaTrader 5 e Profit (tela Conexões)
A tela **Conexões → Plataformas** é um assistente de três passos: escolher a plataforma, preencher e
**Testar conexão**. O teste mostra uma prévia do que muda no Inventário (🆕 entra, ✏️ muda, ✅ igual,
⚠️ só no app) e só aplica quando a pessoa toca em **Trazer para o Inventário**. Com o botão **Auto**, o
Sentinela sincroniza sozinho a cada ciclo.

- **MetaTrader 5 (o mais fácil, gratuito):** várias corretoras da B3 oferecem o MT5 sem custo. No
  Windows: instale o terminal, entre com a conta (fica logado) e, no Chrono Trade, `pip install MetaTrader5`
  (o `instalar_windows.bat` já pode rodar isso). Com o terminal aberto e logado, **conta e senha são
  opcionais**: é só tocar em Testar conexão.
- **Profit (Nelogica):** o Profit não tem API aberta; o caminho oficial é a **ProfitDLL**, uma licença
  paga à parte, contratada com a Nelogica (ela fornece a chave de ativação e o `ProfitDLL64.dll`, só para
  Windows). O Chrono Trade usa o conector comunitário `pip install profitdll-wrapper`. Preencha o
  caminho da DLL, a chave, usuário e senha da Nelogica e teste. **Valide primeiro no simulador da
  Nelogica**: o conector é novo e o adaptador avisa claramente se algum método faltar.
- **Senhas:** no app instalado, a opção "Lembrar as senhas" guarda num cofre criptografado
  (`cofre.bin` + `.chave_cofre`, na pasta do usuário). Na versão online, nenhuma senha de corretora é
  guardada no servidor.
- **Ordens reais:** desligadas por padrão. Só com `CHRONOTRADE_PERMITIR_ORDENS_REAIS=1` no `.env`
  daquele computador e confirmação a cada ordem. As ordens por voz (Jarvis) vão só para a carteira simulada.
- Outra corretora: crie uma classe em `chronotrade/corretoras/` seguindo `base.py` e registre em
  `chronotrade/conexoes.py`.

### Importar da B3 (grátis, todas as corretoras)
Em **Conexões → Importar da B3**: baixe na Área do Investidor (investidor.b3.com.br → Extratos → Posição)
o Excel da sua posição e solte no app. Ele soma as quantidades de todas as corretoras, mostra a prévia e só
grava quando você confirma. A B3 não informa o preço médio: o app mantém o que você já tinha e, para ativos
novos, começa com o preço de fechamento (ajuste no Inventário).

### Agenda no seu calendário
Em **Agenda de proventos**, o botão **Levar para a minha agenda** baixa um arquivo `.ics`: abra e as datas com
entram no Google Agenda, Outlook ou celular, com lembrete um dia antes.

### Conector do PC (versão online + MT5/Profit)
O MT5 e a ProfitDLL rodam no Windows do cliente, e o servidor online não alcança esse PC. Por isso:
1. O cliente Premium abre **Conexões → Conector do PC**, escolhe a plataforma e toca em
   **Gerar meu atalho do Conector**. Baixa o `conector_chronotrade.bat` (já vem com um token pessoal).
2. Salva o atalho na pasta do Chrono Trade instalado no PC e dá dois cliques. A cada 15 minutos ele lê as
   posições e envia para `https://seu-dominio/api/ponte/posicoes`. Ele **só lê**; não envia ordens.
3. O cliente vê "Última sincronização" na mesma tela e pode **revogar** o atalho quando quiser.

No servidor: suba o serviço `api` junto (`docker compose up -d chronotrade agente api`, ou com
`--profile https ... caddy`), e o Caddy já encaminha `/api/*` para ele. Preencha o endereço público em
**Painel do admin → Comunidade** (ou `CHRONOTRADE_URL` no `.env`).

### Pregão ao vivo, perfil, Notícias e WhatsApp
- **Salão interativo:** cada pessoa é um avatar (a foto dela ou o bonequinho em pixel art) que **anda pelo
  salão**: clique no chão ou use as setas do teclado; no celular, toque. Os outros veem você andando em
  tempo real (a sala atualiza a cada 3 segundos). Clique em alguém para **mandar mensagem privada**, **ver o
  gráfico** que ela mostrou ou **ir até ela**.
- **Gráficos compartilhados:** botão **📈 Gráfico** (ou o comando `/grafico TAEE11 1a comentário`). O gráfico
  aparece num monitor ao lado do seu avatar, no **telão** da sala e na conversa; quem clicar abre o gráfico
  grande, com a média de 200 dias.
- **Conversa:** responder (↪), reações 👍 🔥 💡 🤔, **@apelido** avisa a pessoa citada, `$TAEE11` vira
  etiqueta, apagar a própria mensagem, denunciar. **Mestre do Pregão** (robô): `/cotacao`, `/grafico`,
  `/proventos`, `/quem`, `/ajuda`.
- **Mensagens privadas:** aba ✉️ no Pregão; avisos de mensagem nova no app e contador na barra lateral.
- **Meu perfil:** foto (enviar ou tirar com a câmera; o app recorta, reduz e apaga os dados escondidos da
  imagem), opção **estilo pixel**, **apelido único**, bio de até 140 letras e o bonequinho.
- **Moderação:** 1 mensagem a cada 3 s, até 500 caracteres; denúncia de mensagens e de conversas privadas;
  o admin apaga, silencia e remove fotos em **Painel do admin → Comunidade**. A **TV do Pregão** toca o
  vídeo ou live do YouTube escolhido pelo admin.
- **Notícias e vídeos:** feeds RSS gratuitos (Google Notícias por ativo da carteira, InfoMoney, Money
  Times, buscas sobre B3 e negócios) e canais do YouTube (o admin sugere; cada pessoa adiciona os seus).
  O admin edita as fontes em **Comunidade**, uma por linha: `Nome | endereço` ou `Nome | google:termo`.
- **WhatsApp:** em notícias, Pregão, Jarvis e relatórios há o botão **💬 WhatsApp**: abre o WhatsApp com a
  mensagem pronta (e o aviso de que não é recomendação) para um contato salvo (amigo, consultor,
  família) ou qualquer conversa. Os contatos ficam em **Conexões → Contatos do WhatsApp**. Gratuito: usa
  o link `wa.me`, sem API paga.

### Conta de teste grátis (para o cliente experimentar)
No **Painel do admin → 🎁 Criar conta de teste**: informe o usuário (por exemplo `Teste`), a senha que você
escolher (mínimo 8 caracteres, com letras e números), os dias (30 = 1 mês) e o plano liberado (Premium mostra
tudo). O cliente entra na tela inicial com **"Teste" no campo "E-mail ou usuário"** e a senha. O painel gera
o convite pronto para o WhatsApp, **sem a senha** (mande a senha separada). Pelo terminal:

```
chronotrade-admin teste Teste SUASENHA --dias 30 --plano premium
```

Durante o teste a barra lateral mostra "🎁 Teste grátis: faltam N dias" e o link para assinar. Contas de teste
não contam na receita nem nos assinantes ativos e não recebem e-mail do Sentinela. Ao vencer, os dados ficam
guardados: basta pagar um plano em **Minha conta** para continuar.

### Cores do app (temas)
Quatro temas: **Retrô** (o original), **Verde investidor**, **Laranja energia** e **Clássico** (azul-marinho e
dourado, títulos com serifa). Cada pessoa escolhe em **Meu perfil → Aparência do app**; o admin define o
tema padrão em **Painel do admin → Loja**.

### Chrono Pontos, check-in e loja do avatar
- **Check-in diário** (botão na barra lateral ou em **Pontos e loja**): 10 pontos + 2 por dia de sequência
  (até +14); a cada 7 dias seguidos, +30.
- **Carteira valorizou na semana:** o Sentinela dá 1 ponto a cada 0,1% de alta das posições que já existiam
  (mesmas quantidades no começo e no fim da semana, então aporte novo não conta), até 50 por semana.
- **Conquistas:** primeiro check-in, carteira montada, foto no perfil, primeira conversa, primeiro gráfico no
  telão, primeiro alerta, 7 dias seguidos.
- **Loja:** ternos, smoking, cartola, panamá, coroa, óculos, relógio de ouro, maleta, troféu e molduras para a
  foto. Comprou, toca em **Usar** e o avatar aparece assim no Pregão.
- **Pacotes pelo PIX:** 500 (R$ 4,90), 1.500 (R$ 12,90) e 4.000 pontos (R$ 29,90). O cliente paga e toca em
  "Já paguei"; você confere o PIX (identificador `PONTOSnúmero`) e confirma em **Painel do admin → Pontos**,
  onde também dá pontos ou itens de presente. Pontos não valem dinheiro (está nos termos).

### Webhooks (Discord, Slack, Teams, Google Chat, Zapier, Make)
Em **Avisos → Onde receber**, cole o endereço do webhook do canal e toque em **Mandar um teste**. Os avisos
do Sentinela, alertas de preço e pontos chegam lá também. Só endereços HTTPS desses serviços são aceitos.

### Visual: temas modernos
O padrão agora é o **Esmeralda moderno** (grafite e verde, cartões de vidro, cantos suaves e animações discretas). Há
também **Oceano moderno**, **Verde investidor**, **Laranja energia**, **Clássico** e o **Retrô noite** original. Quem
prefere menos movimento na tela (configuração "reduzir movimento" do sistema) vê o app sem animações. O Portal ganhou
uma linha de atalhos: Próximo aporte, Simular uma crise, Pregão, Check-in e Jarvis.

### Simulador de mercado (plano Médio)
Tela **Mercado → Simulador de mercado**, com três abas:
- **Teste de estresse:** aplica à carteira de hoje as quedas aproximadas de crises que a B3 viveu (Covid 2020,
  crise de 2008, recessão de 2015, choque de juros 2021–22, greve dos caminhoneiros 2018, Joesley Day 2017) ou uma
  crise montada por você. Ações e ETFs são ajustados pelo beta de cada um contra o Ibovespa. Mostra o fundo da
  crise, a perda no papel, o corte nos proventos, o tempo de volta e o caminho mês a mês com e sem aportes
  (quem aporta na queda compra mais barato).
- **Simular intenções:** escreva as compras e vendas que pensa em fazer e veja antes e depois: peso de cada ativo,
  concentração, proventos por mês, caixa e o impacto numa crise. Dá para mandar para a carteira simulada.
- **Futuros possíveis:** milhares de caminhos sorteados a partir dos retornos reais da carteira (bootstrap por
  blocos de um mês), com a faixa provável, a chance de prejuízo e o tamanho de um mês ruim.
Tudo para estudo: não é previsão nem recomendação.

### Jarvis mãos livres (em todas as telas)
O botão redondo no canto inferior direito (ou **Alt+J**) liga o microfone:
- **Sempre ouvindo:** o Jarvis responde quando a frase começa com “Jarvis”. Depois de uma resposta, por 20
  segundos dá para continuar sem repetir o nome. “Jarvis, para de ouvir” desliga.
- **Toque para falar:** toca, fala, e ele para sozinho quando você termina.
Comandos novos: check-in, simular crise (“e se o mercado cair 30%?”), simular compra ou venda, emojis e frases no
Pregão, trocar o tema, ler avisos, confirmar ou cancelar a ordem simulada por voz, repetir. A fala vira texto na voz
local (`chronotrade-voz` ou OpenJarvis); sem ela, pelo Gemini se houver chave. Nenhum áudio é guardado.
Para o reconhecimento entender bem, rode o `chronotrade-voz` com o Whisper `small` ou maior
(`CHRONOTRADE_VOZ_WHISPER=medium` entende melhor, mas pede mais computador). O app tolera variações como
“Javis” e “Jardis” quando o resto da frase é um comando.

### Emojis e frases dos avatares no Pregão
- No salão há uma barra com 12 emojis (👏 🚀 💰 📈 📉 🐂 🐻 🔥 😂 🤝 🎉 ☕). Eles sobem da cabeça do seu avatar e todo
  mundo vê. Atalho: teclas 1 a 0.
- **Frases:** em **Meu perfil → Frases do avatar**, crie até 6 frases (até 80 letras) com a **sua voz gravada**
  (até 8 segundos), com a **voz do Jarvis** ou com a voz do navegador. No salão, toque em **🗣️ Frases** (tecla F) ou
  diga “Jarvis, falar a minha frase 1”: o avatar fala para a sala com balão.
- Frases passam por um filtro (sem promessa de ganho, links, telefones ou ofensas). Quem ouvir algo errado clica
  no avatar → **Denunciar a última frase**; o admin ouve e apaga em **Painel do admin → Pregão → Moderação**.

### Jarvis: comando de voz com o OpenJarvis
O [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) (Stanford, código aberto) é um assistente de IA
que roda no computador da pessoa. O Chrono Trade conversa com ele de dois jeitos:
1. **O app usa o OpenJarvis:** a tela **Jarvis** grava a voz no navegador, manda para
   `/v1/speech/transcribe` (Whisper local), entende o comando em português e responde com voz
   (`/v1/speech/synthesize`, ou a voz do navegador). Conversas livres vão para `/v1/chat/completions`
   com a trava legal (nunca recomenda compra ou venda).
2. **O OpenJarvis usa o Chrono Trade:** o comando `chronotrade-mcp` é um servidor MCP com as ferramentas
   `resumo_carteira`, `proximos_proventos`, `dica_aporte`, `cotacao` e `noticias_ativo`. Cole no
   `~/.openjarvis/config.toml`:
   ```toml
   [tools.mcp]
   enabled = true
   servers = '[{"name": "chronotrade", "command": "chronotrade-mcp", "args": []}]'
   ```

**Voz local do Chrono Trade (o jeito mais leve):** se você só quer o Jarvis ouvindo e falando em
português, sem instalar o OpenJarvis inteiro, use o servidor de voz que vem no projeto. Ele implementa as
mesmas rotas de voz do OpenJarvis, roda 100% offline (Whisper para ouvir, voz brasileira Piper para falar)
e nada sai do seu computador:
```
pip install -e ".[voz]"
chronotrade-voz baixar      # baixa os modelos uma vez (cerca de 900 MB, do GitHub do sherpa-onnx)
chronotrade-voz             # fica ligado na porta 8000
```
No `.env`: `OPENJARVIS_URL=http://localhost:8000`. A tela Jarvis mostra "Voz local do Chrono Trade
conectado". Vozes: `CHRONOTRADE_VOZ=jeff` (padrão), `faber` ou `cadu`.

Instalar o OpenJarvis no Windows (PowerShell): `irm https://open-jarvis.github.io/OpenJarvis/install.ps1 | iex`,
depois `jarvis serve --port 8000`. No `.env`: `OPENJARVIS_URL=http://localhost:8000`. Sem OpenJarvis, a
voz ainda funciona se houver `GOOGLE_API_KEY` (o Gemini transcreve) e os comandos podem ser digitados.

Comandos de exemplo: "cotação da Taesa", "como está o Ibovespa", "qual a dica do aporte?", "próximos
dividendos", "quanto vale minha carteira", "notícias da WEG", "abrir o pregão", "comprar 100 TAEE11 a
35 reais" (carteira simulada, com confirmação), "manda a cotação do Itaú no WhatsApp".

### Backup
Tudo fica no volume `chronotrade_data` (`contas.db`, carteiras e análises). Para copiar:
```bash
docker run --rm -v tradingagents_chronotrade_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/chronotrade_backup_$(date +%F).tar.gz -C /data .
```
O nome exato do volume aparece em `docker volume ls`.

### Atualizar o app
```bash
git pull
docker compose up -d --build chronotrade agente
```

---

## 3. Instalar no Android como aplicativo
1. Abra o endereço do app no **Chrome** do celular.
2. Toque no menu **⋮** e escolha **Adicionar à tela inicial** (ou **Instalar app**).
3. O ícone da ampulheta aparece junto dos outros aplicativos e abre em tela cheia.

---

## 4. Antes de cobrar de verdade
- **CVM:** vender análise de ações específicas (com preço-alvo) é atividade de analista
  credenciado (Resolução CVM 20). O app se apresenta como calculadora com parâmetros do
  próprio usuário, mas consulte um advogado.
- **Dados de mercado:** o Yahoo Finance é para uso pessoal. Numa versão paga, contrate
  um provedor de dados com licença comercial.
- **IA:** no plano gratuito do Gemini, o Google pode usar o que é enviado. Com clientes
  pagantes, use um plano pago.
- **Termos e privacidade:** o texto em **Termos e privacidade** é um modelo. Revise com um advogado.
