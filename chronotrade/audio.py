"""Áudio curto: deixa gravações leves (WAV mono 16 kHz), corta silêncio e limita a duração."""

from __future__ import annotations

import base64
import io
import wave

import numpy as np

TAXA = 16_000


class ErroAudio(ValueError):
    pass


def ler_wav(dados: bytes) -> tuple[np.ndarray, int]:
    """Amostras float32 mono e a taxa. Aceita WAV PCM 8/16/32 bits ou float (com soundfile, se houver)."""
    try:
        import soundfile as sf

        amostras, taxa = sf.read(io.BytesIO(dados), dtype="float32", always_2d=True)
        return amostras.mean(axis=1).astype(np.float32), int(taxa)
    except ImportError:
        pass
    except Exception as erro:
        raise ErroAudio("Não consegui ler o áudio. Grave de novo.") from erro
    try:
        with wave.open(io.BytesIO(dados)) as w:
            canais, largura, taxa = w.getnchannels(), w.getsampwidth(), w.getframerate()
            brutos = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as erro:
        raise ErroAudio("Não consegui ler o áudio. Grave de novo.") from erro
    tipos = {1: (np.uint8, 128.0, 128.0), 2: (np.int16, 0.0, 32768.0), 4: (np.int32, 0.0, 2147483648.0)}
    if largura not in tipos:
        raise ErroAudio("Formato de áudio não suportado.")
    tipo, centro, escala = tipos[largura]
    amostras = (np.frombuffer(brutos, dtype=tipo).astype(np.float32) - centro) / escala
    if canais > 1:
        amostras = amostras.reshape(-1, canais).mean(axis=1)
    return amostras, taxa


def reamostrar(amostras: np.ndarray, taxa: int, nova: int = TAXA) -> np.ndarray:
    if taxa == nova or len(amostras) == 0:
        return amostras
    n = int(round(len(amostras) * nova / taxa))
    return np.interp(np.linspace(0, len(amostras) - 1, n), np.arange(len(amostras)), amostras).astype(np.float32)


def cortar_silencio(amostras: np.ndarray, taxa: int = TAXA, limiar: float = 0.02, folga: float = 0.15) -> np.ndarray:
    if len(amostras) == 0:
        return amostras
    janela = max(1, int(taxa * 0.02))
    n = len(amostras) // janela
    if n == 0:
        return amostras
    energia = np.sqrt((amostras[: n * janela].reshape(n, janela) ** 2).mean(axis=1))
    pico = energia.max() or 1.0
    falando = np.where(energia > max(limiar, pico * 0.08))[0]
    if len(falando) == 0:
        return amostras[:0]
    extra = int(taxa * folga)
    return amostras[max(0, falando[0] * janela - extra): min(len(amostras), (falando[-1] + 1) * janela + extra)]


def para_wav(amostras: np.ndarray, taxa: int = TAXA) -> bytes:
    pico = float(np.abs(amostras).max()) if len(amostras) else 0.0
    if pico > 0:
        amostras = amostras * min(1.0, 0.92 / pico) if pico > 0.92 else amostras * min(3.0, 0.7 / pico)
    pcm = (np.clip(amostras, -1, 1) * 32767).astype("<i2").tobytes()
    saida = io.BytesIO()
    with wave.open(saida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(pcm)
    return saida.getvalue()


def preparar_frase(dados: bytes, maximo_segundos: float = 8.0) -> tuple[bytes, float]:
    """Gravação da pessoa → WAV leve, sem silêncio nas pontas. Devolve (wav, segundos)."""
    amostras, taxa = ler_wav(dados)
    amostras = cortar_silencio(reamostrar(amostras, taxa))
    segundos = len(amostras) / TAXA
    if segundos < 0.3:
        raise ErroAudio("Não ouvi nada. Fale mais perto do microfone.")
    if segundos > maximo_segundos:
        amostras = amostras[: int(maximo_segundos * TAXA)]
        segundos = maximo_segundos
    return para_wav(amostras), round(segundos, 1)


def data_uri(wav: bytes, tipo: str = "audio/wav") -> str:
    return f"data:{tipo};base64,{base64.b64encode(wav).decode()}"
