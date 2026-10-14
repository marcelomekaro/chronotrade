"""Texto dos termos de uso e da política de privacidade (modelo para revisar com um advogado)."""

from __future__ import annotations

from chronotrade.contas import email_admin


def texto_termos(cfg: dict[str, str]) -> str:
    loja = cfg.get("nome_loja") or "Chrono Trade"
    contato = email_admin()
    return f"""
**1. O que é o {loja}.** Uma ferramenta de organização e estudo de carteiras de investimento.
Os números (preço justo, preço de entrada, projeções, pareceres da IA) vêm de fórmulas
automáticas com parâmetros escolhidos por você. **Não são recomendação de investimento**,
nem análise feita por analista credenciado na CVM. Decisões de compra e venda são suas.

**2. Dados de mercado.** Cotações e proventos vêm de fontes públicas da internet e podem
ter atraso, falhas ou erros. Confira na sua corretora antes de operar.

**3. Assinatura.** O plano Completo é pago antecipadamente, por PIX, e libera o acesso
pelo período contratado. Não há renovação automática nem cobrança recorrente. Você pode
desistir em até 7 dias após o pagamento e receber o valor de volta (direito de arrependimento).

**4. Seus dados (LGPD).** Guardamos nome, e-mail, WhatsApp (se informado), senha (só
em forma criptografada, que ninguém consegue ler) e a carteira que você cadastra. Eles
servem apenas para o app funcionar e para falar com você sobre a assinatura. Não vendemos
nem compartilhamos com terceiros. Os pareceres de IA enviam o ticker analisado e, se
você permitir, a sua carteira ao provedor de IA. Você pode baixar os seus dados ou excluir
a sua conta a qualquer momento em **Minha conta**.

**5. Contato.** {contato}

_Modelo de termos. Revise com um advogado antes de cobrar pelo acesso._
"""
