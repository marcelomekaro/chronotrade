# Guia do Chrono Trade

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
| Oráculo de IA | | | 30 análises por mês |
| Corretora real (MetaTrader 5) | | | ✅ |

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
- executa as ordens limitadas da carteira simulada.

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
- **IA**: a mesma do TradingAgents (`GOOGLE_API_KEY` e `TRADINGAGENTS_LLM_PROVIDER=google`, por exemplo).
  No servidor, só o administrador escolhe o modelo, porque é ele quem paga.

A situação de cada integração aparece em **Painel do admin → Loja e integrações**.

### Corretora
- **Carteira simulada** (Médio e Premium): R$ 100.000 de mentira para treinar ordens a mercado e limitadas.
- **MetaTrader 5** (Premium): funciona com o app **instalado no computador Windows** do cliente, com o
  terminal MT5 da corretora aberto. Traz as posições reais para o Inventário. Ordens reais só com
  `CHRONOTRADE_PERMITIR_ORDENS_REAIS=1` no `.env` daquele computador, e cada ordem pede confirmação.
- Outras corretoras: crie uma classe em `chronotrade/corretoras/` seguindo `base.py`.

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
