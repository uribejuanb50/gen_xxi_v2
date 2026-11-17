import src.correos as correos
import src.config as config

def main():

    usuarios_objetivo = correos.leer_encargados(config.DATA_CONTACTO, "VIKI", ["PRACTICANTES", "PROFESIONALES"])
    filas = correos.generar_mensaje_por_importancia(usuarios_objetivo, "", config.MENSAJE_TEMPORAL)
    correos.extraer_y_montar_correos(
        config.EXCEL_ALERTAS, "HojaAlertasCorreo", "TablaAlertas", filas
    )

    print(filas)
    
    pass

if __name__ == "__main__":
    main()