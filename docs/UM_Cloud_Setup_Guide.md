# UM-Cloud · Guía de inicio (acceso vía ZeroTier)

Guía genérica para acceder a la UM-Cloud (OpenStack del laboratorio de la Universidad
de Mendoza), provisionar una VM y conectarse por SSH a través de ZeroTier.
Pensada para retomar la operación en cualquier momento sin reconstruir el contexto.

## Pre-requisitos

- Cuenta en **My-UM-Cloud** (la da la universidad).
- Cliente **ZeroTier** instalado en tu equipo (Windows / Mac / Linux).
- Cliente **SSH** (OpenSSH viene incorporado en Windows 10+, Mac y la mayoría de Linux).
- Un navegador moderno para el dashboard Horizon de OpenStack.

---

## 1. Acceso al portal My-UM-Cloud

1. Entrar al portal interno de UM-Cloud con tus credenciales de alumno.
2. La pantalla de bienvenida tiene dos botones principales:
   - **Cloud_Credentials** (naranja) — credenciales OpenStack
   - **Zerotier_Config** (azul) — vinculación de tu address ZeroTier

## 2. Obtener credenciales de la cloud

1. Click en **Cloud_Credentials**.
2. Primera vez: aparece `Credential creation in progress...` — esperar unos segundos y hacer click otra vez.
3. Aparecen: `username`, `password`, y un enlace al **Dashboard** de OpenStack (Horizon).
4. Guardar ambos en un gestor seguro. El password no se vuelve a mostrar igual; si se pierde, se regenera desde acá.

## 3. Conectar ZeroTier a la red de UM-Cloud

1. Si es la primera vez, instalar ZeroTier desde https://zerotier.com/download/.
2. Hacer **join** a la red de la cloud (el ID es público en la pantalla de bienvenida del portal):
   ```
   # Linux/Mac
   sudo zerotier-cli join <ID-DE-LA-RED>
   #   → 200 join OK

   # Windows: usar la UI (icono en la bandeja → Join Network) o ejecutar
   # zerotier-cli.bat join <ID-DE-LA-RED> desde una terminal con privilegios.
   ```
3. Obtener tu **address ZeroTier** (10 caracteres hex):
   ```
   sudo zerotier-cli info
   #   → 200 info <tu-address> 1.x.x ONLINE
   ```
4. Volver al portal, click en **Zerotier_Config**, pegar la address en la caja y click **Create_ZT**.
5. Click otra vez en **Zerotier_Config**. Si todo está OK ves un cartel verde tipo:
   ```
   You are IN!
   name   : <tu-email-uni>
   address: <tu-address-zt>
   IP     : 10.203.x.x
   ```
6. Tu PC ahora forma parte de la red interna del lab y rutea hacia las subnets de OpenStack.

> Tip: Las **rutas administradas** (managed routes) las maneja el admin del lab. Por
> defecto tu PC va a aprender rutas hacia las subnets internas de la cloud (`10.201.0.0/16`,
> `10.200.0.0/16`, etc.) vía un gateway interno (típicamente `10.203.0.250`).

## 4. Login en Horizon (dashboard OpenStack)

URL: el enlace que figura en **Cloud_Credentials**.

Completar:

| Campo | Valor |
|---|---|
| **Domain** | `Default` (con D mayúscula) |
| **User Name** | el de Cloud_Credentials |
| **Password** | el de Cloud_Credentials |

⚠️ El `Domain` NO es tu IP ni tu email ni el nombre de la universidad — es un *namespace* de Keystone, y por convención casi siempre se llama `Default`.

## 5. Familiarización con el proyecto

Antes de crear nada, revisar lo que ya viene listo:

### Quotas (Compute → Vista general)
Anotá los límites del proyecto: instancias, vCPUs, RAM, almacenamiento, IPs flotantes, etc. Suelen ser generosas para uso académico.

### Imágenes disponibles (Compute → Imágenes)
El lab pre-arma imágenes con stacks listos para usar. Las más útiles típicamente:

- `ubuntu_2404` / `ubuntu_minimal_2404` — base limpia
- `srv-docker-ubuntu2404` — Ubuntu + Docker preinstalado
- `srv-nginx-ubuntu2404` — Nginx
- `srv-postgresql-ubuntu2404` — PostgreSQL
- Imágenes especializadas para Kubernetes, n8n, etc.

### Redes (Red → Redes)
Las redes del proyecto son **compartidas** (gestionadas por el admin del cloud):

- `net_umstack` (10.201.0.0/16) — red interna principal
- `net_vmkube` (10.200.0.0/16) — red para clusters Kubernetes
- `ext_net` — red "externa" del lab (ver §12, **no es internet pública**)

⚠️ Al ser compartidas, no podés adjuntar la subnet a un router de tu proyecto (te tira "subnet not owned by project"). Las VMs simplemente se "enchufan" directo a la red.

## 6. Crear keypair SSH

1. **Compute → Pares de claves → + Crear par de claves**.
2. Nombre identificable, tipo SSH.
3. Te descarga un `.pem`. **Se descarga una sola vez**. Guardalo en lugar seguro.

### Windows: cerrar permisos del .pem

OpenSSH rechaza la key si está accesible por otros usuarios (error
`UNPROTECTED PRIVATE KEY FILE`). Hay que cerrarla:

```powershell
takeown /F C:\ruta\al\archivo.pem
icacls C:\ruta\al\archivo.pem /reset
icacls C:\ruta\al\archivo.pem /inheritance:r /grant:r "${env:USERNAME}:F"
```

## 7. Crear security group

Por defecto el SG `default` no permite nada entrante. Crear uno propio:

1. **Red → Grupos de seguridad → + Crear grupo de seguridad** (con nombre descriptivo).
2. Click en **Administrar reglas** → **+ Añadir regla**.

⚠️ **Importante sobre el origen (CIDR)**:

Cuando hacés SSH desde tu PC con ZeroTier (`10.203.x.x`), tu IP **no llega tal cual** a
la VM — la infraestructura del lab hace NAT en el camino. La VM ve los paquetes con
origen **`192.168.3.x`** (típicamente `192.168.3.250`).

Por eso:

- ❌ Mal: `10.203.0.0/16` — la VM no ve tráfico con ese origen
- ✅ Bien: `192.168.3.0/24` — cubre el rango NAT del lab

Reglas iniciales recomendadas para empezar (puerto / CIDR):

| Puerto                   | Servicio                    | Origen           |
|--------------------------|-----------------------------|------------------|
| 22                       | SSH                         | `192.168.3.0/24` |
| Otros (3000, 5432, etc.) | App / DB / lo que necesites | `192.168.3.0/24` |

> Tip: si en la primera prueba SSH falla y querés descartar problemas de red,
> podés abrir temporalmente la regla a `0.0.0.0/0`. La VM no tiene IP pública,
> así que sigue siendo inalcanzable desde internet — pero es mala práctica
> dejarlo así. Cerralo apenas confirmes que SSH anda.

## 8. (Opcional) Crear router

**Solo necesario si vas a usar floating IPs o salida a internet por un router propio.**
Para acceder a una VM por la red interna `net_umstack` desde ZeroTier, no hace falta
crear router — el cloud ya rutea esas subnets.

Si lo creás:

1. **Red → Routers → + Crear router**
2. External Network: `ext_net`
3. (Las subnets compartidas no se pueden conectar — te tira error de ownership)

## 9. Lanzar instancia

**Compute → Instancias → + Lanzar instancia**. Hay varias pestañas:

### Pestaña *Detalles*
- Nombre descriptivo, count = 1
- Availability Zone = `nova` (o la que esté disponible)

### Pestaña *Origen*
- **Seleccionar el origen de arranque**: `Imagen`
- **¿Crear volumen nuevo?**: **`No`** ⚠️
  Si lo dejás en "Sí" sin tamaño válido, falla con
  `Block Device Mapping is Invalid: Missing device UUID`.
- En la lista, buscar la imagen y click en la **flecha ↑** para moverla a "Asignado".
  Si no aparece nada en "Asignado", el wizard tira el mismo error de UUID.

### Pestaña *Sabor*
Elegir flavor según necesidades (ej. `m1.small`, `m1.medium`).

### Pestaña *Redes*
Mover `net_umstack` (u otra que corresponda) a "Asignado" con la flecha.

### Pestaña *Grupos de seguridad*
Mover el SG creado en §7 a "Asignado". El `default` puede quedar también, no estorba.

### Pestaña *Par de claves*
Seleccionar el keypair del §6.

Las demás pestañas (Puertos, Configuración, Grupo de servidores, Metadatos) se pueden
dejar en default. Click **Iniciar instancia de lanzamiento**.

Esperar 1–2 minutos:

- **Status**: `Activo`
- **Power State**: `Ejecutando`
- **Task**: vacío

## 10. Verificar conectividad

La VM recibe una IP en `net_umstack` (rango `10.201.x.x`). Desde tu PC, con ZeroTier
conectada:

### Verificar ruteo (PowerShell)
```powershell
Get-NetRoute -AddressFamily IPv4 | Where-Object { $_.DestinationPrefix -like '10.20*' }
```
Esperás ver algo como:
```
10.201.0.0/16     10.203.0.250 ZeroTier One        256
```
Si no aparece esa ruta, ZeroTier no está bien conectada o el admin no propaga ese
rango.

### Probar TCP al puerto SSH
```powershell
Test-NetConnection -ComputerName 10.201.x.x -Port 22
```
- `TcpTestSucceeded : True` → puerto accesible.
- ICMP (PingSucceeded) puede dar `False` aunque TCP funcione — ICMP no estaba abierto
  en el SG.

### SSH
```powershell
ssh -i C:\ruta\al\keypair.pem ubuntu@10.201.x.x
```
Usuario según imagen:
- `ubuntu` para `ubuntu_*` y `srv-*-ubuntu*`
- `core` para `flatcar_*`
- `debian`, `cloud-user` en otros casos — probar en orden si el primero rechaza

## 11. Si SSH falla — checklist de diagnóstico

1. **Status de la VM**: confirmar `Activo` + `Ejecutando`. Si dice `Error`, ver detalles.
2. **Console log**: Instancias → click en la VM → pestaña **Log** → últimas líneas.
   Buscar `cloud-init finished` y las "SSH HOST KEY FINGERPRINTS". Si esos mensajes no
   están, la VM no terminó de bootear.
3. **Consola VNC**: pestaña **Consola** — acceso visual al boot. Sirve para ver
   mensajes de error pero no para login (las imágenes vienen sin password,
   solo se entra con la keypair).
4. **Tracert** (Windows):
   ```powershell
   tracert -d -h 5 -w 2000 10.201.x.x
   ```
   Los paquetes deberían pasar por `10.203.0.250` (gateway ZeroTier) → `192.168.3.x`
   (infra interna del lab) → VM. Si mueren después de `192.168.3.x`, el SG no permite
   el tráfico.
5. **Verificar SG asociado**: en la pestaña *Vista general* de la VM, confirmar que el
   SG personalizado está aplicado y que las reglas son las correctas.
6. **Permisos del .pem en Windows**: si tira `UNPROTECTED PRIVATE KEY FILE`, repetir
   el bloque `icacls` del §6.

## 12. Identificar la IP origen real (afinar SG)

Una vez logueado por SSH:

```bash
echo SSH_CLIENT=$SSH_CLIENT
echo SSH_CONNECTION=$SSH_CONNECTION
```

La primera IP que figura es la que **la VM ve como origen**. Tomá esa para el
`Remote IP Prefix` del security group. En el lab UM-Cloud típicamente es
`192.168.3.250`, así que un CIDR `192.168.3.0/24` cubre bien sin abrir de más.

Si abriste el SG con `0.0.0.0/0` para destrabar el primer SSH, ahora podés cerrarlo
a `192.168.3.0/24` (o `192.168.3.250/32` para máximo cinturón) sin perder acceso.

## 13. ⚠️ Sobre acceso desde internet (fuera de ZeroTier)

**El pool de floating IPs (`ext_net`) entrega IPs privadas (`192.168.3.x`), NO IPs
internet-ruteables.**

Implicancia: una VM con floating IP **NO es alcanzable** desde 4G, wifi pública, o
cualquier red que no esté conectada a la ZeroTier del lab.

Para exponer un servicio a internet hay tres caminos:

| Opción | Pros | Contras |
|---|---|---|
| **Túnel saliente** (Cloudflare Tunnel, ngrok, frp, etc.) | Sin floating IP, sin abrir puertos, URL HTTPS pública | Depende de un servicio externo, latencia extra |
| **ZeroTier en el cliente** | Inmediato, secure-by-default, gratis | El dispositivo cliente tiene que correr ZT (PC, no siempre práctico en móviles) |
| **Pedir IP pública real al admin del lab** | Solución limpia | Depende de disponibilidad y tiempo de respuesta |

## 14. Operaciones útiles de mantenimiento

### Reiniciar / detener una VM
- Horizon: Instancias → menú de acciones (▾) al final de la fila

### Ver log de consola
- Horizon: Instancias → click en la VM → **Log**

### Eliminar VM
- Horizon: Instancias → acción → **Borrar instancia**
- El volumen de boot puede borrarse junto o quedar como volumen huérfano (ver
  Volúmenes → Volúmenes).

### Liberar floating IP que no se usa
- Red → IPs flotantes → fila correspondiente → **Liberar IP flotante**
- Para no ocupar quota innecesaria.

### Liberar keypair
- Compute → Pares de claves → seleccionar → Borrar. La clave privada en tu PC sigue
  siendo válida solo si en alguna VM ya quedó la clave pública embebida (cloud-init la
  copió a `~/.ssh/authorized_keys` al primer arranque).

---

## Resumen del flujo en una sola pasada

```
1. Login portal UM-Cloud → Cloud_Credentials
2. ZeroTier: instalar, join al network ID del lab, registrar address en el portal
3. Horizon: Domain=Default, login con las cloud credentials
4. Crear Keypair SSH (cerrar permisos del .pem en Windows con icacls)
5. Crear Security Group (origen 192.168.3.0/24 para SSH y resto)
6. Lanzar Instancia (Origen → Imagen, no volumen nuevo, mover con flechita;
                     Redes → net_umstack; SG → el creado; Keypair → el creado)
7. Esperar Activo + Ejecutando
8. SSH a 10.201.x.x con la keypair
9. Confirmar $SSH_CLIENT, afinar SG si quedó abierto
10. Mantener: liberar IPs/keys/volúmenes que no se usen, monitorear quotas
```

---

## Apéndice: rangos de red típicos del lab UM-Cloud

| Rango | Función |
|---|---|
| `10.201.0.0/16` | `net_umstack` — red interna principal del proyecto |
| `10.200.0.0/16` | `net_vmkube` — red para clusters Kubernetes |
| `10.203.0.0/24` | rango de IPs ZeroTier asignadas a clientes |
| `100.64.0.0/24` | subred de balanceo para `net_vmkube` |
| `192.168.3.0/24` | red "externa" del lab (NAT del tráfico ZT→subnets internas) |
| `192.168.3.250` | gateway NAT típico (IP origen vista por las VMs) |
| `192.168.3.x` | floating IPs (privadas, NO internet) |
