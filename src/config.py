from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

DATA = RAIZ

BD_VIKI = DATA / "Archivos de Jhon Jairo Martinez Gonzalez - DB_VIKI"

ALERTAS = DATA / "Gerencia de Mejora continua de Procesos - data_alertas"
EXCEL_ALERTAS = ALERTAS / "Alertas_GenXXI.xlsx"


#-----------Direcciones---------------------------

DIRECCIONES_VIKI = {
    "PRACTICANTES" : {
        [
            {
                "nombre" :  "Juan Uribe",
                "correo" : "38519950@claro.com.co"
            },
            {
                "nombre" : "Alejandro",
                "correo" : "38520135@claro.com.co"
            }
        ]
    },
    "PROFESIONALES" : {
        [
            {
                "nombre" : "yulieta",
                "correo" : "45758028@claro.com.co"
            }
        ]
    }
}