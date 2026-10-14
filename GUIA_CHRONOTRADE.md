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
docker compose --profile https up -d chronotrade caddy
```
Pronto: o app fica em `https://chronotrade.seudominio.com.br`, com certificado automático.
Sem domínio, use `docker compose up -d chronotrade` e acesse `http://IP-DO-SERVIDOR:8501`
(sem HTTPS, as senhas trafegam abertas; use só para testar).

### Primeiro acesso do administrador
1. Entre com o e-mail do administrador e a senha de `CHRONOTRADE_ADMIN_SENHA`.
2. Vá em **Minha conta** e troque a senha.
3. Vá em **Painel do admin → Loja** e preencha preços, chave PIX, nome do recebedor e o seu WhatsApp.
4. Use o **Teste do PIX** (R$ 0,01) para conferir se o dinheiro cai na sua conta.

Esqueceu a senha do administrador? No servidor:
```bash
docker compose exec chronotrade chronotrade-admin senha marcelomekaro@gmail.com
```

### Como funciona a assinatura
1. O cliente cria a conta na tela de entrada. Ela nasce **pendente**.
2. Ele vê o QR Code do PIX com o valor do plano e o botão de mandar o comprovante pelo WhatsApp.
3. Você confere o pagamento no banco e, em **Painel do admin → Pendentes**, clica em **Liberar acesso**
   (plano, dias e valor recebido). O pagamento fica registrado na aba **Pagamentos**.
4. Perto do vencimento, a aba **Cobrança** mostra quem vence e um botão que abre o WhatsApp
   com a mensagem e o PIX prontos.
5. Renovou? Em **Assinantes**, registre o pagamento: os dias são somados à validade atual.

Cliente esqueceu a senha: em **Assinantes**, clique em **Gerar senha temporária** e envie pelo
botão do WhatsApp. Na próxima entrada ele é convidado a trocar.

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
docker compose up -d --build chronotrade
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
