# 🛡️ GUARDIAHEXBOT PLATFORM

Plataforma multi-bot de Telegram con panel maestro SUPERADMIN, bots para socios, versiones V1–V5, sistema de créditos, roles, estadísticas, auditoría y conexión central a API.

## 👑 Arquitectura principal

- GUARDIAHEXBOT es el bot principal / MASTER.
- El SUPERADMIN tiene control total.
- Cada socio tiene su propio bot.
- Todos los bots utilizan un mismo motor central.
- Cada bot mantiene sus usuarios, créditos, roles y configuración separados.
- FastAPI para backend y panel.
- Aiogram para Telegram.
- PostgreSQL para base de datos.
- WebSockets para actualizaciones en tiempo real.

## 🤖 Bots de socios

Cada bot tendrá:

- Token Telegram independiente.
- OWNER propio.
- Hasta 4 FUNDADORES / COFUNDADORES.
- ADMINS.
- SELLERS.
- USERS.
- Créditos independientes.
- Grupo propio.
- Canal propio.
- Historial propio.
- Grupo de compra / venta y suscripciones.
- Estadísticas propias.

## 📦 Versiones

| Versión | Botones | CMD |
|---|---:|---:|
| V1 INICIAL | 10/19 | 25/72 |
| V2 INICIAL PLUS | 13/19 | 40/72 |
| V3 AVANZADO | 16/19 | 55/72 |
| V4 AVANZADO PLUS | 18/19 | 65/72 |
| V5 BUSINESS | 19/19 | 72/72 |

La versión de cada bot solamente puede ser modificada por el SUPERADMIN.

## 🎛️ Control de CMD

El panel maestro permitirá:

- Activar y desactivar CMD.
- Configurar CMD según versión.
- Crear excepciones por bot.
- Ver estado operativo.
- Gestionar las 19 categorías.
- Gestionar el catálogo de 72 CMD.

## 💳 Sistema de créditos

Comandos principales:

/cred ID CANTIDAD

/sub ID DIAS PLAN

El SELLER puede transferir créditos únicamente desde su propio saldo.

## 👑 Roles

Jerarquía:

SUPERADMIN  
OWNER  
FUNDADOR / COFUNDADOR  
ADMIN  
SELLER  
USER

Los roles son independientes por bot.

El SUPERADMIN tiene acceso global.

## ⚙️ Panel del socio

El socio solamente podrá:

- Encender / apagar su bot.
- Gestionar hasta 4 FUNDADORES / COFUNDADORES.
- Cambiar o eliminar su CANAL.
- Cambiar o eliminar su GRUPO.

No podrá modificar:

- Versión.
- CMD.
- API.
- Token.
- Foto.
- Branding.
- Configuración global.

## 📜 Auditoría

Cada bot tendrá:

📜 HISTORIAL  
💳 COMPRA Y VENTA / SUSCRIPCIONES

Se registrarán:

- Consultas.
- Créditos.
- Suscripciones.
- Sellers.
- Cambios de roles.
- Encendido / apagado.
- Grupo / canal.
- Errores internos.
- Actividad administrativa.

El SUPERADMIN tendrá además historial global.

## 📊 Estadísticas

El SUPERADMIN podrá ver:

- Estadísticas globales.
- Estadísticas por socio.
- Estadísticas por bot.
- Usuarios.
- Consultas.
- Créditos.
- Suscripciones.
- Sellers.
- Consumo.
- Errores.

Cada socio solamente podrá ver las estadísticas de su propio bot mediante:

/estadisticas

## 📡 API

La conexión API será centralizada.

Variables previstas:

FUENTESDATA_ENABLED  
FUENTESDATA_BASE_URL  
FUENTESDATA_TOKEN

Durante el desarrollo la API podrá permanecer desactivada.

Cuando se agreguen las credenciales reales, el sistema podrá activarse desde el panel maestro.

## 🔐 Seguridad

Nunca subir a GitHub:

- .env
- Tokens Telegram
- Tokens API
- Contraseñas
- Base de datos
- Logs privados

## 🚀 Despliegue

GitHub  
↓  
VPS  
↓  
FastAPI  
↓  
PostgreSQL  
↓  
Bot Manager  
↓  
GUARDIAHEXBOT + bots de socios

## 🛡️ Proyecto

GUARDIAHEXBOT PLATFORM

Sistema multi-bot administrado desde un panel maestro con control centralizado y actualización en tiempo real.

Estado: EN CONSTRUCCIÓN 🚧
