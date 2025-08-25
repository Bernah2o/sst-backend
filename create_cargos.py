#!/usr/bin/env python3
"""
Script para crear cargos de ejemplo en la base de datos
"""

from app.database import get_db
from app.models.cargo import Cargo
from sqlalchemy.orm import Session

def create_sample_cargos():
    """Crear cargos de ejemplo"""
    db = next(get_db())
    
    cargos = [
        'Operador',
        'Supervisor', 
        'Coordinador',
        'Jefe de Área',
        'Gerente',
        'Técnico',
        'Auxiliar',
        'Analista',
        'Asistente',
        'Especialista'
    ]
    
    for cargo_name in cargos:
        existing = db.query(Cargo).filter(Cargo.nombre_cargo == cargo_name).first()
        if not existing:
            new_cargo = Cargo(
                nombre_cargo=cargo_name,
                periodicidad_emo="12 meses",
                activo=True
            )
            db.add(new_cargo)
            print(f'Cargo {cargo_name} creado')
        else:
            print(f'Cargo {cargo_name} ya existe')
    
    db.commit()
    db.close()
    print('Proceso completado')

if __name__ == '__main__':
    create_sample_cargos()