"""
Módulo plantilla_correo

Arma el cuerpo HTML del correo de alerta a partir del contenido que devuelve Copilot.
Copilot pone el contenido (título, resumen, hallazgos, impacto, acciones) y este módulo
pone la forma: franja de color según importancia, negrillas, secciones y espaciado.

HTML pensado para Outlook (escritorio usa el motor de Word):
- solo tablas y estilos en línea (Outlook ignora <style>, CSS externo, display, max-width...)
- los colores de fondo van también como atributo bgcolor, que es lo único que Outlook respeta siempre
- el resultado sale en UNA sola línea (compactar_html): el correo pasa por una celda de Excel
  y por Power Automate, y los saltos de línea entre etiquetas terminan convertidos en <br>
  sueltos o en espacios que desarman la tabla.

Uso:
    html = armar_correo_html(datos, "ALTA")
    # datos = {"titulo": ..., "resumen": ..., "hallazgos": [...], "impacto": ..., "acciones": [...]}

    html = texto_a_html("texto plano de respaldo", "MEDIA")   # si Copilot no devolvió el JSON por partes
"""

import re
import html
import datetime

import src.config as config


FUENTE = "font-family:'Segoe UI',Arial,sans-serif;"


def _formatear(texto):
    """Escapa el texto y convierte **negrilla** en <b>negrilla</b> y los saltos de línea en <br>."""
    seguro = html.escape(str(texto or "").strip())
    seguro = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", seguro)
    return seguro.replace("\r\n", "\n").replace("\n", "<br>")


def compactar_html(codigo):
    """
    Deja el HTML en una sola línea sin cambiar lo que se ve.
    Solo quita los saltos de línea (y la sangría que los rodea) de la plantilla; el texto de
    Copilot ya llega sin saltos (_formatear los vuelve <br>), así que no se pierden espacios
    entre palabras, por ejemplo entre dos negrillas seguidas.
    """
    return re.sub(r"[ \t]*[\r\n]+[ \t]*", "", codigo.strip())


def _lista(items, ordenada=False):
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return ""
    etiqueta = "ol" if ordenada else "ul"
    filas = "".join(
        f'<li style="margin:0 0 8px 0;">{_formatear(i)}</li>' for i in items
    )
    return f'<{etiqueta} style="margin:0 0 0 22px;padding:0;">{filas}</{etiqueta}>'


def _seccion(titulo, contenido_html):
    if not contenido_html:
        return ""
    return (
        '<tr><td style="padding:0 32px 22px 32px;">'
        f'<p style="margin:0 0 8px 0;font-size:12px;font-weight:bold;letter-spacing:1px;'
        f'text-transform:uppercase;color:#6B7280;{FUENTE}">{titulo}</p>'
        f'<div style="font-size:14px;line-height:1.6;color:#1F2937;{FUENTE}">{contenido_html}</div>'
        "</td></tr>"
    )


def _caja_impacto(texto, color):
    """Caja gris con borde de color a la izquierda (hecha con tabla: Outlook no respeta border-left en div)."""
    if not str(texto or "").strip():
        return ""
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td width="4" bgcolor="{color}" style="background-color:{color};width:4px;font-size:0;line-height:0;">&nbsp;</td>'
        f'<td bgcolor="#F9FAFB" style="background-color:#F9FAFB;padding:12px 16px;font-size:14px;'
        f'line-height:1.6;color:#1F2937;{FUENTE}">{_formatear(texto)}</td></tr></table>'
    )


def armar_correo_html(datos, importancia):
    """Devuelve el HTML completo del correo, en una sola línea."""
    importancia = str(importancia).upper()
    color = config.CORREO_COLORES_IMPORTANCIA.get(importancia, "#6B7280")
    fecha = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    titulo = _formatear(datos.get("titulo") or "Alerta del sistema de monitoreo")
    resumen = _formatear(datos.get("resumen"))
    hallazgos = _lista(datos.get("hallazgos"))
    acciones = _lista(datos.get("acciones"), ordenada=True)
    impacto = _caja_impacto(datos.get("impacto"), color)

    cuerpo = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#F3F4F6" style="background-color:#F3F4F6;{FUENTE}">
<tr><td align="center" style="padding:24px 8px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" bgcolor="#FFFFFF" style="width:640px;background-color:#FFFFFF;border:1px solid #E5E7EB;">
<tr><td height="6" bgcolor="{color}" style="height:6px;background-color:{color};font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:28px 32px 8px 32px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
<td bgcolor="{color}" style="background-color:{color};color:#FFFFFF;font-size:11px;font-weight:bold;letter-spacing:1px;padding:4px 10px;{FUENTE}">IMPORTANCIA {html.escape(importancia)}</td>
<td style="padding-left:10px;font-size:12px;color:#6B7280;{FUENTE}">{fecha}</td>
</tr></table>
</td></tr>
<tr><td style="padding:8px 32px 18px 32px;font-size:22px;line-height:1.3;font-weight:bold;color:#111827;{FUENTE}">{titulo}</td></tr>
<tr><td style="padding:0 32px 22px 32px;font-size:15px;line-height:1.6;color:#1F2937;{FUENTE}">{html.escape(config.CORREO_SALUDO)}<br><br>{resumen}</td></tr>
{_seccion("Lo que encontramos", hallazgos)}
{_seccion("Impacto", impacto)}
{_seccion("Acciones recomendadas", acciones)}
<tr><td style="padding:8px 32px 28px 32px;font-size:14px;line-height:1.6;color:#1F2937;{FUENTE}">Cordialmente,<br><b>{html.escape(config.CORREO_FIRMA)}</b></td></tr>
<tr><td bgcolor="#F9FAFB" style="padding:14px 32px;background-color:#F9FAFB;border-top:1px solid #E5E7EB;font-size:11px;color:#9CA3AF;{FUENTE}">{html.escape(config.CORREO_PIE)}</td></tr>
</table>
</td></tr>
</table>"""
    return compactar_html(cuerpo)


def texto_a_html(texto, importancia):
    """
    Respaldo: si Copilot devolvió el correo como texto corrido (formato viejo, campo "correo"),
    igual se manda con la plantilla para que nunca llegue un bloque de texto plano.
    """
    return armar_correo_html({"titulo": None, "resumen": texto}, importancia)


def es_html(texto):
    """True si el texto parece un cuerpo HTML (empieza por una etiqueta)."""
    return bool(re.match(r"\s*<[a-zA-Z!]", str(texto or "")))


if __name__ == "__main__":
    # Vista previa:  python -m src.plantilla_correo  -> genera vista_previa_correo.html en la raíz
    ejemplo = {
        "titulo": "VIKI: el NPS cayó **4 pp** frente a su tendencia",
        "resumen": "El NPS de VIKI bajó a **38 %** hoy, **4 puntos porcentuales** por debajo del promedio de los últimos 7 días. Es la caída más fuerte del mes y requiere revisión **hoy**.",
        "hallazgos": [
            "NPS actual **38 %** vs. promedio semanal **42 %**.",
            "La caída coincide con el inicio del fin de semana de **Black Friday**, cuando el volumen de conversaciones sube.",
            "No hay caídas similares en los registros de los jueves anteriores.",
        ],
        "impacto": "Más clientes insatisfechos con la atención de VIKI en un día de alto tráfico: riesgo de **más transferencias a asesor** y de quejas.",
        "acciones": [
            "Revisar despliegues o cambios en VIKI de las últimas 48 horas.",
            "Validar tiempos de respuesta y errores del servicio en el mismo periodo.",
            "Informar el resultado al equipo antes de las **5:00 p. m.**",
        ],
    }
    ruta = config.RAIZ / "vista_previa_correo.html"
    ruta.write_text(armar_correo_html(ejemplo, "ALTA"), encoding="utf-8")
    print(f"Vista previa en {ruta}")
