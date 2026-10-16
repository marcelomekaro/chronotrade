# Publicar o Chrono Trade: pelo VS Code e no Render

Este guia tem dois caminhos:

1. **VS Code**: rodar, testar e publicar sem decorar comandos (tarefas e botões prontos).
2. **Render**: colocar o app online com HTTPS, disco para os dados e deploy automático a cada `git push`.

Os arquivos já estão no projeto:

| Arquivo | Para quê |
|---|---|
| `.vscode/launch.json` | Botões de **Executar e depurar** (F5): modo pessoal, modo servidor, igual ao Render, agente, voz, testes |
| `.vscode/tasks.json` | **Tarefas**: instalar, rodar, testar, Docker, publicar no Render, senha do admin |
| `.vscode/settings.json` e `extensions.json` | Python da `.venv`, testes, ruff e as extensões recomendadas |
| `.devcontainer/devcontainer.json` | Abrir tudo pronto num contêiner ou no GitHub Codespaces |
| `render.yaml` | **Blueprint do Render**: serviço web, disco `/data`, variáveis e deploy automático |
| `Dockerfile.render` e `deploy/render/iniciar.sh` | A imagem do Render: liga o agente Sentinela e o app no mesmo serviço |

---

## 1. No VS Code

### Primeira vez (uns 5 minutos)
1. Instale o [VS Code](https://code.visualstudio.com/), o [Python 3.11 ou mais novo](https://www.python.org/downloads/) e o [Git](https://git-scm.com/).
2. Descompacte o projeto e abra a pasta `TradingAgents` no VS Code (**Arquivo → Abrir pasta**).
3. Aceite **Instalar as extensões recomendadas** (aparece no canto). São Python, Ruff, Docker e YAML.
4. Copie `.env.example` para `.env` e preencha o que for usar (pelo menos `GOOGLE_API_KEY` para a IA).
5. `Ctrl+Shift+P` → **Tasks: Run Task** → **1. Instalar**. Cria a `.venv` e instala tudo.
6. `Ctrl+Shift+P` → **Python: Select Interpreter** → escolha o da `.venv`.

### Rodar e depurar
- Aba **Executar e depurar** (`Ctrl+Shift+D`) → escolha e aperte **F5**:
  - **Chrono Trade: modo pessoal**: só você, sem login, em http://localhost:8501
  - **Chrono Trade: modo servidor**: com contas, planos e PIX, em http://localhost:8502. Entre como
    `marcelomekaro@gmail.com`, senha `marcelomekaro@gmail.com`.
  - **Igual ao Render**: roda o mesmo script do Render (agente + app) em http://localhost:10000 (Linux/Mac;
    no Windows use a tarefa 4, com Docker).
  - **Agente Sentinela: um ciclo agora**, **Voz local do Jarvis**, **Testes**.
- Dá para pôr pontos de parada (clique à esquerda do número da linha) em qualquer tela do app.

### Tarefas prontas (`Ctrl+Shift+P` → Tasks: Run Task)
| Tarefa | O que faz |
|---|---|
| 3. Testes e verificação | pytest + ruff (rode antes de publicar) |
| 4. Docker: imagem do Render | monta exatamente a imagem do Render e roda em http://localhost:10000 |
| 5. Docker: servidor completo | app + agente + API do Conector do PC (para VPS) |
| 6. Publicar no Render | `git add`, `commit` e `push`: o Render publica sozinho |
| 7. Render: forçar um deploy | chama o Deploy Hook do Render (pede o endereço na hora, não fica salvo) |
| 8. Admin: senha igual ao e-mail | volta a senha do administrador para `marcelomekaro@gmail.com` |

### Sem instalar nada: GitHub Codespaces ou contêiner
Com a extensão **Dev Containers**, use **Reopen in Container**. No GitHub, **Code → Codespaces → Create**.
O ambiente vem com Python e as dependências instaladas; as portas 8501 e 10000 abrem sozinhas.

---

## 2. No Render

### O que você precisa saber antes
- **Use um plano pago.** O plano gratuito do Render apaga os arquivos a cada reinício e não aceita disco
  persistente: contas, carteiras e o Pregão sumiriam. Ele também "dorme" depois de 15 minutos sem visitas.
- O `render.yaml` usa o **menor plano pago** (0,5 CPU, 512 MB) com **1 GB de disco** em `/data`. Com muitos
  usuários ao mesmo tempo, suba para `1c-2g` no painel. Confira os preços em [render.com/pricing](https://render.com/pricing).
- Com disco, o serviço roda numa instância só e cada deploy fica uns segundos fora do ar.
- A **região** escolhida é Virginia (a mais próxima do Brasil entre as opções). Ela não muda depois de criada.

### Passo a passo
1. **Suba o projeto para o GitHub** (no VS Code: aba **Controle do código-fonte** → **Publicar no GitHub**,
   repositório **privado**). O `.env` não vai junto: ele está no `.gitignore`.
2. No [Render](https://dashboard.render.com): **New → Blueprint** → conecte o GitHub → escolha o repositório.
3. O Render lê o `render.yaml` e pede os valores secretos. Preencha:
   - `GOOGLE_API_KEY`: a sua chave do Gemini;
   - `MERCADOPAGO_ACCESS_TOKEN`: para o PIX liberar o plano sozinho;
   - os de e-mail (`CHRONOTRADE_SMTP_*`), Telegram e WhatsApp, se for usar;
   - `CHRONOTRADE_ADMIN_SENHA`: **deixe vazio** para a senha inicial do admin ser o próprio e-mail.
4. **Apply**. O primeiro deploy leva uns 5 a 10 minutos (monta a imagem). Quando ficar verde, abra o endereço
   `https://chronotrade-xxxx.onrender.com`.
5. Entre com `marcelomekaro@gmail.com` e a senha `marcelomekaro@gmail.com`. Em **Painel do admin → Loja e
   integrações**, confira preços, PIX, WhatsApp e a **URL pública** (o endereço do Render).
6. **Domínio próprio** (opcional): no serviço → **Settings → Custom Domains** → adicione, por exemplo,
   `app.chronotrade.com.br` e crie no seu provedor de domínio o registro que o Render mostrar. O certificado
   HTTPS é automático.

### Depois disso, publicar é só `git push`
Cada `git push` na branch conectada publica sozinho (`autoDeployTrigger: commit`). No VS Code, use a tarefa
**6. Publicar no Render**. Para publicar sem commit novo, copie o **Deploy Hook** (Settings → Deploy Hook) e
use a tarefa **7**.

### Como funciona por dentro
- `Dockerfile.render` instala o pacote e roda `deploy/render/iniciar.sh`.
- O script liga o **agente Sentinela** em segundo plano (dicas, alertas, datas com, lembrete do DARF,
  pagamentos PIX, foto diária do patrimônio, carteiras virtuais). Se ele cair, ele volta sozinho em 30 s.
  Depois o script liga o app na porta que o Render define (`PORT`).
- Tudo que precisa durar fica no disco `/data`: contas, carteiras, Pregão, pontos, frases e músicas.
- O Render verifica a saúde do app em `/_stcore/health`.

### Backup
No Render: serviço → **Disks** → os snapshots diários são automáticos. Para guardar uma cópia sua, use o
**Shell** do serviço: `tar czf /tmp/backup.tgz /data`. Dá para baixar pelo
`render ssh` ou com `scp` (veja a documentação do Render sobre SSH).

### O que fica de fora no Render
- **Conector do PC** (MetaTrader 5 e Profit sincronizando com a versão online): ele precisa de uma segunda porta
  (`chronotrade-api`), e no Render o disco não pode ser dividido entre dois serviços. Para isso, use a VPS com
  `docker compose` (tarefa 5 e o GUIA). A importação da B3 e as carteiras manuais funcionam normalmente.
- **Voz local do Jarvis**: os modelos de voz são pesados para o plano pequeno. No Render, o Jarvis ouve pelo
  Gemini (com a `GOOGLE_API_KEY`) e responde com a voz do navegador. Quem quiser voz offline roda o
  `chronotrade-voz` no próprio PC.

### Se algo der errado
| Sintoma | O que fazer |
|---|---|
| Deploy falhou na montagem | Veja **Logs** do deploy; rode a tarefa 4 no seu PC para reproduzir |
| App abre mas some tudo depois de um deploy | O disco não está montado: confira **Disks** com `/data` |
| "Out of memory" nos logs | Suba o plano para `1c-2g` |
| Esqueceu a senha do admin | **Shell** do serviço: `chronotrade-admin senha-email` |
| Agente não manda avisos | Logs devem mostrar `Sentinela: {...}` a cada ciclo; confira e-mail/Telegram no `.env` do Render |

---

Desenvolvido por **Marcelo Mekaro** · marcelomekaro@gmail.com · WhatsApp (19) 99965-0436
