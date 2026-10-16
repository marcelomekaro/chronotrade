"""Nome, slogan e frases da marca, num lugar só."""

NOME = "Chrono Trade"
SLOGAN = "Buy and hold diário. Prosperidade no longo prazo."
SLOGAN_CURTO = "Buy and hold diário, prosperidade no longo prazo"
PROMESSA = ("Um pouco de atenção todo dia, sem ansiedade: o app vigia preços, dividendos e notícias, "
            "e você vê a sua prosperidade crescer no longo prazo.")

DESENVOLVEDOR = "Marcelo Mekaro"
CONTATO_EMAIL = "marcelomekaro@gmail.com"
WHATSAPP = "5519999650436"
WHATSAPP_EXIBIR = "(19) 99965-0436"
CREDITO = f"Desenvolvido por {DESENVOLVEDOR}"


def link_whatsapp(texto: str = "Olá, Marcelo! Vim pelo Chrono Trade.") -> str:
    from urllib.parse import quote

    return f"https://wa.me/{WHATSAPP}?text={quote(texto)}"


def credito_html() -> str:
    """Rodapé com o crédito e o contato do desenvolvedor."""
    return (f'<div class="ct-credito">{CREDITO}<br>'
            f'<a href="mailto:{CONTATO_EMAIL}">{CONTATO_EMAIL}</a> · '
            f'<a href="{link_whatsapp()}" target="_blank" rel="noopener">WhatsApp {WHATSAPP_EXIBIR}</a></div>')
