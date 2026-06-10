from ...domain.models import (
    CampoFormativo, FaseAprendizaje,
    ContenidoProgramaSintetico, ProcesoDesarrolloAprendizaje
)

CONTENIDOS_FASE_4 = [
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-LNG-F4-C01",
        descripcion="Lee y analiza textos argumentativos, identificando la postura del autor, argumentos y contraargumentos."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-LNG-F4-C02",
        descripcion="Produce textos argumentativos: ensayos breves, artículos de opinión y cartas formales."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-LNG-F4-C03",
        descripcion="Participa en mesas redondas, debates y foros argumentando con evidencias y fuentes confiables."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-LNG-F4-C04",
        descripcion="Investiga, organiza y presenta información de diversas fuentes aplicando procedimientos de investigación."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-LNG-F4-C05",
        descripcion="Analiza y produce textos literarios identificando recursos estilísticos, géneros y contextos culturales."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.LENGUAJES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-LNG-F4-C06",
        descripcion="Revisa y edita textos propios y ajenos atendiendo coherencia, cohesión y adecuación."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.SABERES_PCIENTIFICO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-SPC-F4-C01",
        descripcion="Resuelve problemas con números decimales y fracciones en contextos de medición, dinero y proporciones."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.SABERES_PCIENTIFICO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-SPC-F4-C02",
        descripcion="Identifica y aplica proporcionalidad directa en problemas de escalas, porcentajes y recetas."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.SABERES_PCIENTIFICO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-SPC-F4-C03",
        descripcion="Calcula perímetros, áreas y volúmenes de figuras regulares e irregulares en situaciones reales."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.SABERES_PCIENTIFICO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-SPC-F4-C04",
        descripcion="Resuelve problemas de combinatoria y probabilidad con eventos cotidianos."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.SABERES_PCIENTIFICO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-SPC-F4-C05",
        descripcion="Diseña y lleva a cabo experimentos para investigar fenómenos de la materia y la energía."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.SABERES_PCIENTIFICO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-SPC-F4-C06",
        descripcion="Analiza los sistemas del cuerpo humano y su relación con hábitos de salud y prevención."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.SABERES_PCIENTIFICO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-SPC-F4-C07",
        descripcion="Estudia la geografía de México: regiones, recursos naturales, actividades económicas y distribución poblacional."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.ETICA_NATURALEZA_SOCIEDADES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-ENS-F4-C01",
        descripcion="Analiza la historia de México desde las civilizaciones mesoamericanas hasta la vida independiente."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.ETICA_NATURALEZA_SOCIEDADES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-ENS-F4-C02",
        descripcion="Comprende y valora los derechos humanos, la Constitución y la organización del gobierno mexicano."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.ETICA_NATURALEZA_SOCIEDADES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-ENS-F4-C03",
        descripcion="Analiza problemáticas ambientales nacionales y globales: cambio climático, contaminación y pérdida de biodiversidad."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.ETICA_NATURALEZA_SOCIEDADES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-ENS-F4-C04",
        descripcion="Participa en acciones de participación ciudadana, gobierno escolar y democracia deliberativa."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.ETICA_NATURALEZA_SOCIEDADES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-ENS-F4-C05",
        descripcion="Valora la diversidad de México, reconoce el racismo y promueve la interculturalidad y el diálogo."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.ETICA_NATURALEZA_SOCIEDADES,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-ENS-F4-C06",
        descripcion="Estudia las migraciones en México e Iberoamérica: causas, efectos y aportaciones culturales."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.HUMANO_COMUNITARIO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-HYC-F4-C01",
        descripcion="Gestiona sus emociones y resuelve conflictos de forma asertiva en contextos sociales complejos."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.HUMANO_COMUNITARIO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-HYC-F4-C02",
        descripcion="Participa en proyectos comunitarios identificando problemáticas locales y proponiendo soluciones colectivas."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.HUMANO_COMUNITARIO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-HYC-F4-C03",
        descripcion="Reconoce y cuestiona estereotipos de género, raciales y sociales en los medios y la sociedad."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.HUMANO_COMUNITARIO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-HYC-F4-C04",
        descripcion="Practica actividades físicas y deportivas de mayor complejidad con actitud de cooperación y fair play."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.HUMANO_COMUNITARIO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-HYC-F4-C05",
        descripcion="Promueve hábitos de vida saludable y prevención de adicciones en su comunidad escolar."
    ),
    ContenidoProgramaSintetico(
        campo_formativo=CampoFormativo.HUMANO_COMUNITARIO,
        fase=FaseAprendizaje.FASE_4,
        codigo="CF-HYC-F4-C06",
        descripcion="Produce y aprecia manifestaciones artísticas originales integrando técnicas y lenguajes artísticos."
    ),
]


PDA_FASE_4 = [
    ProcesoDesarrolloAprendizaje(
        contenido_id=0,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Identifica la tesis, argumentos y contraargumentos en textos de opinión y editoriales."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=0,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Evalúa la solidez y pertinencia de los argumentos presentados por el autor."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=1,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Escribe textos argumentativos con tesis clara, argumentos jerarquizados y conclusión fundamentada."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=2,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Defiende su postura en debates usando evidencias y refutando argumentos de forma respetuosa."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=3,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Aplica procedimientos de investigación documental: búsqueda, selección y citación de fuentes."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=4,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Analiza recursos literarios como metáfora, símil, hipérbole e ironía en textos literarios."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=5,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Edita textos identificando problemas de coherencia, redundancia y ambigüedad."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=6,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Resuelve problemas que implican operaciones con decimales y fracciones en contextos reales."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=6,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Compara y ordena fracciones y decimales representándolos en recta numérica."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=7,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Resuelve problemas de proporcionalidad directa usando regla de tres y factor de proporcionalidad."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=8,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Calcula el área de figuras compuestas descomponiéndolas en figuras conocidas."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=9,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Determina la probabilidad de eventos usando diagramas de árbol y tablas."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=10,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Diseña experimentos controlados y analiza resultados para explicar fenómenos de la materia."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=11,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Explica la interrelación de los sistemas del cuerpo humano y su importancia para la salud."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=12,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Analiza la distribución de población, recursos y actividades económicas en las regiones de México."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=13,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Construye líneas de tiempo y mapas históricos que integren procesos de la historia de México."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=13,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Compara visiones históricas distintas sobre un mismo evento y argumenta su propia interpretación."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=14,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Identifica artículos de la Constitución que protegen derechos humanos y los relaciona con la vida cotidiana."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=15,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Propone estrategias colectivas para mitigar la contaminación y el cambio climático."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=16,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Diseña y lleva a cabo una campaña de participación ciudadana en su comunidad escolar."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=17,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Identifica y cuestiona actitudes discriminatorias y promueve la inclusión y el respeto."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=18,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Elabora un mapa de flujos migratorios y analiza las aportaciones culturales de migrantes."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=19,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Aplica técnicas de negociación y mediación para resolver conflictos interpersonales y grupales."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=20,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Diseña un proyecto comunitario integrando diagnóstico, acción y evaluación."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=21,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Analiza críticamente la representación de género y diversidad en medios digitales."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=22,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Participa en deportes colectivos aplicando estrategias, reglas y valores deportivos."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=23,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Diseña campañas de prevención sobre adicciones dirigidas a su grupo de edad."
    ),
    ProcesoDesarrolloAprendizaje(
        contenido_id=24,
        fase=FaseAprendizaje.FASE_4,
        descripcion="Crea una obra artística original integrando técnicas de al menos dos disciplinas artísticas."
    ),
]


def seed_nem_fase4(nem_repo):
    added_contenidos = 0
    added_pda = 0
    contenido_map = {}

    for contenido in CONTENIDOS_FASE_4:
        try:
            saved = nem_repo.add_contenido(contenido)
            contenido_map[contenido.codigo] = saved.id
            added_contenidos += 1
        except Exception:
            pass

    for pda in PDA_FASE_4:
        try:
            codigo_keys = list(contenido_map.keys())
            if pda.contenido_id < len(codigo_keys):
                real_id = contenido_map[codigo_keys[pda.contenido_id]]
            else:
                real_id = pda.contenido_id
            pda_with_id = ProcesoDesarrolloAprendizaje(
                contenido_id=real_id,
                fase=pda.fase,
                descripcion=pda.descripcion
            )
            nem_repo.add_pda(pda_with_id)
            added_pda += 1
        except Exception:
            pass

    return {"contenidos_inserted": added_contenidos, "pda_inserted": added_pda}
