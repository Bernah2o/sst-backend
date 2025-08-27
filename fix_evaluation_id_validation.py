#!/usr/bin/env python3
"""
Script para diagnosticar y corregir el problema de validación de evaluation_id
"""

import requests
import json
from datetime import datetime

# Configuración
BASE_URL = "http://localhost:8000/api/v1"
TEST_USER_EMAIL = "admin@sst.com"
TEST_PASSWORD = "Admin123!"

def get_auth_token():
    """Obtener token de autenticación"""
    login_data = {
        "email": TEST_USER_EMAIL,
        "password": TEST_PASSWORD
    }
    
    headers = {"Content-Type": "application/json"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data, headers=headers)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Error en login: {response.status_code} - {response.text}")
        return None

def test_evaluation_endpoints_with_fixes():
    """Probar endpoints con diferentes tipos de parámetros"""
    print(f"Iniciando pruebas de corrección - {datetime.now()}")
    
    token = get_auth_token()
    if not token:
        print("No se pudo obtener el token de autenticación")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Verificar que los endpoints funcionen con enteros
    print("\n1. Probando /evaluations/admin/all-results con parámetros correctos")
    params = {
        "skip": 0,
        "limit": 10
    }
    response = requests.get(f"{BASE_URL}/evaluations/admin/all-results", headers=headers, params=params)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success', False)}")
        print(f"Data count: {len(data.get('data', []))}")
    else:
        print(f"Response: {response.text[:200]}")
    
    # Test 2: Verificar el problema con evaluation_id como string
    print("\n2. Probando con evaluation_id como string (debería fallar)")
    params_with_string_id = {
        "evaluation_id": "123",  # String en lugar de int
        "skip": 0,
        "limit": 10
    }
    response = requests.get(f"{BASE_URL}/evaluations/admin/all-results", headers=headers, params=params_with_string_id)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    # Test 3: Verificar con evaluation_id como entero
    print("\n3. Probando con evaluation_id como entero (debería funcionar)")
    params_with_int_id = {
        "evaluation_id": 1,  # Entero
        "skip": 0,
        "limit": 10
    }
    response = requests.get(f"{BASE_URL}/evaluations/admin/all-results", headers=headers, params=params_with_int_id)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success', False)}")
        print(f"Data count: {len(data.get('data', []))}")
    else:
        print(f"Response: {response.text[:200]}")
    
    print("\n=== Diagnóstico completado ===")
    print("\nRecomendaciones:")
    print("1. El frontend debe enviar evaluation_id como número, no como string")
    print("2. Verificar que los parámetros de URL se conviertan correctamente")
    print("3. Implementar validación adicional en el backend si es necesario")

if __name__ == "__main__":
    test_evaluation_endpoints_with_fixes()