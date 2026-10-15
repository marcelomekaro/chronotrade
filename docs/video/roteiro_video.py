"""Roteiro do vídeo: falas do narrador, comandos do usuário e a síntese das vozes (Piper pt-BR)."""
import json
import re
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, "/tmp/claude-0/tts")
from falar import motor  # noqa: E402

NARRADOR, USUARIO = "pt_BR-faber-medium", "pt_BR-cadu-medium"
OUT = "/tmp/claude-0/video2/audio/"

# id: texto da legenda (o que aparece na tela)
FALAS = {
    "n01": "Todo mês é a mesma cena: o dinheiro do aporte está separado.",
    "n02": "E vem a dúvida: onde eu invisto agora?",
    "n03": "Para viver de dividendos, você usa cinco ferramentas que não conversam: a corretora, a planilha, "
           "o portal de notícias, o grupo de WhatsApp e o YouTube.",
    "n04": "O Chrono Trade junta tudo isso num lugar só. E trabalha por você.",
    "n05": "Um painel feito para o investidor de longo prazo da B3: ações, fundos imobiliários e dividendos.",
    "n06": "Em segundos você vê o patrimônio, quanto os dividendos já pagam por mês "
           "e em quantos anos chega à sua meta de renda.",
    "n07": "A carteira entra sozinha: conecte o MetaTrader 5 ou o Profit, da Nelogica.",
    "n08": "O app testa a conexão, mostra o que vai mudar e só traz para a sua carteira quando você confirma.",
    "n09": "Agora, a pergunta de todo mês tem resposta.",
    "n10": "O Próximo Aporte mostra o que está abaixo do preço justo, o momento do gráfico "
           "e quantas cotas de cada ativo cabem no seu dinheiro.",
    "n11": "E você nem precisa abrir o app: o robô Sentinela vigia a sua carteira e manda a dica no app, "
           "por e-mail e no WhatsApp.",
    "n12": "Prefere perguntar? Converse com o Jarvis.",
    "n13": "Ele também prepara ordens na carteira simulada. Sempre com a sua confirmação.",
    "n14": "A voz funciona no seu computador, com o OpenJarvis ou com a voz local do Chrono Trade.",
    "n15": "E investir não precisa ser solitário.",
    "n16": "No Pregão ao vivo você encontra quem investe como você, em salas de dividendos, "
           "fundos imobiliários e primeiros aportes.",
    "n17": "Com moderação, e sem promessa de ganho fácil.",
    "n18": "Notícias da B3, do mundo dos negócios e dos seus canais do YouTube, filtradas pela sua carteira.",
    "n19": "Gostou de uma ideia? Um toque e ela vai para o amigo ou para o seu consultor.",
    "n20": "No computador ou no celular.",
    "n21": "O plano Básico organiza, o Médio decide e o Premium automatiza. A partir de R$ 19,90 por mês, no PIX, sem fidelidade.",
    "n22": "Este é o Chrono Trade. Invista na B3 um ano de cada vez.",
    "n23": "Ferramenta de estudo. Não é recomendação de investimento: a decisão é sempre sua.",
}

COMANDOS = {
    "u1": "Jarvis, qual a cotação da Taesa?",
    "u2": "Jarvis, compra cem cotas da Taesa.",
}

PRONUNCIA = [
    (r"Chrono Trade", "Crôno Treide"), (r"OpenJarvis", "Ópen Djárvis"), (r"Jarvis", "Djárvis"),
    (r"WhatsApp", "uótsap"), (r"YouTube", "iutúbi"), (r"\bB3\b", "bê três"), (r"MetaTrader 5", "MetaTrader cinco"),
    (r"Profit", "Prófit"), (r"Nelogica", "Nelógica"), (r"R\$ 19,90", "dezenove e noventa"), (r"e-mail", "imêil"),
    (r"Buy and hold", "Bai én rôuld"), (r"PIX", "pix"), (r"Premium", "Prêmium"), (r"Básico", "Bázico"),
]


def para_fala(texto: str) -> str:
    for de, para in PRONUNCIA:
        texto = re.sub(de, para, texto)
    return texto


def sintetizar(voz, texto, saida, velocidade, antes=0.0, depois=0.0):
    a = motor(voz).generate(texto, sid=0, speed=velocidade)
    sr = a.sample_rate
    s = np.array(a.samples, dtype=np.float32)
    s = np.concatenate([np.zeros(int(antes * sr), np.float32), s, np.zeros(int(depois * sr), np.float32)])
    sf.write(saida, s, sr, subtype="PCM_16")
    return len(s) / sr


if __name__ == "__main__":
    import os

    os.makedirs(OUT, exist_ok=True)
    info = {}
    for k, t in FALAS.items():
        info[k] = {"texto": t, "fala": para_fala(t), "voz": "narrador",
                   "dur": sintetizar(NARRADOR, para_fala(t), OUT + k + ".wav", 0.95)}
    for k, t in COMANDOS.items():
        # o arquivo do microfone: 0,4 s de silêncio, a fala e 1,2 s de silêncio
        info[k] = {"texto": t, "fala": para_fala(t), "voz": "usuario",
                   "dur": sintetizar(USUARIO, para_fala(t), OUT + k + ".wav", 1.0, 0.4, 1.2)}
    json.dump(info, open(OUT + "roteiro.json", "w"), ensure_ascii=False, indent=1)
    print(round(sum(v["dur"] for v in info.values()), 1), "s de falas")
