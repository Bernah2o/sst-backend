"""
Servicio para la Matriz Legal SST.

Proporciona funcionalidades para:
- Importación de archivos Excel de la ARL
- Detección automática de aplicabilidad de normas
- Filtrado de normas aplicables por empresa
- Sincronización de cumplimientos
- Cálculo de estadísticas
"""

import hashlib
import json
import logging
import re
from datetime import date, datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.models.matriz_legal import (
    MatrizLegalNorma, MatrizLegalNormaHistorial,
    MatrizLegalCumplimiento, MatrizLegalCumplimientoHistorial,
    MatrizLegalImportacion,
    EstadoImportacion, EstadoNorma, EstadoCumplimiento, AmbitoAplicacion
)
from app.models.sector_economico import SectorEconomico
from app.models.empresa import Empresa

logger = logging.getLogger(__name__)


class MatrizLegalService:
    """Servicio principal para gestión de la Matriz Legal."""

    # Mapeo de columnas del Excel a campos del modelo
    # Soporta múltiples variantes de nombres de columnas (incluye formato ARL Bolívar)
    COLUMN_MAPPING = {
        # Ámbito de aplicación
        'ambito de aplicacion': 'ambito_aplicacion',
        'ambito de aplicación': 'ambito_aplicacion',
        'ambito': 'ambito_aplicacion',
        'ámbito de aplicación': 'ambito_aplicacion',
        'ámbito': 'ambito_aplicacion',
        # Sector económico
        'sector economico': 'sector_economico_texto',
        'sector económico': 'sector_economico_texto',
        # Clasificación
        'clasificacion de la norma': 'clasificacion_norma',
        'clasificación de la norma': 'clasificacion_norma',
        'clasificacion': 'clasificacion_norma',
        'clasificación': 'clasificacion_norma',
        # Tema
        'tema general': 'tema_general',
        'tema': 'tema_general',
        # Subtema
        'sub tema o riesgo especifico': 'subtema_riesgo_especifico',
        'sub tema o riesgo específico': 'subtema_riesgo_especifico',
        'subtema': 'subtema_riesgo_especifico',
        'subtema riesgo especifico': 'subtema_riesgo_especifico',
        'subtema o riesgo especifico': 'subtema_riesgo_especifico',
        'subtema o riesgo específico': 'subtema_riesgo_especifico',
        # Año
        'ano': 'anio',
        'año': 'anio',
        'anio': 'anio',
        # Tipo/Número (columna combinada del Excel ARL)
        'tipo/numero': 'tipo_numero_raw',
        'tipo/número': 'tipo_numero_raw',
        'tipo / numero': 'tipo_numero_raw',
        'tipo / número': 'tipo_numero_raw',
        'legislacion tipo/numero': 'tipo_numero_raw',
        'legislación tipo/número': 'tipo_numero_raw',
        # Tipo y Número separados
        'tipo': 'tipo_norma',
        'tipo norma': 'tipo_norma',
        'numero': 'numero_norma',
        'número': 'numero_norma',
        'numero norma': 'numero_norma',
        'número norma': 'numero_norma',
        # Fecha
        'fecha': 'fecha_expedicion',
        'legislacion fecha': 'fecha_expedicion',
        'legislación fecha': 'fecha_expedicion',
        'fecha expedicion': 'fecha_expedicion',
        'fecha expedición': 'fecha_expedicion',
        # Expedida por
        'expedida por': 'expedida_por',
        'legislacion expedida por': 'expedida_por',
        'legislación expedida por': 'expedida_por',
        # Descripción de la norma
        'descripcion de la norma': 'descripcion_norma',
        'descripción de la norma': 'descripcion_norma',
        'legislacion descripcion de la norma': 'descripcion_norma',
        'legislación descripción de la norma': 'descripcion_norma',
        'descripcion norma': 'descripcion_norma',
        'descripción norma': 'descripcion_norma',
        # Artículo
        'articulo': 'articulo',
        'artículo': 'articulo',
        'legislacion articulo': 'articulo',
        'legislación artículo': 'articulo',
        # Estado
        'estado': 'estado',
        'legislacion estado': 'estado',
        'legislación estado': 'estado',
        # Info
        'info': 'info_adicional',
        'legislacion info': 'info_adicional',
        'legislación info': 'info_adicional',
        'informacion adicional': 'info_adicional',
        'información adicional': 'info_adicional',
        # Exigencias / Descripción del artículo
        'descripcion del articulo que aplica - exigencias': 'descripcion_articulo_exigencias',
        'descripción del artículo que aplica - exigencias': 'descripcion_articulo_exigencias',
        'descripcion del articulo que aplica': 'descripcion_articulo_exigencias',
        'descripción del artículo que aplica': 'descripcion_articulo_exigencias',
        'exigencias': 'descripcion_articulo_exigencias',
        'descripcion articulo exigencias': 'descripcion_articulo_exigencias',
        'descripción artículo exigencias': 'descripcion_articulo_exigencias',
        # Variantes adicionales del formato ARL
        'descripcion del articulo  que aplica - exigencias': 'descripcion_articulo_exigencias',
        'descripción del artículo  que aplica - exigencias': 'descripcion_articulo_exigencias',
    }

    # Palabras clave para detección automática de aplicabilidad
    APPLICABILITY_KEYWORDS = {
        'aplica_trabajadores_independientes': [
            'independiente', 'contratista', 'prestador de servicio',
            'trabajador independiente', 'contrato de prestación'
        ],
        'aplica_teletrabajo': [
            'teletrabajo', 'trabajo remoto', 'trabajo en casa',
            'trabajo a distancia', 'home office'
        ],
        'aplica_trabajo_alturas': [
            'altura', 'alturas', 'trabajo en altura', 'caída',
            'andamios', 'escaleras', 'plataformas elevadas'
        ],
        'aplica_espacios_confinados': [
            'espacio confinado', 'espacios confinados',
            'atmósfera peligrosa', 'tanque', 'silo'
        ],
        'aplica_trabajo_caliente': [
            'trabajo caliente', 'soldadura', 'corte con llama',
            'esmerilado', 'oxicorte'
        ],
        'aplica_sustancias_quimicas': [
            'químico', 'quimico', 'sustancia química', 'sustancia peligrosa',
            'tóxico', 'corrosivo', 'inflamable', 'sga', 'fds'
        ],
        'aplica_radiaciones': [
            'radiación', 'radiacion', 'ionizante', 'no ionizante',
            'rayos x', 'ultravioleta', 'láser'
        ],
        'aplica_trabajo_nocturno': [
            'nocturno', 'noche', 'jornada nocturna', 'turno de noche'
        ],
        'aplica_menores_edad': [
            'menor de edad', 'menores', 'joven', 'adolescente',
            'trabajo infantil', 'menor trabajador'
        ],
        'aplica_mujeres_embarazadas': [
            'embarazada', 'embarazo', 'maternidad', 'lactancia',
            'gestante', 'licencia de maternidad'
        ],
        'aplica_conductores': [
            'conductor', 'vehículo', 'vehiculo', 'transporte',
            'conducción', 'seguridad vial', 'pesv'
        ],
        'aplica_manipulacion_alimentos': [
            'alimento', 'manipulación de alimentos', 'inocuidad',
            'bpm', 'haccp', 'manipulador'
        ],
        'aplica_maquinaria_pesada': [
            'maquinaria pesada', 'montacargas', 'grúa', 'retroexcavadora',
            'equipos móviles'
        ],
        'aplica_riesgo_electrico': [
            'eléctrico', 'electrico', 'electricidad', 'tensión',
            'alta tensión', 'baja tensión', 'retie'
        ],
        'aplica_riesgo_biologico': [
            'biológico', 'biologico', 'bioseguridad', 'microorganismo',
            'patógeno', 'infeccioso', 'sangre', 'fluidos corporales'
        ],
        'aplica_trabajo_excavaciones': [
            'excavación', 'excavacion', 'zanja', 'túnel',
            'movimiento de tierra', 'demolición'
        ],
        'aplica_trabajo_administrativo': [
            'administrativo', 'oficina', 'pantalla de visualización',
            'videoterminales', 'ergonomía', 'sedentarismo', 'postura',
            'escritorio', 'computador', 'trabajo de oficina'
        ],
    }

    def __init__(self, db: Session):
        self.db = db

    def _read_excel_with_header_detection(self, file_content: bytes) -> pd.DataFrame:
        """
        Lee el archivo Excel detectando automáticamente la fila de encabezados.
        Los archivos de la ARL suelen tener:
        - Fila 1: Encabezados principales + "LEGISLACION" como grupo
        - Fila 2: Sub-encabezados bajo LEGISLACION (TIPO/NUMERO, FECHA, etc.)
        """
        # Leer las primeras filas para analizar la estructura
        df_preview = pd.read_excel(BytesIO(file_content), header=None, nrows=15)

        # Buscar la fila que contiene los encabezados principales (AMBITO, SECTOR, etc.)
        main_header_row = None
        sub_header_row = None

        # Palabras clave para encabezados principales
        main_keywords = ['ambito', 'ámbito', 'sector', 'clasificacion', 'clasificación']
        # Palabras clave para sub-encabezados (bajo LEGISLACION)
        sub_keywords = ['tipo/numero', 'tipo/número', 'tipo', 'fecha', 'expedida', 'articulo', 'artículo']

        for idx in range(min(10, len(df_preview))):
            row_values = df_preview.iloc[idx].astype(str).str.lower().tolist()
            row_text = ' '.join(row_values)

            main_matches = sum(1 for kw in main_keywords if kw in row_text)
            sub_matches = sum(1 for kw in sub_keywords if kw in row_text)

            logger.debug(f"Fila {idx + 1}: main_matches={main_matches}, sub_matches={sub_matches}")
            logger.debug(f"  Valores: {row_values[:8]}...")

            # Si tiene encabezados principales Y tiene "legislacion" (grupo)
            if main_matches >= 2 and 'legislaci' in row_text:
                main_header_row = idx
                # La siguiente fila debería tener los sub-encabezados
                if idx + 1 < len(df_preview):
                    next_row_text = ' '.join(df_preview.iloc[idx + 1].astype(str).str.lower().tolist())
                    if any(kw in next_row_text for kw in sub_keywords):
                        sub_header_row = idx + 1
                break
            # Si solo tiene encabezados principales sin grupo
            elif main_matches >= 3 and sub_matches >= 2:
                main_header_row = idx
                break

        logger.info(f"main_header_row={main_header_row}, sub_header_row={sub_header_row}")

        # Caso 1: Encabezados en dos filas (formato ARL típico)
        if main_header_row is not None and sub_header_row is not None:
            logger.info(f"Detectado formato de encabezado de dos filas: {main_header_row + 1} y {sub_header_row + 1}")

            # Leer ambas filas de encabezado
            row1 = df_preview.iloc[main_header_row].astype(str).tolist()
            row2 = df_preview.iloc[sub_header_row].astype(str).tolist()

            # Combinar encabezados: usar row1 si tiene valor válido, sino usar row2
            combined_headers = []
            for i in range(len(row1)):
                val1 = str(row1[i]).strip() if i < len(row1) else ''
                val2 = str(row2[i]).strip() if i < len(row2) else ''

                # Si row1 tiene "nan", "LEGISLACION", o está vacío, usar row2
                if val1.lower() in ['nan', '', 'legislacion', 'legislación', 'none']:
                    combined_headers.append(val2 if val2.lower() not in ['nan', '', 'none'] else f'col_{i}')
                else:
                    combined_headers.append(val1)

            logger.info(f"Encabezados combinados: {combined_headers}")

            # Leer datos saltando las filas de encabezado
            df = pd.read_excel(BytesIO(file_content), header=None, skiprows=sub_header_row + 1)
            df.columns = combined_headers[:len(df.columns)]

        # Caso 2: Encabezados en una sola fila
        elif main_header_row is not None:
            logger.info(f"Detectado formato de encabezado de una fila: {main_header_row + 1}")
            df = pd.read_excel(BytesIO(file_content), header=main_header_row)

            # Limpiar nombres de columnas
            new_columns = []
            for col in df.columns:
                col_str = str(col)
                if 'Unnamed' in col_str or col_str.lower() == 'nan':
                    new_columns.append('')
                else:
                    new_columns.append(col_str.strip())
            df.columns = new_columns

        # Caso 3: No se detectó estructura clara
        else:
            logger.warning("No se detectó estructura de encabezado clara, usando fila 1")
            df = pd.read_excel(BytesIO(file_content))

        # Eliminar filas completamente vacías
        df = df.dropna(how='all')

        # Eliminar columnas sin nombre (vacías)
        df = df.loc[:, (df.columns != '') & (df.columns.astype(str).str.lower() != 'nan')]

        logger.info(f"Columnas finales: {list(df.columns)}")
        logger.info(f"Total filas de datos: {len(df)}")

        return df

    def preview_import(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Previsualiza una importación sin guardar cambios.
        Retorna estadísticas y errores de validación.
        """
        try:
            df = self._read_excel_with_header_detection(file_content)
            df = self._normalize_columns(df)

            errors = []
            normas_nuevas = 0
            normas_existentes = 0

            for idx, row in df.iterrows():
                row_num = idx + 2  # +2 por header y 0-index
                validation_errors = self._validate_row(row, row_num)
                if validation_errors:
                    errors.extend(validation_errors)
                    continue

                # Verificar si existe
                existing = self._find_existing_norma(row)
                if existing:
                    normas_existentes += 1
                else:
                    normas_nuevas += 1

            # Muestra de datos (primeras 5 filas válidas)
            muestra = []
            valid_rows = 0
            for idx, row in df.iterrows():
                if valid_rows >= 5:
                    break
                row_errors = self._validate_row(row, idx + 2)
                if not row_errors:
                    muestra.append(row.to_dict())
                    valid_rows += 1

            # Log de columnas para diagnóstico
            columnas_originales = list(df.columns)
            columnas_mapeadas = {}
            for col in columnas_originales:
                col_lower = str(col).lower().strip()
                if col_lower in self.COLUMN_MAPPING:
                    columnas_mapeadas[col] = self.COLUMN_MAPPING[col_lower]
                else:
                    columnas_mapeadas[col] = None

            return {
                'total_filas': len(df),
                'normas_nuevas_preview': normas_nuevas,
                'normas_existentes_preview': normas_existentes,
                'errores_validacion': errors[:50],  # Limitar errores mostrados
                'columnas_detectadas': columnas_originales,
                'columnas_mapeadas': columnas_mapeadas,
                'muestra_datos': muestra,
            }

        except Exception as e:
            logger.error(f"Error en preview de importación: {e}")
            return {
                'total_filas': 0,
                'normas_nuevas_preview': 0,
                'normas_existentes_preview': 0,
                'errores_validacion': [{'fila': 0, 'error': str(e)}],
                'columnas_detectadas': [],
                'muestra_datos': [],
            }

    def import_excel(
        self,
        file_content: bytes,
        filename: str,
        user_id: int,
        sobrescribir: bool = False
    ) -> MatrizLegalImportacion:
        """
        Importa el archivo Excel de la ARL.
        """
        # Crear registro de importación
        importacion = MatrizLegalImportacion(
            nombre_archivo=filename,
            creado_por=user_id,
            estado=EstadoImportacion.EN_PROCESO.value
        )
        self.db.add(importacion)
        self.db.flush()

        try:
            df = self._read_excel_with_header_detection(file_content)
            df = self._normalize_columns(df)

            importacion.total_filas = len(df)
            errores_log = []

            for idx, row in df.iterrows():
                row_num = idx + 2
                try:
                    result = self._process_row(row, importacion.id, user_id, sobrescribir)
                    if result == 'new':
                        importacion.normas_nuevas += 1
                    elif result == 'updated':
                        importacion.normas_actualizadas += 1
                    elif result == 'unchanged':
                        importacion.normas_sin_cambios += 1
                except Exception as e:
                    importacion.errores += 1
                    errores_log.append(f"Fila {row_num}: {str(e)}")
                    logger.warning(f"Error procesando fila {row_num}: {e}")

            importacion.log_errores = "\n".join(errores_log) if errores_log else None

            if importacion.errores == 0:
                importacion.estado = EstadoImportacion.COMPLETADA.value
            elif importacion.normas_nuevas > 0 or importacion.normas_actualizadas > 0:
                importacion.estado = EstadoImportacion.PARCIAL.value
            else:
                importacion.estado = EstadoImportacion.FALLIDA.value

            self.db.commit()

        except Exception as e:
            importacion.estado = EstadoImportacion.FALLIDA.value
            importacion.log_errores = str(e)
            self.db.commit()
            logger.error(f"Error en importación: {e}")
            raise

        return importacion

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza nombres de columnas del DataFrame."""
        # Convertir a minúsculas y limpiar caracteres especiales
        cleaned_columns = []
        for col in df.columns:
            col_clean = str(col).lower().strip()
            # Remover saltos de línea y retornos de carro
            col_clean = col_clean.replace('\n', ' ').replace('\r', ' ')
            # Reemplazar múltiples espacios por uno solo
            col_clean = re.sub(r'\s+', ' ', col_clean)
            # Remover caracteres no imprimibles
            col_clean = ''.join(c for c in col_clean if c.isprintable() or c == ' ')
            col_clean = col_clean.strip()
            cleaned_columns.append(col_clean)

        df.columns = cleaned_columns
        logger.info(f"Columnas después de limpieza: {list(df.columns)}")

        # Aplicar mapeo
        rename_map = {}
        for col in df.columns:
            col_clean = col.lower().strip()
            if col_clean in self.COLUMN_MAPPING:
                rename_map[col] = self.COLUMN_MAPPING[col_clean]
                logger.info(f"Mapeando '{col}' -> '{self.COLUMN_MAPPING[col_clean]}'")
            else:
                logger.warning(f"Columna sin mapeo: '{col}'")

        if rename_map:
            df = df.rename(columns=rename_map)
            logger.info(f"Columnas después de mapeo: {list(df.columns)}")

        return df

    def _validate_row(self, row: pd.Series, row_num: int) -> List[Dict]:
        """Valida una fila del Excel."""
        errors = []

        # Campos requeridos
        required_fields = ['clasificacion_norma', 'tema_general', 'anio']

        # Verificar si tenemos tipo_numero_raw o tipo_norma/numero_norma separados
        has_tipo_numero = 'tipo_numero_raw' in row and pd.notna(row.get('tipo_numero_raw'))
        has_tipo_norma = 'tipo_norma' in row and pd.notna(row.get('tipo_norma'))
        has_numero_norma = 'numero_norma' in row and pd.notna(row.get('numero_norma'))

        if not has_tipo_numero and not (has_tipo_norma and has_numero_norma):
            errors.append({
                'fila': row_num,
                'error': 'Falta tipo/número de norma'
            })

        for field in required_fields:
            if field not in row or pd.isna(row.get(field)) or str(row.get(field)).strip() == '':
                errors.append({
                    'fila': row_num,
                    'error': f'Campo requerido vacío: {field}'
                })

        return errors

    def _find_existing_norma(self, row: pd.Series) -> Optional[MatrizLegalNorma]:
        """Busca si ya existe una norma con el mismo tipo/número/artículo."""
        tipo_norma, numero_norma = self._extract_tipo_numero(row)
        articulo = self._clean_string(row.get('articulo'))

        if not tipo_norma or not numero_norma:
            logger.debug(f"_find_existing_norma: tipo_norma o numero_norma vacío")
            return None

        logger.debug(f"Buscando norma existente: tipo='{tipo_norma}', numero='{numero_norma}', articulo='{articulo}'")

        # Usar comparación case-insensitive con func.lower para mayor robustez
        query = self.db.query(MatrizLegalNorma).filter(
            func.lower(MatrizLegalNorma.tipo_norma) == func.lower(tipo_norma),
            func.lower(MatrizLegalNorma.numero_norma) == func.lower(numero_norma),
        )

        if articulo:
            # Comparar artículo con case-insensitive
            query = query.filter(func.lower(MatrizLegalNorma.articulo) == func.lower(articulo))
        else:
            query = query.filter(
                or_(
                    MatrizLegalNorma.articulo.is_(None),
                    MatrizLegalNorma.articulo == ''
                )
            )

        existing = query.first()
        if existing:
            logger.debug(f"  -> Encontrada norma existente ID={existing.id}")
        else:
            logger.debug(f"  -> No se encontró norma existente")
        return existing

    def _extract_tipo_numero(self, row: pd.Series) -> Tuple[Optional[str], Optional[str]]:
        """Extrae tipo y número de norma de la fila."""
        # Primero intentar con columnas separadas
        if 'tipo_norma' in row and pd.notna(row.get('tipo_norma')):
            tipo = self._clean_string(row.get('tipo_norma'))
            numero = self._clean_string(row.get('numero_norma', ''))
            return tipo, numero

        # Luego intentar con columna combinada
        if 'tipo_numero_raw' in row and pd.notna(row.get('tipo_numero_raw')):
            raw = str(row.get('tipo_numero_raw')).strip()
            # Patrones comunes: "Resolución 0312", "Ley 1562", "Decreto 1072"
            match = re.match(r'^(\w+)\s+(.+)$', raw)
            if match:
                return match.group(1), match.group(2)
            return raw, ''

        return None, None

    def _clean_string(self, value: Any) -> Optional[str]:
        """Limpia un valor string."""
        if pd.isna(value) or value is None:
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned else None

    def _process_row(
        self,
        row: pd.Series,
        importacion_id: int,
        user_id: int,
        sobrescribir: bool
    ) -> str:
        """
        Procesa una fila del Excel.
        Retorna: 'new', 'updated', 'unchanged'
        """
        # Extraer datos
        data = self._extract_norma_data(row)
        content_hash = self._compute_hash(data)

        logger.debug(f"Procesando: tipo='{data.get('tipo_norma')}', numero='{data.get('numero_norma')}', articulo='{data.get('articulo')}'")

        # Buscar existente
        existing = self._find_existing_norma(row)

        if existing:
            if existing.hash_contenido == content_hash:
                return 'unchanged'

            if sobrescribir:
                # Guardar versión anterior en historial
                self._save_to_history(existing, user_id)
                # Actualizar
                for key, value in data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.hash_contenido = content_hash
                existing.version += 1
                existing.importacion_id = importacion_id
                existing.updated_at = datetime.utcnow()
                return 'updated'
            else:
                return 'unchanged'
        else:
            # Obtener o crear sector económico
            sector_texto = data.pop('sector_economico_texto', None)
            sector = self._get_or_create_sector(sector_texto)

            # Detectar aplicabilidad automática
            applicability = self._detect_applicability(data)
            data.update(applicability)

            # Crear nueva norma
            norma = MatrizLegalNorma(
                **data,
                sector_economico_id=sector.id if sector else None,
                sector_economico_texto=sector_texto,
                hash_contenido=content_hash,
                importacion_id=importacion_id
            )

            # Usar savepoint para manejar posibles duplicados sin afectar toda la transacción
            try:
                savepoint = self.db.begin_nested()
                self.db.add(norma)
                # Flush para que el registro sea visible en queries posteriores dentro del mismo batch
                self.db.flush()
                savepoint.commit()
                return 'new'
            except Exception as e:
                # Si hay error de duplicado, rollback del savepoint y tratar como existente
                savepoint.rollback()
                logger.warning(f"Error al insertar norma (posible duplicado): tipo='{data.get('tipo_norma')}', numero='{data.get('numero_norma')}', articulo='{data.get('articulo')}' - {e}")
                # La norma probablemente ya existe, tratarla como sin cambios
                return 'unchanged'

    def _extract_norma_data(self, row: pd.Series) -> Dict[str, Any]:
        """Extrae los datos de una norma de la fila."""
        tipo_norma, numero_norma = self._extract_tipo_numero(row)

        # Parsear fecha
        fecha_expedicion = None
        if 'fecha_expedicion' in row and pd.notna(row.get('fecha_expedicion')):
            try:
                fecha_raw = row.get('fecha_expedicion')
                if isinstance(fecha_raw, datetime):
                    fecha_expedicion = fecha_raw.date()
                elif isinstance(fecha_raw, date):
                    fecha_expedicion = fecha_raw
                else:
                    # Intentar parsear string
                    fecha_str = str(fecha_raw).strip()
                    for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d de %B de %Y']:
                        try:
                            fecha_expedicion = datetime.strptime(fecha_str, fmt).date()
                            break
                        except ValueError:
                            continue
            except Exception:
                pass

        # Parsear año
        anio = None
        if 'anio' in row and pd.notna(row.get('anio')):
            try:
                anio = int(float(row.get('anio')))
            except (ValueError, TypeError):
                anio = datetime.now().year

        # Mapear ámbito
        ambito = AmbitoAplicacion.NACIONAL.value
        if 'ambito_aplicacion' in row and pd.notna(row.get('ambito_aplicacion')):
            ambito_text = str(row.get('ambito_aplicacion')).lower().strip()
            if 'departamental' in ambito_text:
                ambito = AmbitoAplicacion.DEPARTAMENTAL.value
            elif 'municipal' in ambito_text:
                ambito = AmbitoAplicacion.MUNICIPAL.value
            elif 'internacional' in ambito_text:
                ambito = AmbitoAplicacion.INTERNACIONAL.value

        # Mapear estado
        estado = EstadoNorma.VIGENTE.value
        if 'estado' in row and pd.notna(row.get('estado')):
            estado_text = str(row.get('estado')).lower().strip()
            if 'derogad' in estado_text:
                estado = EstadoNorma.DEROGADA.value
            elif 'modificad' in estado_text:
                estado = EstadoNorma.MODIFICADA.value

        return {
            'ambito_aplicacion': ambito,
            'sector_economico_texto': self._clean_string(row.get('sector_economico_texto')),
            'clasificacion_norma': self._clean_string(row.get('clasificacion_norma')) or 'Sin clasificar',
            'tema_general': self._clean_string(row.get('tema_general')) or 'General',
            'subtema_riesgo_especifico': self._clean_string(row.get('subtema_riesgo_especifico')),
            'anio': anio or datetime.now().year,
            'tipo_norma': tipo_norma or 'Norma',
            'numero_norma': numero_norma or 'S/N',
            'fecha_expedicion': fecha_expedicion,
            'expedida_por': self._clean_string(row.get('expedida_por')),
            'descripcion_norma': self._clean_string(row.get('descripcion_norma')),
            'articulo': self._clean_string(row.get('articulo')),
            'estado': estado,
            'info_adicional': self._clean_string(row.get('info_adicional')),
            'descripcion_articulo_exigencias': self._clean_string(row.get('descripcion_articulo_exigencias')),
        }

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Calcula hash SHA256 del contenido para detectar cambios."""
        # Serializar datos relevantes para comparación
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    def _save_to_history(self, norma: MatrizLegalNorma, user_id: int) -> None:
        """Guarda la versión actual de una norma en el historial."""
        data = {
            'ambito_aplicacion': norma.ambito_aplicacion,
            'sector_economico_texto': norma.sector_economico_texto,
            'clasificacion_norma': norma.clasificacion_norma,
            'tema_general': norma.tema_general,
            'subtema_riesgo_especifico': norma.subtema_riesgo_especifico,
            'anio': norma.anio,
            'tipo_norma': norma.tipo_norma,
            'numero_norma': norma.numero_norma,
            'fecha_expedicion': norma.fecha_expedicion.isoformat() if norma.fecha_expedicion else None,
            'expedida_por': norma.expedida_por,
            'descripcion_norma': norma.descripcion_norma,
            'articulo': norma.articulo,
            'estado': norma.estado,
            'descripcion_articulo_exigencias': norma.descripcion_articulo_exigencias,
        }

        historial = MatrizLegalNormaHistorial(
            norma_id=norma.id,
            version=norma.version,
            datos_json=json.dumps(data, default=str),
            motivo_cambio='Actualización por importación',
            creado_por=user_id
        )
        self.db.add(historial)

    def _get_or_create_sector(self, sector_texto: Optional[str]) -> Optional[SectorEconomico]:
        """Obtiene o crea un sector económico."""
        if not sector_texto:
            return None

        sector_texto_clean = sector_texto.strip().upper()

        # Buscar sector existente
        sector = self.db.query(SectorEconomico).filter(
            func.upper(SectorEconomico.nombre) == sector_texto_clean
        ).first()

        if not sector:
            # Verificar si es "TODOS LOS SECTORES"
            es_todos = 'TODOS' in sector_texto_clean and 'SECTOR' in sector_texto_clean

            sector = SectorEconomico(
                nombre=sector_texto.strip(),
                es_todos_los_sectores=es_todos,
                activo=True
            )
            self.db.add(sector)
            self.db.flush()

        return sector

    def _detect_applicability(self, data: Dict[str, Any]) -> Dict[str, bool]:
        """
        Detecta automáticamente las características de aplicabilidad
        basándose en el contenido del tema, subtema y descripción.
        """
        # Construir texto para búsqueda
        text_parts = [
            data.get('tema_general', ''),
            data.get('subtema_riesgo_especifico', ''),
            data.get('descripcion_norma', ''),
            data.get('descripcion_articulo_exigencias', ''),
        ]
        text = ' '.join(filter(None, text_parts)).lower()

        result = {'aplica_general': True}  # Por defecto aplica a todos

        for field, keywords in self.APPLICABILITY_KEYWORDS.items():
            matches = any(keyword.lower() in text for keyword in keywords)
            result[field] = matches
            if matches:
                result['aplica_general'] = False  # Si tiene característica específica, no es general

        return result

    def get_normas_aplicables_empresa(
        self,
        empresa: Empresa,
        filtros: Optional[Dict] = None
    ) -> List[MatrizLegalNorma]:
        """
        Obtiene las normas aplicables a una empresa basándose en:
        1. Sector económico (si es específico) o TODOS LOS SECTORES
        2. Características de la empresa (teletrabajo, alturas, etc.)
        """
        query = self.db.query(MatrizLegalNorma).filter(
            MatrizLegalNorma.activo == True,
            MatrizLegalNorma.estado == EstadoNorma.VIGENTE.value
        )

        # Obtener sector "TODOS LOS SECTORES"
        sector_todos = self.db.query(SectorEconomico).filter(
            SectorEconomico.es_todos_los_sectores == True
        ).first()

        # Condiciones de sector
        sector_conditions = [MatrizLegalNorma.aplica_general == True]

        if sector_todos:
            sector_conditions.append(
                MatrizLegalNorma.sector_economico_id == sector_todos.id
            )

        if empresa.sector_economico_id:
            sector_conditions.append(
                MatrizLegalNorma.sector_economico_id == empresa.sector_economico_id
            )

        query = query.filter(or_(*sector_conditions))

        # Filtrar por características de la empresa
        # Solo incluir normas específicas si la empresa tiene esa característica
        characteristic_filters = []

        if not empresa.tiene_trabajadores_independientes:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_trabajadores_independientes == False
            )
        if not empresa.tiene_teletrabajo:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_teletrabajo == False
            )
        if not empresa.tiene_trabajo_alturas:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_trabajo_alturas == False
            )
        if not empresa.tiene_trabajo_espacios_confinados:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_espacios_confinados == False
            )
        if not empresa.tiene_trabajo_caliente:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_trabajo_caliente == False
            )
        if not empresa.tiene_sustancias_quimicas:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_sustancias_quimicas == False
            )
        if not empresa.tiene_radiaciones:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_radiaciones == False
            )
        if not empresa.tiene_trabajo_nocturno:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_trabajo_nocturno == False
            )
        if not empresa.tiene_menores_edad:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_menores_edad == False
            )
        if not empresa.tiene_mujeres_embarazadas:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_mujeres_embarazadas == False
            )
        if not empresa.tiene_conductores:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_conductores == False
            )
        if not empresa.tiene_manipulacion_alimentos:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_manipulacion_alimentos == False
            )
        if not empresa.tiene_maquinaria_pesada:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_maquinaria_pesada == False
            )
        if not empresa.tiene_riesgo_electrico:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_riesgo_electrico == False
            )
        if not empresa.tiene_riesgo_biologico:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_riesgo_biologico == False
            )
        if not empresa.tiene_trabajo_excavaciones:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_trabajo_excavaciones == False
            )
        if not empresa.tiene_trabajo_administrativo:
            characteristic_filters.append(
                MatrizLegalNorma.aplica_trabajo_administrativo == False
            )

        # Aplicar filtros de características
        # Las normas generales siempre aplican, las específicas solo si la empresa tiene la característica
        if characteristic_filters:
            query = query.filter(
                or_(
                    MatrizLegalNorma.aplica_general == True,
                    and_(*characteristic_filters)
                )
            )

        # Aplicar filtros adicionales
        if filtros:
            if filtros.get('clasificacion'):
                query = query.filter(
                    MatrizLegalNorma.clasificacion_norma == filtros['clasificacion']
                )
            if filtros.get('tema_general'):
                query = query.filter(
                    MatrizLegalNorma.tema_general == filtros['tema_general']
                )
            if filtros.get('anio'):
                query = query.filter(MatrizLegalNorma.anio == filtros['anio'])
            if filtros.get('q'):
                search = f"%{filtros['q']}%"
                query = query.filter(
                    or_(
                        MatrizLegalNorma.descripcion_norma.ilike(search),
                        MatrizLegalNorma.tipo_norma.ilike(search),
                        MatrizLegalNorma.numero_norma.ilike(search),
                        MatrizLegalNorma.tema_general.ilike(search),
                    )
                )

        return query.order_by(MatrizLegalNorma.anio.desc(), MatrizLegalNorma.id).all()

    def sincronizar_cumplimientos_empresa(self, empresa_id: int, user_id: int) -> Dict[str, int]:
        """
        Sincroniza los cumplimientos de una empresa:
        - Crea registros pendientes para normas nuevas aplicables
        - Marca aplica_empresa=False para normas que ya no aplican (característica removida)
        - Reactiva aplica_empresa=True para normas que vuelven a aplicar
        - No elimina registros existentes (pueden tener historial)
        """
        empresa = self.db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not empresa:
            raise ValueError("Empresa no encontrada")

        normas_aplicables = self.get_normas_aplicables_empresa(empresa)
        normas_aplicables_ids = {n.id for n in normas_aplicables}

        # Cumplimientos existentes
        cumplimientos_existentes = self.db.query(MatrizLegalCumplimiento).filter(
            MatrizLegalCumplimiento.empresa_id == empresa_id
        ).all()

        cumplimientos_por_norma = {c.norma_id: c for c in cumplimientos_existentes}

        # Crear nuevos cumplimientos para normas que ahora aplican y no tienen registro
        nuevos = 0
        for norma_id in normas_aplicables_ids - set(cumplimientos_por_norma.keys()):
            cumplimiento = MatrizLegalCumplimiento(
                empresa_id=empresa_id,
                norma_id=norma_id,
                estado=EstadoCumplimiento.PENDIENTE.value,
                aplica_empresa=True
            )
            self.db.add(cumplimiento)
            nuevos += 1

        # Actualizar aplica_empresa en registros existentes según las características actuales
        reactivados = 0
        desactivados = 0
        for norma_id, cumplimiento in cumplimientos_por_norma.items():
            if norma_id in normas_aplicables_ids:
                if not cumplimiento.aplica_empresa:
                    cumplimiento.aplica_empresa = True
                    reactivados += 1
            else:
                if cumplimiento.aplica_empresa:
                    cumplimiento.aplica_empresa = False
                    desactivados += 1

        self.db.commit()

        return {
            'total_normas_aplicables': len(normas_aplicables_ids),
            'cumplimientos_existentes': len(cumplimientos_existentes),
            'nuevos_creados': nuevos,
            'reactivados': reactivados,
            'desactivados': desactivados,
        }

    def get_estadisticas_empresa(self, empresa_id: int) -> Dict[str, Any]:
        """Calcula estadísticas de cumplimiento para una empresa."""
        empresa = self.db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not empresa:
            raise ValueError("Empresa no encontrada")

        # Contar por estado
        stats = self.db.query(
            MatrizLegalCumplimiento.estado,
            func.count(MatrizLegalCumplimiento.id)
        ).filter(
            MatrizLegalCumplimiento.empresa_id == empresa_id,
            MatrizLegalCumplimiento.aplica_empresa == True
        ).group_by(MatrizLegalCumplimiento.estado).all()

        por_estado = {
            'cumple': 0,
            'no_cumple': 0,
            'pendiente': 0,
            'no_aplica': 0,
            'en_proceso': 0,
        }

        for estado, count in stats:
            if estado:
                # estado es un string (no enum) porque se almacena como String en la DB
                estado_key = estado.value if hasattr(estado, 'value') else estado
                if estado_key in por_estado:
                    por_estado[estado_key] = count

        total_aplicables = sum(por_estado.values()) - por_estado.get('no_aplica', 0)
        total_cumple = por_estado.get('cumple', 0)

        porcentaje = (total_cumple / total_aplicables * 100) if total_aplicables > 0 else 0

        # Contar normas con plan de acción
        con_plan = self.db.query(func.count(MatrizLegalCumplimiento.id)).filter(
            MatrizLegalCumplimiento.empresa_id == empresa_id,
            MatrizLegalCumplimiento.plan_accion.isnot(None),
            MatrizLegalCumplimiento.plan_accion != ''
        ).scalar() or 0

        # Contar normas vencidas
        vencidas = self.db.query(func.count(MatrizLegalCumplimiento.id)).filter(
            MatrizLegalCumplimiento.empresa_id == empresa_id,
            MatrizLegalCumplimiento.estado.in_([EstadoCumplimiento.NO_CUMPLE.value, EstadoCumplimiento.EN_PROCESO.value]),
            MatrizLegalCumplimiento.fecha_compromiso < date.today()
        ).scalar() or 0

        return {
            'empresa_id': empresa_id,
            'empresa_nombre': empresa.nombre,
            'total_normas_aplicables': total_aplicables,
            'por_estado': por_estado,
            'porcentaje_cumplimiento': round(porcentaje, 2),
            'normas_con_plan_accion': con_plan,
            'normas_vencidas': vencidas,
        }

    def registrar_cambio_cumplimiento(
        self,
        cumplimiento: MatrizLegalCumplimiento,
        estado_anterior: Optional[str],
        user_id: int,
        observaciones: Optional[str] = None
    ) -> None:
        """Registra un cambio en el historial de cumplimiento."""
        historial = MatrizLegalCumplimientoHistorial(
            cumplimiento_id=cumplimiento.id,
            estado_anterior=estado_anterior,
            estado_nuevo=cumplimiento.estado,
            observaciones=observaciones,
            evidencia_anterior=None,
            evidencia_nueva=cumplimiento.evidencia_cumplimiento,
            plan_accion_anterior=None,
            plan_accion_nuevo=cumplimiento.plan_accion,
            creado_por=user_id
        )
        self.db.add(historial)

    def bulk_update_con_campos(
        self,
        empresa_id: int,
        payload: Any,
        user_id: int
    ) -> Dict[str, int]:
        """
        Actualiza múltiples cumplimientos seleccionados por ID,
        aplicando estado + campos opcionales. Registra historial por cada uno.
        """
        updated = 0
        skipped = 0
        for cumplimiento_id in payload.cumplimiento_ids:
            cumplimiento = self.db.query(MatrizLegalCumplimiento).filter(
                MatrizLegalCumplimiento.id == cumplimiento_id,
                MatrizLegalCumplimiento.empresa_id == empresa_id
            ).first()

            if not cumplimiento:
                skipped += 1
                continue

            estado_anterior = cumplimiento.estado
            cumplimiento.estado = payload.estado.value

            if payload.evidencia_cumplimiento is not None:
                cumplimiento.evidencia_cumplimiento = payload.evidencia_cumplimiento
            if payload.plan_accion is not None:
                cumplimiento.plan_accion = payload.plan_accion
            if payload.responsable is not None:
                cumplimiento.responsable = payload.responsable
            if payload.fecha_compromiso is not None:
                cumplimiento.fecha_compromiso = payload.fecha_compromiso
            if payload.observaciones is not None:
                cumplimiento.observaciones = payload.observaciones
            if payload.aplica_empresa is not None:
                cumplimiento.aplica_empresa = payload.aplica_empresa
            if payload.justificacion_no_aplica is not None:
                cumplimiento.justificacion_no_aplica = payload.justificacion_no_aplica

            cumplimiento.fecha_ultima_evaluacion = datetime.utcnow()
            cumplimiento.evaluado_por = user_id

            self.registrar_cambio_cumplimiento(
                cumplimiento,
                estado_anterior,
                user_id,
                payload.observaciones or f"Actualización masiva → {payload.estado.value}"
            )
            updated += 1

        self.db.commit()
        return {"updated": updated, "skipped": skipped, "total": len(payload.cumplimiento_ids)}

    def bulk_update_por_filtros(
        self,
        empresa_id: int,
        payload: Any,
        user_id: int
    ) -> Dict[str, int]:
        """
        Aplica una actualización masiva a TODOS los cumplimientos que coincidan
        con los filtros dados (no solo la página actual). Maneja también las
        normas sin registro de cumplimiento ("ghost rows").
        """
        empresa = self.db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not empresa:
            raise ValueError("Empresa no encontrada")

        normas_aplicables_ids: List[int] = []
        if payload.solo_aplicables:
            normas_aplicables = self.get_normas_aplicables_empresa(empresa)
            normas_aplicables_ids = [n.id for n in normas_aplicables]

        # --- Primera pasada: actualizar cumplimientos existentes ---
        query = self.db.query(MatrizLegalCumplimiento).join(
            MatrizLegalNorma,
            MatrizLegalCumplimiento.norma_id == MatrizLegalNorma.id
        ).filter(
            MatrizLegalCumplimiento.empresa_id == empresa_id,
            MatrizLegalNorma.activo == True,
            MatrizLegalNorma.estado == EstadoNorma.VIGENTE.value
        )

        if payload.solo_aplicables and normas_aplicables_ids:
            query = query.filter(MatrizLegalCumplimiento.norma_id.in_(normas_aplicables_ids))

        if payload.estado_cumplimiento:
            query = query.filter(
                MatrizLegalCumplimiento.estado == payload.estado_cumplimiento
            )
        if payload.clasificacion:
            query = query.filter(
                MatrizLegalNorma.clasificacion_norma == payload.clasificacion
            )
        if payload.tema_general:
            query = query.filter(
                MatrizLegalNorma.tema_general == payload.tema_general
            )
        if payload.q:
            search = f"%{payload.q}%"
            query = query.filter(
                or_(
                    MatrizLegalNorma.descripcion_norma.ilike(search),
                    MatrizLegalNorma.tipo_norma.ilike(search),
                    MatrizLegalNorma.numero_norma.ilike(search),
                )
            )

        cumplimientos = query.all()
        updated = 0
        for cumplimiento in cumplimientos:
            estado_anterior = cumplimiento.estado
            cumplimiento.estado = payload.estado.value
            if payload.evidencia_cumplimiento is not None:
                cumplimiento.evidencia_cumplimiento = payload.evidencia_cumplimiento
            if payload.plan_accion is not None:
                cumplimiento.plan_accion = payload.plan_accion
            if payload.responsable is not None:
                cumplimiento.responsable = payload.responsable
            if payload.fecha_compromiso is not None:
                cumplimiento.fecha_compromiso = payload.fecha_compromiso
            if payload.observaciones is not None:
                cumplimiento.observaciones = payload.observaciones
            if payload.aplica_empresa is not None:
                cumplimiento.aplica_empresa = payload.aplica_empresa
            if payload.justificacion_no_aplica is not None:
                cumplimiento.justificacion_no_aplica = payload.justificacion_no_aplica
            cumplimiento.fecha_ultima_evaluacion = datetime.utcnow()
            cumplimiento.evaluado_por = user_id
            self.registrar_cambio_cumplimiento(
                cumplimiento,
                estado_anterior,
                user_id,
                payload.observaciones or f"Aplicar a todos los filtrados → {payload.estado.value}"
            )
            updated += 1

        # --- Segunda pasada: crear registros para ghost rows (normas sin cumplimiento) ---
        created = 0
        if payload.solo_aplicables and normas_aplicables_ids:
            # Solo aplica si no hay filtro de estado (ghost rows son implícitamente "pendiente")
            if not payload.estado_cumplimiento or payload.estado_cumplimiento == EstadoCumplimiento.PENDIENTE.value:
                ghost_query = self.db.query(MatrizLegalNorma).outerjoin(
                    MatrizLegalCumplimiento,
                    and_(
                        MatrizLegalCumplimiento.norma_id == MatrizLegalNorma.id,
                        MatrizLegalCumplimiento.empresa_id == empresa_id
                    )
                ).filter(
                    MatrizLegalNorma.id.in_(normas_aplicables_ids),
                    MatrizLegalNorma.activo == True,
                    MatrizLegalCumplimiento.id.is_(None)
                )
                if payload.clasificacion:
                    ghost_query = ghost_query.filter(
                        MatrizLegalNorma.clasificacion_norma == payload.clasificacion
                    )
                if payload.tema_general:
                    ghost_query = ghost_query.filter(
                        MatrizLegalNorma.tema_general == payload.tema_general
                    )
                if payload.q:
                    search = f"%{payload.q}%"
                    ghost_query = ghost_query.filter(
                        or_(
                            MatrizLegalNorma.descripcion_norma.ilike(search),
                            MatrizLegalNorma.tipo_norma.ilike(search),
                            MatrizLegalNorma.numero_norma.ilike(search),
                        )
                    )
                for norma in ghost_query.all():
                    nuevo = MatrizLegalCumplimiento(
                        empresa_id=empresa_id,
                        norma_id=norma.id,
                        estado=payload.estado.value,
                        evidencia_cumplimiento=payload.evidencia_cumplimiento,
                        plan_accion=payload.plan_accion,
                        responsable=payload.responsable,
                        fecha_compromiso=payload.fecha_compromiso,
                        observaciones=payload.observaciones,
                        aplica_empresa=payload.aplica_empresa if payload.aplica_empresa is not None else True,
                        justificacion_no_aplica=payload.justificacion_no_aplica,
                        fecha_ultima_evaluacion=datetime.utcnow(),
                        evaluado_por=user_id,
                    )
                    self.db.add(nuevo)
                    self.db.flush()
                    self.registrar_cambio_cumplimiento(
                        nuevo,
                        None,
                        user_id,
                        payload.observaciones or f"Creado via aplicar a todos los filtrados → {payload.estado.value}"
                    )
                    created += 1

        self.db.commit()
        return {"updated": updated, "created": created, "total": updated + created}
