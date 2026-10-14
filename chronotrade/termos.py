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
(MetaTrader 5) roda no seu computador, com a sua conta; ordens reais ficam desligadas até você ligá-las
e cada uma pede confirmação. Você é responsável pelas ordens enviadas.

**5. Assinatura.** Os planos Básico, Médio e Premium são pagos antecipadamente por PIX e liberam o acesso
pelo período contratado (mensal ou anual). Não há renovação automática nem cobrança recorrente. Você pode
desistir em até 7 dias após o pagamento e receber o valor de volta (direito de arrependimento, art. 49
do Código de Defesa do Consumidor).

**6. Seus dados (LGPD).** Guardamos nome, e-mail, WhatsApp, senha (só em forma criptografada, que
ninguém consegue ler), a carteira que você cadastra e os avisos enviados. Eles servem para o app
funcionar, para enviar os avisos que você escolher (no app, por e-mail ou WhatsApp) e para falar com
você sobre a assinatura. Não vendemos nem compartilhamos com terceiros, exceto os prestadores
necessários: o provedor de IA (recebe os ativos analisados e, se você permitir, a carteira), o
Mercado Pago (pagamentos) e os serviços de e-mail e WhatsApp. Você pode baixar os seus dados, mudar as
preferências de aviso ou excluir a conta a qualquer momento em **Minha conta**.

**7. Contato.** {contato}{f", WhatsApp {whatsapp}" if whatsapp else ""}

**Aviso de risco.** {AVISO_LEGAL}

_Modelo de termos. Revise com um advogado antes de cobrar pelo acesso._
"""
