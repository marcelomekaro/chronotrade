"""Voz local do Jarvis: um servidor pequeno, 100% offline, que fala a mesma língua do OpenJarvis.

Para quem quer o Jarvis falando e ouvindo em português sem instalar o OpenJarvis inteiro.
Implementa as rotas de voz do OpenJarvis, então a tela Jarvis usa sem mudar nada:

    GET  /health                  GET /v1/speech/health
    POST /v1/speech/transcribe    (Whisper, ouve o português)
    POST /v1/speech/synthesize    (Piper, voz brasileira)

Instalar e rodar no seu PC:

    pip install -e ".[voz]"
    chronotrade-voz baixar        # baixa os modelos (uns 900 MB, uma vez só)
    chronotrade-voz               # liga na porta 8000; no .env: OPENJARVIS_URL=http://localhost:8000

Os modelos vêm do projeto sherpa-onnx (Apache 2.0) e das vozes Piper (pt_BR). Nada sai do seu computador.
"""

from __future__ import annotations

import io
import os
import sys
import tarfile
import threading
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

VOZES = {"faber": "pt_BR-faber-medium", "jeff": "pt_BR-jeff-medium", "cadu": "pt_BR-cadu-medium"}
BASE_TTS = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-{}.tar.bz2"
BASE_ASR = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-{}.tar.bz2"
LIMITE_TEXTO = 4000


def pasta_modelos() -> Path:
    from chronotrade.carteira import pasta_dados

    return Path(os.environ.get("CHRONOTRADE_VOZ_MODELOS") or pasta_dados() / "modelos_voz")


def voz_escolhida() -> str:
    nome = os.environ.get("CHRONOTRADE_VOZ", "jeff")
    return VOZES.get(nome, nome)


def tamanho_whisper() -> str:
    return os.environ.get("CHRONOTRADE_VOZ_WHISPER", "small")


def baixar(destino: Path | None = None) -> None:
    destino = destino or pasta_modelos()
    destino.mkdir(parents=True, exist_ok=True)
    urls = [BASE_TTS.format(voz_escolhida()), BASE_ASR.format(tamanho_whisper())]
    for url in urls:
        nome = url.rsplit("/", 1)[1].replace(".tar.bz2", "")
        if (destino / nome).exists():
            print(f"Já baixado: {nome}")
            continue
        print(f"Baixando {nome} (pode levar alguns minutos)…")
        with urllib.request.urlopen(url, timeout=600) as resposta:
            dados = resposta.read()
        with tarfile.open(fileobj=io.BytesIO(dados), mode="r:bz2") as tar:
            tar.extractall(destino, filter="data")
    print(f"Pronto. Modelos em {destino}")


class Pedido(BaseModel):
    text: str
    voice_id: str | None = None
    speed: float | None = None


class Voz:
    """Carrega os modelos na primeira vez que são usados."""

    def __init__(self, pasta: Path | None = None):
        self.pasta = pasta or pasta_modelos()
        self._tts = self._asr = None
        self._trava = threading.Lock()

    def falante(self):
        import sherpa_onnx

        with self._trava:
            if self._tts is None:
                voz = voz_escolhida()
                d = self.pasta / f"vits-piper-{voz}"
                cfg = sherpa_onnx.OfflineTtsConfig(
                    model=sherpa_onnx.OfflineTtsModelConfig(
                        vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=str(d / f"{voz}.onnx"),
                                                                   tokens=str(d / "tokens.txt"),
                                                                   data_dir=str(d / "espeak-ng-data")),
                        num_threads=2),
                    max_num_sentences=2)
                self._tts = sherpa_onnx.OfflineTts(cfg)
            return self._tts

    def ouvinte(self):
        import sherpa_onnx

        with self._trava:
            if self._asr is None:
                t = tamanho_whisper()
                d = self.pasta / f"sherpa-onnx-whisper-{t}"
                self._asr = sherpa_onnx.OfflineRecognizer.from_whisper(
                    encoder=str(d / f"{t}-encoder.int8.onnx"), decoder=str(d / f"{t}-decoder.int8.onnx"),
                    tokens=str(d / f"{t}-tokens.txt"), language="pt", task="transcribe", num_threads=2)
            return self._asr

    def pronta(self) -> bool:
        voz, t = voz_escolhida(), tamanho_whisper()
        return (self.pasta / f"vits-piper-{voz}").exists() and (self.pasta / f"sherpa-onnx-whisper-{t}").exists()

    def transcrever(self, audio: bytes) -> tuple[str, float]:
        import numpy as np
        import soundfile as sf

        dados, taxa = sf.read(io.BytesIO(audio), dtype="float32", always_2d=True)
        mono = dados.mean(axis=1).astype(np.float32)
        rec = self.ouvinte()
        fluxo = rec.create_stream()
        fluxo.accept_waveform(taxa, mono)
        rec.decode_stream(fluxo)
        return fluxo.result.text.strip(), len(mono) / taxa

    def sintetizar(self, texto: str, velocidade: float = 1.0) -> bytes:
        import soundfile as sf

        audio = self.falante().generate(texto[:LIMITE_TEXTO], sid=0, speed=velocidade)
        saida = io.BytesIO()
        sf.write(saida, audio.samples, audio.sample_rate, format="WAV", subtype="PCM_16")
        return saida.getvalue()


def criar_app(voz: Voz | None = None):
    voz = voz or Voz()
    app = FastAPI(title="Chrono Trade, voz local", description="Rotas de voz compatíveis com o OpenJarvis.")

    @app.get("/health")
    def saude():
        return {"status": "ok", "servico": "chronotrade-voz"}

    @app.get("/v1/speech/health")
    def saude_voz():
        pronta = voz.pronta()
        return {"available": pronta, "backend": "sherpa-onnx",
                **({} if pronta else {"reason": "Rode: chronotrade-voz baixar"})}

    @app.post("/v1/speech/transcribe")
    async def transcrever(request: Request):
        form = await request.form()
        arquivo = form.get("file")
        if arquivo is None:
            raise HTTPException(400, "Missing 'file' field")
        try:
            texto, duracao = voz.transcrever(await arquivo.read())
        except Exception as erro:
            raise HTTPException(500, f"Não consegui ouvir: {erro}") from erro
        return {"text": texto, "language": "pt", "confidence": None, "duration_seconds": duracao}

    @app.post("/v1/speech/synthesize")
    def sintetizar(pedido: Pedido):
        texto = pedido.text.strip()
        if not texto:
            raise HTTPException(400, "Missing 'text'")
        if len(texto) > LIMITE_TEXTO:
            raise HTTPException(413, f"Text exceeds {LIMITE_TEXTO} characters")
        return Response(voz.sintetizar(texto, pedido.speed or 1.0), media_type="audio/wav")

    return app


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "baixar":
        baixar()
        return
    import uvicorn

    voz = Voz()
    if not voz.pronta():
        print("Modelos de voz não encontrados. Rode primeiro: chronotrade-voz baixar")
    else:  # carrega os modelos já, para a primeira fala do modo mãos livres não demorar
        threading.Thread(target=lambda: (voz.ouvinte(), voz.falante()), daemon=True).start()
    uvicorn.run(criar_app(voz), host=os.environ.get("CHRONOTRADE_VOZ_HOST", "127.0.0.1"),
                port=int(os.environ.get("CHRONOTRADE_VOZ_PORTA", "8000")))


if __name__ == "__main__":
    main()
