"""Texto dos termos de uso, avisos de risco e política de privacidade (modelo para revisar com um advogado)."""

from __future__ import annotations

from chronotrade.contas import email_admin
from chronotrade.legal import AVISO_LEGAL


def texto_termos(cfg: dict[str, str]) -> str:
    loja = cfg.get("nome_loja") or "Chrono Trade"
    contato = email_admin()
    whatsapp = cfg.get("whatsapp_admin", "")
    return f"""
**1. O que é o {loja}.** Uma ferramenta de organização e estudo de carteiras de investimento.
Preço justo, preço de entrada, momento técnico, projeções, agenda de proventos, dicas do agente
Sentinela e pareceres de IA vêm de fórmulas e modelos automáticos, com parâmetros escolhidos por
você. **Não são recomendação de investimento**, consultoria de valores mobiliários (Resolução CVM 19)
nem relatório de análise elaborado por analista credenciado (Resolução CVM 20).

**2. Responsabilidade do investidor.** A decisão de comprar, vender ou manter qualquer ativo, o valor
de cada aporte e os riscos envolvidos são exclusivamente seus. Investimentos em renda variável podem
perder valor; rentabilidade e proventos passados não garantem resultados futuros. Antes de investir,
avalie o seu perfil (suitability) com a sua corretora.

**3. Dados de mercado.** Cotações, proventos e datas vêm de fontes públicas da internet e podem ter
atraso, falhas ou erros. Datas e valores "previstos" repetem o histórico e podem não se confirmar.
Confira na sua corretora e no site de relações com investidores da empresa antes de operar.

**4. Corretoras e ordens.** A carteira simulada não usa dinheiro real. A conexão com corretora
(MetaTrader 5 ou Profit/ProfitDLL) roda no seu computador, com a sua conta; ordens reais ficam desligadas
até você ligá-las e cada uma pede confirmação. A ProfitDLL é licenciada pela Nelogica e o MetaTrader 5 é
fornecido pela sua corretora: termos, custos e disponibilidade são deles. Senhas de corretora não são
guardadas no servidor; no app instalado, ficam num cofre criptografado no seu PC, se você escolher.
O Conector do PC só envia posições (ativo, quantidade e preço médio). Você é responsável pelas ordens enviadas.

**5. Pregão, notícias, WhatsApp e Jarvis.** No Pregão, as mensagens são opiniões pessoais de cada
participante e não recomendações de investimento. É proibido prometer ganhos, oferecer serviços de
consultoria ou gestão sem registro na CVM, divulgar dados pessoais, fazer propaganda, ofender ou
combinar operações para manipular preços. Mensagens podem ser denunciadas, apagadas pelo administrador,
e quem descumprir as regras pode ser silenciado ou bloqueado. Notícias e vídeos vêm de fontes públicas
de terceiros (RSS e YouTube), que respondem pelo próprio conteúdo. O compartilhamento no WhatsApp só abre o
aplicativo com o texto pronto: o {loja} não lê nem guarda as suas conversas. O Jarvis (voz) usa o
OpenJarvis instalado no seu computador ou, se você configurar, o Gemini do Google para transcrever o áudio;
ordens por voz vão apenas para a carteira simulada, com confirmação. A foto e o apelido do seu perfil ficam
visíveis para os participantes do Pregão; use uma foto sua, e a moderação pode removê-la. Mensagens privadas
ficam guardadas no servidor e podem ser analisadas pela moderação quando há denúncia.

**6. Assinatura.** Os planos Básico, Médio e Premium são pagos antecipadamente por PIX e liberam o acesso
pelo período contratado (mensal ou anual). Não há renovação automática nem cobrança recorrente. Você pode
desistir em até 7 dias após o pagamento e receber o valor de volta (direito de arrependimento, art. 49
do Código de Defesa do Consumidor). Contas de teste grátis valem pelo prazo informado, não geram cobrança
e, ao fim do teste, a carteira e o avatar ficam guardados até você assinar ou excluir a conta.

**6.1 Chrono Pontos e loja do avatar.** Pontos são ganhos com check-in diário, conquistas e valorização
semanal da carteira, ou comprados em pacotes pelo PIX. Eles servem só para personalizar o avatar (trajes,
chapéus, acessórios e molduras): não têm valor monetário, não são transferíveis nem resgatáveis em dinheiro e
não são recomendação nem prêmio por desempenho de investimento. Pacotes comprados podem ser cancelados em até
7 dias, com devolução do valor, enquanto os pontos não forem usados.

**7. Seus dados (LGPD).** Guardamos nome, e-mail, WhatsApp, senha (só em forma criptografada, que
ninguém consegue ler), a carteira que você cadastra e os avisos enviados. Eles servem para o app
funcionar, para enviar os avisos que você escolher (no app, por e-mail ou WhatsApp) e para falar com
você sobre a assinatura. Não vendemos nem compartilhamos com terceiros, exceto os prestadores
necessários: o provedor de IA (recebe os ativos analisados e, se você permitir, a carteira), o
Mercado Pago (pagamentos) e os serviços de e-mail e WhatsApp. No Pregão, os outros participantes veem o
seu apelido, o avatar e as mensagens que você enviar. Você pode baixar os seus dados, mudar as
preferências de aviso ou excluir a conta a qualquer momento em **Minha conta**.

**8. Contato.** {contato}{f", WhatsApp {whatsapp}" if whatsapp else ""}

**Aviso de risco.** {AVISO_LEGAL}

_Modelo de termos. Revise com um advogado antes de cobrar pelo acesso._
"""
