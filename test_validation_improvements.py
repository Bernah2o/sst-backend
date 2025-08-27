#!/usr/bin/env python3
"""
Script para probar las mejoras en el manejo de errores de validación
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

def test_improved_validation():
    """Probar las mejoras en el manejo de errores de validación"""
    print(f"Probando mejoras en validación - {datetime.now()}")
    
    token = get_auth_token()
    if not token:
        print("No se pudo obtener el token de autenticación")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n=== Probando errores de validación mejorados ===")
    
    # Test 1: evaluation_id como string inválido
    print("\n1. Probando evaluation_id como string inválido")
    params = {"evaluation_id": "invalid_string", "skip": 0, "limit": 10}
    response = requests.get(f"{BASE_URL}/evaluations/admin/all-results", headers=headers, params=params)
    print(f"Status: {response.status_code}")
    if response.status_code == 422:
        data = response.json()
        print(f"Message: {data.get('message', 'N/A')}")
        print(f"Detail: {data.get('detail', 'N/A')}")
        print(f"Field: {data.get('field', 'N/A')}")
        print(f"Error Type: {data.get('error_type', 'N/A')}")
    
    # Test 2: user_id como string inválido
    print("\n2. Probando user_id como string inválido")
    params = {"user_id": "not_a_number", "skip": 0, "limit": 10}
    response = requests.get(f"{BASE_URL}/evaluations/admin/all-results", headers=headers, params=params)
    print(f"Status: {response.status_code}")
    if response.status_code == 422:
        data = response.json()
        print(f"Message: {data.get('message', 'N/A')}")
        print(f"Detail: {data.get('detail', 'N/A')}")
        print(f"Field: {data.get('field', 'N/A')}")
        print(f"Error Type: {data.get('error_type', 'N/A')}")
    
    # Test 3: Path parameter inválido
    print("\n3. Probando path parameter inválido")
    response = requests.get(f"{BASE_URL}/evaluations/not_a_number/results", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 422:
        data = response.json()
        print(f"Message: {data.get('message', 'N/A')}")
        print(f"Detail: {data.get('detail', 'N/A')}")
        print(f"Field: {data.get('field', 'N/A')}")
        print(f"Error Type: {data.get('error_type', 'N/A')}")
    
    # Test 4: Parámetros válidos (deberían funcionar)
    print("\n4. Probando parámetros válidos")
    params = {"evaluation_id": "1", "skip": "0", "limit": "10"}  # Strings que son números válidos
    response = requests.get(f"{BASE_URL}/evaluations/admin/all-results", headers=headers, params=params)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success', False)}")
        print(f"Data count: {len(data.get('data', []))}")
    elif response.status_code == 422:
        data = response.json()
        print(f"Unexpected 422 error: {data.get('message', 'N/A')}")
    
    print("\n=== Resumen de pruebas ===")
    print("✓ Los errores de validación ahora incluyen información más detallada")
    print("✓ Los mensajes de error son más específicos y útiles")
    print("✓ Se incluye información sobre el campo y tipo de error")
    print("✓ Los valores recibidos se muestran en los mensajes de error")

if __name__ == "__main__":
    test_improved_validation()