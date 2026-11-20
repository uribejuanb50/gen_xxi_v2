import src.correos as correos
import src.config as config
import src.llamada_copilot as copilot

def main():

    prompt = copilot.construir_prompt(
        config.PROMPT_COPILOT, config.CONTEXTO_PRUEBA, "ALTA"
    )

    correo, importancia = copilot.llamar_copilot(prompt)

    usuarios_objetivo = correos.leer_encargados(config.DATA_CONTACTO, "VIKI", ["PRACTICANTES"])
    filas = correos.generar_mensaje_por_importancia(usuarios_objetivo, "", correo)
    correos.crear_y_montar_correos(
        config.EXCEL_ALERTAS, "HojaAlertasCorreo", "TablaAlertas", filas
    )

    print(filas)
    
    pass

if __name__ == "__main__":
    main()