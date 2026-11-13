"""Genera koperfield.ico (K) y koperfield_opciones.ico (C): homenaje al icono del Koperfield original (K amarilla
sobre azul marino), pero distinto: esquinas redondeadas, degradado azul-violeta,
borde dorado y un destello mágico."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
S = 1024  # se dibuja grande y se reduce para que quede suave


def destello(d, cx, cy, r, color):
    w = r * 0.22
    d.polygon([(cx, cy - r), (cx + w, cy - w), (cx + r, cy), (cx + w, cy + w),
               (cx, cy + r), (cx - w, cy + w), (cx - r, cy), (cx - w, cy - w)], fill=color)


def dibujar(letra="K"):
    # Fondo: degradado vertical azul marino -> violeta
    fondo = Image.new("RGBA", (S, S))
    top, bot = (16, 24, 120), (70, 20, 140)
    px = fondo.load()
    for y in range(S):
        t = y / (S - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        for x in range(S):
            px[x, y] = c
    mascara = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([16, 16, S - 16, S - 16], radius=200, fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(fondo, (0, 0), mascara)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([16, 16, S - 16, S - 16], radius=200, outline=(255, 205, 40, 255), width=36)

    # K amarilla con sombra
    fuente = ImageFont.truetype(r"C:\Windows\Fonts\georgiab.ttf", 760)
    caja = d.textbbox((0, 0), letra, font=fuente)
    x = (S - (caja[2] - caja[0])) // 2 - caja[0] - 30
    y = (S - (caja[3] - caja[1])) // 2 - caja[1] + 20
    sombra = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).text((x + 22, y + 26), letra, font=fuente, fill=(0, 0, 0, 150))
    img.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.text((x, y), letra, font=fuente, fill=(255, 225, 40, 255))

    # Destello mágico arriba a la derecha
    destello(d, 805, 225, 140, (255, 255, 255, 255))
    destello(d, 880, 400, 55, (255, 240, 170, 255))
    return img


TAMANOS = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]

if __name__ == "__main__":
    # K = Koperfield, C = Configuración (Opciones)
    for letra, nombre in (("K", "koperfield"), ("C", "koperfield_opciones")):
        img = dibujar(letra)
        img.resize((256, 256), Image.LANCZOS).save(os.path.join(AQUI, nombre + ".png"))
        img.save(os.path.join(AQUI, nombre + ".ico"), sizes=TAMANOS)
    print("ok")
