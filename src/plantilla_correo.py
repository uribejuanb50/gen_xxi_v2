"""
Módulo plantilla_correo

Arma el cuerpo HTML del correo de alerta a partir del contenido que devuelve Copilot.
Copilot pone el contenido (título, resumen, hallazgos, impacto, acciones) y este módulo
pone la forma: franja de color según importancia, negrillas, secciones y espaciado.

HTML pensado para Outlook: tablas y estilos en línea (Outlook ignora CSS externo y <style>).

Uso:
    html = armar_correo_html(datos, "ALTA")
    # datos = {"titulo": ..., "resumen": ..., "hallazgos": [...], "impacto": ..., "acciones": [...]}
"""

import re
import html
import datetime

import src.config as config


def _formatear(texto):
    """Escapa el texto y convierte **negrilla** en <b>negrilla</b> y los saltos de línea en <br>."""
    seguro = html.escape(str(texto or "").strip())
    seguro = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", seguro)
    return seguro.replace("\n", "<br>")


def _lista(items, ordenada=False):
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return ""
    etiqueta = "ol" if ordenada else "ul"
    filas = "".join(
        f'<li style="margin:0 0 8px 0;">{_formatear(i)}</li>' for i in items
    )
    return f'<{etiqueta} style="margin:0;padding-left:22px;">{filas}</{etiqueta}>'


def _seccion(titulo, contenido_html):
    if not contenido_html:
        return ""
    return (
        '<tr><td style="padding:0 32px 22px 32px;">'
        f'<div style="font-size:12px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;'
        f'color:#6B7280;margin:0 0 8px 0;">{titulo}</div>'
        f'<div style="font-size:14px;line-height:1.6;color:#1F2937;">{contenido_html}</div>'
        "</td></tr>"
    )


def armar_correo_html(datos, importancia):
    """Devuelve el HTML completo del correo."""
    importancia = str(importancia).upper()
    color = config.CORREO_COLORES_IMPORTANCIA.get(importancia, "#6B7280")
    fecha = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    titulo = _formatear(datos.get("titulo") or "Alerta del sistema de monitoreo")
    resumen = _formatear(datos.get("resumen"))
    hallazgos = _lista(datos.get("hallazgos"))
    acciones = _lista(datos.get("acciones"), ordenada=True)

    impacto = ""
    if str(datos.get("impacto") or "").strip():
        impacto = (
            f'<div style="background:#F9FAFB;border-left:4px solid {color};padding:12px 16px;">'
            f"{_formatear(datos.get('impacto'))}</div>"
        )

    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F3F4F6;padding:24px 0;font-family:'Segoe UI',Arial,sans-serif;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#FFFFFF;border:1px solid #E5E7EB;">
<tr><td style="background:{color};height:6px;font-size:0;line-height:0;">&nbsp;</td></tr>
<tr><td style="padding:28px 32px 8px 32px;">
<span style="display:inline-block;background:{color};color:#FFFFFF;font-size:11px;font-weight:bold;letter-spacing:1px;padding:4px 10px;">IMPORTANCIA {html.escape(importancia)}</span>
<span style="font-size:12px;color:#6B7280;padding-left:8px;">{fecha}</span>
</td></tr>
<tr><td style="padding:8px 32px 18px 32px;font-size:22px;line-height:1.3;font-weight:bold;color:#111827;">{titulo}</td></tr>
<tr><td style="padding:0 32px 22px 32px;font-size:15px;line-height:1.6;color:#1F2937;">{config.CORREO_SALUDO}<br><br>{resumen}</td></tr>
{_seccion("Lo que encontramos", hallazgos)}
{_seccion("Impacto", impacto)}
{_seccion("Acciones recomendadas", acciones)}
<tr><td style="padding:8px 32px 28px 32px;font-size:14px;line-height:1.6;color:#1F2937;">Cordialmente,<br><b>{config.CORREO_FIRMA}</b></td></tr>
<tr><td style="padding:14px 32px;background:#F9FAFB;border-top:1px solid #E5E7EB;font-size:11px;color:#9CA3AF;">{config.CORREO_PIE}</td></tr>
</table>
</td></tr>
</table>"""


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
