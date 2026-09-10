# Portal de aplicaciones

Portal inicial para centralizar el acceso local a:

- PORTAL DE HORARIOS
- CONCILIADOR DE COSTOS
- CONCILIADOR CIERRE DE CAJAS
- REVISOR DE OFERTAS
- PORTAL DE COMPRAS Y RRHH

## Arranque rapido

Desde esta carpeta:

```powershell
.\start_all_apps.bat
```

El portal queda en:

```text
http://127.0.0.1:9000
```

Tambien puedes iniciar solo el portal:

```powershell
.\start_portal.bat
```

## Publicar cambios

Cuando hagas cambios locales y quieras mandarlos a GitHub:

```powershell
.\scripts\publish.ps1 -Message "Describe el cambio"
```

El servidor queda configurado para revisar GitHub automaticamente y aplicar los cambios con Docker.

## Docker en servidor

El portal esta preparado para ejecutarse con Docker:

```bash
docker compose up -d --build
```

Por defecto el contenedor escucha en `127.0.0.1:9000` y Apache publica el portal en:

```text
http://192.168.10.7/
```

Si necesitas otro puerto:

```bash
PORTAL_HTTP_PORT=9000 docker compose up -d --build
```

## Actualizacion automatica en servidor

En el servidor Linux, el instalador configura un timer de `systemd` que revisa GitHub cada minuto:

```bash
bash scripts/install_server_autoupdate.sh
```

El instalador tambien puede configurar Apache como proxy inverso hacia Docker para usar `http://192.168.10.7/`.

Repositorio configurado:

```text
https://github.com/jaguz794/union_proyectos.git
```

## Puertos configurados

- Portal local: `9000`
- Portal servidor: `192.168.10.7`
- PORTAL DE HORARIOS: `192.168.10.7:8010`
- CONCILIADOR DE COSTOS: `192.168.10.9:5173`
- CONCILIADOR CIERRE DE CAJAS: `192.168.10.7:8017`
- PORTAL DE COMPRAS Y RRHH: `192.168.10.7:3000`
- REVISOR DE OFERTAS: temporal en construccion

## Configuracion

Los nombres, rutas y enlaces viven en `portal_config.json`.
Si una aplicacion cambia de carpeta o puerto, actualiza ese archivo y reinicia el portal.

## Notas

- El portal no mueve ni modifica los proyectos originales.
- `PORTAL DE HORARIOS`, `CONCILIADOR DE COSTOS`, `CONCILIADOR CIERRE DE CAJAS` y `PORTAL DE COMPRAS Y RRHH` redireccionan a las IPs configuradas.
- `REVISOR DE OFERTAS` muestra una pagina temporal de construccion.
