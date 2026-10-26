"""Centros académicos y licenciaturas de la UAA.

Fuente de verdad ÚNICA para registro, perfil, publicaciones y filtros.
Si la UAA abre o renombra una carrera, se edita solo este archivo.

Referencia: https://www.uaa.mx/portal/oferta-educativa/licenciaturas/
(La lista se armó desde una fuente secundaria porque el portal de la UAA no
permite lectura automática: conviene contrastarla contra la página oficial.)
"""

CENTROS_CARRERAS: dict[str, list[str]] = {
    "Centro de las Artes y la Cultura": [
        "Licenciatura en Actuación",
        "Licenciatura en Artes Cinematográficas y Audiovisuales",
        "Licenciatura en Estudios del Arte y Gestión Cultural",
        "Licenciatura en Letras Hispánicas",
        "Licenciatura en Música",
    ],
    "Centro de Ciencias Agropecuarias": [
        "Ingeniería en Agronomía",
        "Ingeniería en Alimentos",
        "Médico Veterinario Zootecnista",
    ],
    "Centro de Ciencias Básicas": [
        "Ingeniería Bioquímica",
        "Ingeniería en Computación Inteligente",
        "Ingeniería en Electrónica",
        "Ingeniería en Sistemas Computacionales",
        "Ingeniería Industrial Estadística",
        "Licenciatura en Biología",
        "Licenciatura en Biotecnología",
        "Licenciatura en Informática y Tecnologías Computacionales",
        "Licenciatura en Matemáticas Aplicadas",
        "Químico Farmacéutico Biólogo",
    ],
    "Centro de Ciencias de la Ingeniería": [
        "Ingeniería Automotriz",
        "Ingeniería Biomédica",
        "Ingeniería en Diseño Mecánico",
        "Ingeniería en Energías Renovables",
        "Ingeniería en Manufactura y Automatización Industrial",
        "Ingeniería Robótica",
    ],
    "Centro de Ciencias de la Salud": [
        "Licenciatura en Cultura Física y Deporte",
        "Licenciatura en Enfermería",
        "Licenciatura en Nutrición",
        "Licenciatura en Optometría",
        "Licenciatura en Terapia Física",
        "Médico Cirujano",
        "Médico Estomatólogo",
    ],
    "Centro de Ciencias del Diseño y de la Construcción": [
        "Arquitectura",
        "Ingeniería Civil",
        "Licenciatura en Diseño de Interiores",
        "Licenciatura en Diseño de Moda e Indumentaria y Textiles",
        "Licenciatura en Diseño Gráfico",
        "Licenciatura en Diseño Industrial",
        "Licenciatura en Urbanismo",
    ],
    "Centro de Ciencias Económicas y Administrativas": [
        "Contador Público",
        "Licenciatura en Administración de Empresas",
        "Licenciatura en Administración de la Producción y Servicios",
        "Licenciatura en Administración Financiera",
        "Licenciatura en Comercio Internacional",
        "Licenciatura en Economía",
        "Licenciatura en Gestión Turística",
        "Licenciatura en Mercadotecnia",
        "Licenciatura en Relaciones Industriales",
    ],
    "Centro de Ciencias Empresariales": [
        "Licenciatura en Administración y Gestión Fiscal de PYMES",
        "Licenciatura en Agronegocios",
        "Licenciatura en Comercio Electrónico",
        "Licenciatura en Logística Empresarial",
    ],
    "Centro de Ciencias Sociales y Humanidades": [
        "Licenciatura en Asesoría Psicopedagógica",
        "Licenciatura en Ciencias Políticas y Administración Pública",
        "Licenciatura en Comunicación Corporativa Estratégica",
        "Licenciatura en Comunicación e Información",
        "Licenciatura en Derecho",
        "Licenciatura en Docencia del Francés y Español como Lenguas Extranjeras",
        "Licenciatura en Docencia del Idioma Inglés",
        "Licenciatura en Filosofía",
        "Licenciatura en Historia",
        "Licenciatura en Psicología",
        "Licenciatura en Sociología",
        "Licenciatura en Trabajo Social",
    ],
}

# Valor "sin centro" para publicaciones que sirven a cualquier carrera.
CENTRO_GENERAL = "General"

CENTROS: list[str] = list(CENTROS_CARRERAS)
CENTROS_POST: list[str] = [CENTRO_GENERAL, *CENTROS]

# carrera -> centro (los nombres no se repiten entre centros)
CARRERA_A_CENTRO: dict[str, str] = {
    carrera: centro for centro, lista in CENTROS_CARRERAS.items() for carrera in lista
}


def centro_de(carrera: str) -> str | None:
    return CARRERA_A_CENTRO.get(carrera)
