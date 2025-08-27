#!/usr/bin/env python3
"""
Script para diagnosticar el problema específico del error 422 en endpoints de evaluación
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

def test_specific_endpoints():
    """Probar endpoints específicos que podrían causar el error 422"""
    print(f"Iniciando pruebas específicas - {datetime.now()}")
    
    token = get_auth_token()
    if not token:
        print("No se pudo obtener el token de autenticación")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Probar /{evaluation_id}/results con string
    print("\n1. Probando /evaluations/{evaluation_id}/results con string")
    response = requests.get(f"{BASE_URL}/evaluations/invalid_string/results", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:300]}")
    
    # Test 2: Probar /{evaluation_id}/results con número válido
    print("\n2. Probando /evaluations/{evaluation_id}/results con número")
    response = requests.get(f"{BASE_URL}/evaluations/1/results", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success', False)}")
        print(f"Data count: {len(data.get('data', []))}")
    else:
        print(f"Response: {response.text[:300]}")
    
    # Test 3: Probar /admin/all-results con diferentes parámetros
    print("\n3. Probando /evaluations/admin/all-results con parámetros mixtos")
    
    # Caso 3a: Con evaluation_id como string en query params
    params = {
        "evaluation_id": "invalid_string",
        "skip": 0,
        "limit": 10
    }
    response = requests.get(f"{BASE_URL}/evaluations/admin/all-results", headers=headers, params=params)
    print(f"3a. Con evaluation_id string - Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    # Caso 3b: Con user_id como string
    params = {
        "user_id": "invalid_string",
        "skip": 0,
        "limit": 10
    }
    response = requests.get(f"{BASE_URL}/evaluations/admin/all-results", headers=headers, params=params)
    print(f"3b. Con user_id string - Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    # Test 4: Probar otros endpoints con path parameters
    print("\n4. Probando otros endpoints con path parameters")
    
    # Caso 4a: GET /{evaluation_id}
    response = requests.get(f"{BASE_URL}/evaluations/invalid_string", headers=headers)
    print(f"4a. GET /evaluations/invalid_string - Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    # Caso 4b: POST /{evaluation_id}/start
    response = requests.post(f"{BASE_URL}/evaluations/invalid_string/start", headers=headers)
    print(f"4b. POST /evaluations/invalid_string/start - Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    print("\n=== Análisis de resultados ===")
    print("Si algún endpoint devuelve 422, ese es el que está causando el problema.")
    print("Los endpoints con path parameters deberían validar automáticamente el tipo.")
    print("Los endpoints con query parameters pueden ser más permisivos.")

if __name__ == "__main__":
    test_specific_endpoints()