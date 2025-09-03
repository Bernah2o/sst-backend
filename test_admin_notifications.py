#!/usr/bin/env python3
"""
Script de prueba para la funcionalidad de administración de notificaciones de exámenes ocupacionales.

Este script demuestra cómo usar los nuevos endpoints para:
1. Consultar el estado de las notificaciones
2. Enviar notificaciones manuales
3. Suprimir notificaciones
4. Ver estadísticas

Credenciales de prueba:
- Email: admin@sst.com
- Contraseña: Admin123!
"""

import requests
import json
from datetime import datetime
from typing import Dict, Any

# Configuración
BASE_URL = "http://localhost:8000"  # Ajustar según tu configuración
ADMIN_EMAIL = "admin@sst.com"
ADMIN_PASSWORD = "Admin123!"

class AdminNotificationsTest:
    def __init__(self):
        self.base_url = BASE_URL
        self.token = None
        self.headers = {"Content-Type": "application/json"}
    
    def authenticate(self) -> bool:
        """Autenticar como administrador"""
        print("🔐 Autenticando como administrador...")
        
        login_data = {
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }
        
        response = requests.post(
            f"{self.base_url}/auth/login",
            data=login_data
        )
        
        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
            self.headers["Authorization"] = f"Bearer {self.token}"
            print("✅ Autenticación exitosa")
            return True
        else:
            print(f"❌ Error en autenticación: {response.status_code} - {response.text}")
            return False
    
    def get_exam_notifications(self, limit: int = 10) -> Dict[str, Any]:
        """Obtener lista de notificaciones de exámenes"""
        print(f"\n📋 Obteniendo notificaciones de exámenes (límite: {limit})...")
        
        response = requests.get(
            f"{self.base_url}/admin/notifications/exam-notifications",
            headers=self.headers,
            params={"limit": limit}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Se encontraron {len(data)} trabajadores")
            
            # Mostrar resumen
            status_count = {}
            for worker in data:
                status = worker["exam_status"]
                status_count[status] = status_count.get(status, 0) + 1
            
            print("📊 Resumen por estado:")
            for status, count in status_count.items():
                print(f"   - {status}: {count}")
            
            return data
        else:
            print(f"❌ Error obteniendo notificaciones: {response.status_code} - {response.text}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas de notificaciones"""
        print("\n📊 Obteniendo estadísticas...")
        
        response = requests.get(
            f"{self.base_url}/admin/notifications/statistics",
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Estadísticas obtenidas:")
            print(f"   - Total trabajadores: {data['total_workers']}")
            print(f"   - Sin exámenes: {data['workers_without_exams']}")
            print(f"   - Exámenes vencidos: {data['workers_with_overdue_exams']}")
            print(f"   - Próximos a vencer: {data['workers_with_upcoming_exams']}")
            print(f"   - Confirmaciones hoy: {data['total_acknowledgments_today']}")
            print(f"   - Notificaciones suprimidas: {data['suppressed_notifications']}")
            return data
        else:
            print(f"❌ Error obteniendo estadísticas: {response.status_code} - {response.text}")
            return {}
    
    def send_notifications(self, worker_ids: list, notification_type: str = "reminder", force: bool = False) -> Dict[str, Any]:
        """Enviar notificaciones a trabajadores específicos"""
        print(f"\n📧 Enviando notificaciones tipo '{notification_type}' a {len(worker_ids)} trabajadores...")
        
        data = {
            "worker_ids": worker_ids,
            "notification_type": notification_type,
            "force_send": force
        }
        
        response = requests.post(
            f"{self.base_url}/admin/notifications/send-notifications",
            headers=self.headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Resultado del envío:")
            print(f"   - Total solicitados: {result['total_requested']}")
            print(f"   - Enviados: {result['emails_sent']}")
            print(f"   - Fallidos: {result['emails_failed']}")
            print(f"   - Ya confirmados: {result['already_acknowledged']}")
            print(f"   - Trabajadores inválidos: {result['invalid_workers']}")
            
            if result['details']:
                print("\n📝 Detalles:")
                for detail in result['details'][:5]:  # Mostrar solo los primeros 5
                    print(f"   - {detail.get('worker_name', 'N/A')}: {detail['status']} - {detail['message']}")
            
            return result
        else:
            print(f"❌ Error enviando notificaciones: {response.status_code} - {response.text}")
            return {}
    
    def suppress_notifications(self, worker_ids: list, notification_type: str = None, reason: str = "Prueba administrativa") -> Dict[str, Any]:
        """Suprimir notificaciones para trabajadores específicos"""
        print(f"\n🚫 Suprimiendo notificaciones para {len(worker_ids)} trabajadores...")
        
        data = {
            "worker_ids": worker_ids,
            "reason": reason
        }
        
        if notification_type:
            data["notification_type"] = notification_type
        
        response = requests.post(
            f"{self.base_url}/admin/notifications/suppress-notifications",
            headers=self.headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Resultado de la supresión:")
            print(f"   - Total solicitados: {result['total_requested']}")
            print(f"   - Supresiones creadas: {result['suppressions_created']}")
            print(f"   - Ya suprimidas: {result['already_suppressed']}")
            
            return result
        else:
            print(f"❌ Error suprimiendo notificaciones: {response.status_code} - {response.text}")
            return {}
    
    def get_acknowledgments(self, limit: int = 10) -> list:
        """Obtener confirmaciones de notificaciones"""
        print(f"\n✅ Obteniendo confirmaciones (límite: {limit})...")
        
        response = requests.get(
            f"{self.base_url}/admin/notifications/acknowledgments",
            headers=self.headers,
            params={"limit": limit}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Se encontraron {len(data)} confirmaciones")
            
            for ack in data[:3]:  # Mostrar solo las primeras 3
                print(f"   - {ack['worker_name']}: {ack['notification_type']} el {ack['acknowledged_at'][:10]}")
            
            return data
        else:
            print(f"❌ Error obteniendo confirmaciones: {response.status_code} - {response.text}")
            return []
    
    def run_demo(self):
        """Ejecutar demostración completa"""
        print("🚀 Iniciando demostración de administración de notificaciones")
        print("=" * 60)
        
        # 1. Autenticar
        if not self.authenticate():
            return
        
        # 2. Obtener estadísticas
        stats = self.get_statistics()
        
        # 3. Obtener lista de notificaciones
        notifications = self.get_exam_notifications(limit=5)
        
        if notifications:
            # 4. Obtener trabajadores con exámenes vencidos o próximos a vencer
            workers_to_notify = [
                worker["worker_id"] for worker in notifications
                if worker["exam_status"] in ["vencido", "proximo_a_vencer"]
                and worker["worker_email"]  # Solo los que tienen email
            ][:2]  # Limitar a 2 para la demo
            
            if workers_to_notify:
                print(f"\n🎯 Trabajadores seleccionados para demo: {workers_to_notify}")
                
                # 5. Enviar notificaciones de prueba (sin forzar)
                send_result = self.send_notifications(workers_to_notify, "reminder", force=False)
                
                # 6. Suprimir notificaciones para uno de los trabajadores
                if len(workers_to_notify) > 1:
                    suppress_result = self.suppress_notifications([workers_to_notify[0]], reason="Demo de supresión")
                
                # 7. Intentar enviar nuevamente (debería ser bloqueado para el suprimido)
                print("\n🔄 Intentando enviar nuevamente (debería ser bloqueado para trabajadores suprimidos)...")
                send_result2 = self.send_notifications(workers_to_notify, "reminder", force=False)
            else:
                print("\n⚠️ No se encontraron trabajadores con exámenes vencidos o próximos que tengan email")
        
        # 8. Obtener confirmaciones
        acknowledgments = self.get_acknowledgments()
        
        print("\n" + "=" * 60)
        print("✅ Demostración completada exitosamente")
        print("\n📖 Funcionalidades disponibles:")
        print("   - Consultar estado de notificaciones por trabajador")
        print("   - Enviar notificaciones manuales (con control de duplicados)")
        print("   - Suprimir notificaciones para evitar spam")
        print("   - Ver estadísticas generales")
        print("   - Consultar historial de confirmaciones")
        print("   - Eliminar confirmaciones para reactivar notificaciones")


def main():
    """Función principal"""
    print("🔧 Script de prueba para Administración de Notificaciones SST")
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 URL Base: {BASE_URL}")
    print(f"👤 Usuario: {ADMIN_EMAIL}")
    print()
    
    # Verificar conectividad
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Servidor disponible")
        else:
            print(f"⚠️ Servidor responde con código: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"❌ No se puede conectar al servidor en {BASE_URL}")
        print("   Asegúrate de que el servidor esté ejecutándose")
        return
    
    # Ejecutar demo
    test = AdminNotificationsTest()
    test.run_demo()


if __name__ == "__main__":
    main()