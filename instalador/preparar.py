"""Etapas comuns do instalador: ícone .ico, termos em texto e LEIA-ME. Uso: python preparar.py PASTA_APP"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
app = Path(sys.argv[1])
app.mkdir(parents=True, exist_ok=True)

from PIL import Image  # noqa: E402

Image.open(RAIZ / "chronotrade" / "static" / "icone-512.png").convert("RGBA").save(
    app / "icone.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

texto = (RAIZ / "chronotrade" / "termos.py").read_text(encoding="utf-8")
inicio = texto.index('return f"""') + len('return f"""')
termos = texto[inicio:texto.index('"""', inicio)]
termos = (termos.replace("{loja}", "Chrono Trade").replace("{contato}", "marcelomekaro@gmail.com")
          .replace('{f", WhatsApp {whatsapp}" if whatsapp else ""}', ", WhatsApp (19) 99965-0436").replace("**", ""))
import re  # noqa: E402

termos = re.sub(r"\{[^{}]*\}", "", termos)
(app.parent / "termos.txt").write_text("TERMOS DE USO E PRIVACIDADE DO CHRONO TRADE\r\n\r\n" + termos.strip().replace("\n", "\r\n"),
                                       encoding="utf-8-sig")
(app / "LEIA-ME.txt").write_text(
    "Chrono Trade\r\n============\r\n\r\n"
    "Abrir: atalho \"Chrono Trade\" na área de trabalho. O app abre no navegador (http://localhost:8501).\r\n"
    "Fechar: menu Iniciar > Chrono Trade > Fechar o Chrono Trade.\r\n"
    "Seus dados e chaves: %USERPROFILE%\\.chronotrade (a carteira e o arquivo .env com a GOOGLE_API_KEY).\r\n"
    "Registro de erros: %USERPROFILE%\\.chronotrade\\chronotrade.log\r\n\r\n"
    "Desenvolvido por Marcelo Mekaro - marcelomekaro@gmail.com - WhatsApp (19) 99965-0436\r\n", encoding="utf-8-sig")
for nome in ("ChronoTrade.pyw", "Fechar.pyw"):
    (app / nome).write_bytes((Path(__file__).parent / nome).read_bytes())
print("ok")
