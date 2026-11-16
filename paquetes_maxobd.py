#!/usr/bin/env python3
"""Descarga, verifica y copia los paquetes originales observados de MAXOBD."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from instalar_maxobd import Adb, InstallerError, select_device, validate_installed_version

PACKAGE = "com.jiawei.maxobd"
BASE = "/sdcard/Android/data/" + PACKAGE + "/files"
CATALOG = Path(__file__).resolve().parent / "datos/catalogo-paquetes-2026-11-16.json"
HOSTS = ("car-diagnostic-app.oss-accelerate.aliyuncs.com",
         "car-diagnostic-app.oss-us-east-1.aliyuncs.com")
BLOCK = 1024 * 1024


class PackageError(Exception):
    pass


def validate_url(url):
    u = urlsplit(url)
    if (u.scheme != "https" or u.hostname not in HOSTS or u.username or u.password
            or u.port is not None or u.query or u.fragment
            or not u.path.startswith("/MAXOBD/CarDat/")
            or not re.fullmatch(r"/[A-Za-z0-9_./-]+", u.path)
            or ".." in PurePosixPath(u.path).parts):
        raise PackageError("URL fuera del bucket oficial permitido.")
    return u


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def load_catalog(path):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise PackageError("Catálogo demasiado grande.")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or value.get("package") != PACKAGE:
        raise PackageError("Formato de catálogo no reconocido.")
    groups = value.get("groups", [])
    files = value.get("files", [])
    if not 1 <= len(groups) <= 100 or not 1 <= len(files) <= 10000:
        raise PackageError("Cantidad de grupos o archivos no permitida.")
    folders = {}
    for group in groups:
        typ, folder = group["types"], group["folder"]
        if (not isinstance(typ, str) or typ in folders
                or not re.fullmatch(r"[a-z][a-z0-9]*", folder)
                or folder in folders.values()):
            raise PackageError("Grupo duplicado o carpeta no válida.")
        folders[typ] = folder
    seen = set()
    for item in files:
        rel = PurePosixPath(item["file"])
        if (rel.is_absolute() or len(rel.parts) != 3 or ".." in rel.parts
                or not re.fullmatch(r"[A-Za-z0-9_./-]+", item["file"])
                or rel.parts[0] != folders.get(item["types"])
                or rel.parts[1] not in {"folder", "cn", "de", "en", "es", "fr", "it", "pl", "pt", "ru", "na", "jp", "eu"}
                or rel.parts[2] in {".", ".."}
                or item["file"].lower() in seen):
            raise PackageError("Ruta no válida o duplicada en el catálogo.")
        seen.add(item["file"].lower())
        if (type(item["size"]) is not int or not 0 < item["size"] <= 128 * 1024 * 1024
                or not re.fullmatch(r"[0-9a-f]{32}", item["md5"])
                or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
            raise PackageError("Tamaño o huellas no válidos.")
        validate_url(item["url"])
    if sum(x["size"] for x in files) > 3 * 1024**3:
        raise PackageError("El catálogo supera 3 GiB.")
    for group in groups:
        subset = [x for x in files if x["types"] == group["types"]]
        if len(subset) != group["files"] or sum(x["size"] for x in subset) != group["bytes"]:
            raise PackageError("Los totales del grupo no coinciden.")
    return value


def local_path(root, relative):
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise PackageError("La ruta local sale del destino, posiblemente mediante un enlace.")
    return path


def matches(path, item):
    if not path.is_file() or path.stat().st_size != item["size"]:
        return False
    md5, sha = hashlib.md5(), hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            md5.update(block)
            sha.update(block)
    return md5.hexdigest() == item["md5"] and sha.hexdigest() == item["sha256"]


def read_block(item, start, end, timeout):
    original = validate_url(item["url"])
    for attempt in range(4):
        host = HOSTS[attempt % len(HOSTS)]
        url = urlunsplit(("https", host, original.path, "", ""))
        headers = {"Accept-Encoding": "identity", "User-Agent": "maxobd-android5-installer/2"}
        ranged = item["size"] > BLOCK
        if ranged:
            headers["Range"] = f"bytes={start}-{end}"
        try:
            opener = build_opener(OfficialRedirects())
            with opener.open(Request(url, headers=headers), timeout=timeout) as response:
                if ranged:
                    expected = f'bytes {start}-{end}/{item["size"]}'
                    if response.status != 206 or response.headers.get("Content-Range") != expected:
                        raise PackageError("El servidor no confirmó el rango solicitado.")
                elif response.status != 200:
                    raise PackageError("El servidor no confirmó el archivo completo.")
                data = response.read(end - start + 2)
                if len(data) != end - start + 1:
                    raise PackageError("Bloque incompleto o mayor que lo solicitado.")
                return data
        except (URLError, OSError, HTTPException, PackageError):
            if attempt == 3:
                raise
            time.sleep(1 + attempt)


def download_one(root, item, timeout):
    dest = local_path(root, item["file"])
    if matches(dest, item):
        return "cache"
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=dest.name + ".", suffix=".part", dir=dest.parent, delete=False) as stream:
            temporary = Path(stream.name)
            for start in range(0, item["size"], BLOCK):
                end = min(start + BLOCK - 1, item["size"] - 1)
                stream.write(read_block(item, start, end, timeout))
        if not matches(temporary, item):
            raise PackageError("Tamaño, MD5 o SHA-256 distinto del catálogo: " + item["file"])
        temporary.replace(dest)
        return "servidor"
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def verify_local(root, files):
    bad = [x["file"] for x in files if not matches(local_path(root, x["file"]), x)]
    if bad:
        raise PackageError(f"Faltan o no coinciden {len(bad)} archivos: " + ", ".join(bad[:5]))


def parse_listing(text):
    directory, result = None, {}
    for line in text.splitlines():
        if line.startswith(BASE) and line.endswith(":"):
            directory = line[:-1]
        elif directory and line.startswith("-"):
            cols = line.split()
            date = next((i for i, x in enumerate(cols) if re.fullmatch(r"\d{4}-\d\d-\d\d", x)), None)
            if date is not None and date > 0 and cols[date - 1].isdigit():
                name = " ".join(cols[date + 2:])
                path = directory + "/" + name
                result[path[len(BASE) + 1:].lower()] = (path, int(cols[date - 1]))
    return result


def copy_packages(adb, root, groups, files, backup):
    # Completar todas las verificaciones antes de detener la app o escribir por ADB.
    verify_local(root, files)
    info = adb.run("shell", "dumpsys", "package", PACKAGE)
    current = validate_installed_version(info, {"version_name": "1.1.01", "version_code": 57})
    if current is None:
        raise PackageError("Instala y abre MAXOBD 1.1.01 antes de copiar el catálogo probado.")
    if backup.exists():
        raise PackageError("El destino de respaldo debe ser nuevo; no se sobrescribe un respaldo.")
    if backup.resolve().is_relative_to(root.resolve()):
        raise PackageError("El respaldo debe quedar fuera de la carpeta de paquetes.")
    adb.run("shell", "ls", "-d", BASE)
    backup.mkdir(parents=True, exist_ok=False)
    adb.run("shell", "am", "force-stop", PACKAGE)
    adb.run("pull", BASE, str(backup.resolve()), timeout=900)
    print("Respaldo de archivos externos guardado; no incluye datos privados internos.")
    print("Copiando los paquetes seleccionados; puede tardar varios minutos.")
    with tempfile.TemporaryDirectory(prefix="maxobd-transfer-", dir=root.parent) as stage:
        stage = Path(stage)
        for item in files:
            source = local_path(root, item["file"])
            target = stage / item["file"]
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source, target)
            except OSError:
                shutil.copy2(source, target)
        dirs = [str(stage / g["folder"]) for g in groups]
        adb.run("push", *dirs, BASE + "/", timeout=900)
    actual = parse_listing(adb.run("shell", "ls", "-lR", BASE, timeout=90))
    if any(actual.get(x["file"].lower(), (None, None))[1] != x["size"] for x in files):
        raise PackageError("La presencia o el tamaño en la tableta no coincide; conserva el respaldo.")
    for group in groups:
        item = min((x for x in files if x["types"] == group["types"]), key=lambda x: x["size"])
        path = actual[item["file"].lower()][0]
        if not re.fullmatch(r"/[A-Za-z0-9_./-]+", path):
            raise PackageError("Ruta inesperada al verificar la tableta.")
        # Adb.run usa texto; para datos binarios se utiliza un proceso independiente.
        command = [adb.executable, "-s", adb.serial, "exec-out", "cat", path]
        data = subprocess.run(command, check=True, capture_output=True, timeout=30).stdout
        if (len(data) != item["size"] or hashlib.md5(data).hexdigest() != item["md5"]
                or hashlib.sha256(data).hexdigest() != item["sha256"]):
            raise PackageError("La muestra del grupo no coincide: " + group["folder"])
    print(f"Copia verificada: {len(files)} tamaños y {len(groups)} muestras MD5/SHA-256.")
    print("Abre MAXOBD manualmente. No se inició un diagnóstico ni una función del vehículo.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogo", type=Path, default=CATALOG)
    parser.add_argument("--destino", type=Path, default=Path("datos-locales"))
    parser.add_argument("--marca", action="append", help="carpeta del grupo; se puede repetir, por defecto todas")
    parser.add_argument("--hilos", type=int, default=4, choices=range(1, 17), metavar="1..16")
    parser.add_argument("--timeout", type=int, default=40)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial")
    parser.add_argument("--respaldo", type=Path, help="carpeta nueva, obligatoria con --copiar")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--descargar", action="store_true")
    actions.add_argument("--verificar", action="store_true")
    actions.add_argument("--copiar", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.timeout < 1:
            raise PackageError("El tiempo de espera debe ser positivo.")
        catalog = load_catalog(args.catalogo)
        requested = set(args.marca or [g["folder"] for g in catalog["groups"]])
        known = {g["folder"] for g in catalog["groups"]}
        if not requested <= known:
            raise PackageError("Grupo desconocido: " + ", ".join(sorted(requested - known)))
        groups = [g for g in catalog["groups"] if g["folder"] in requested]
        types = {g["types"] for g in groups}
        files = [x for x in catalog["files"] if x["types"] in types]
        for group in groups:
            print(group["folder"], "|", group["car"], "|", group["files"], "archivos")
        print("Total:", len(files), "archivos |", sum(x["size"] for x in files), "bytes")
        root = args.destino / "archivos_android"
        if args.descargar:
            root.mkdir(parents=True, exist_ok=True)
            errors = []
            with ThreadPoolExecutor(max_workers=args.hilos) as pool:
                futures = {pool.submit(download_one, root, item, args.timeout): item for item in files}
                for count, future in enumerate(as_completed(futures), 1):
                    try:
                        future.result()
                    except (OSError, URLError, HTTPException, PackageError) as error:
                        errors.append(futures[future]["file"] + ": " + str(error))
                    if count % 50 == 0 or count == len(files):
                        print(f"Procesados {count}/{len(files)}; fallos {len(errors)}", flush=True)
            if errors:
                raise PackageError("Repite para recuperar pendientes. " + "; ".join(errors[:5]))
            verify_local(root, files)
            print("Todos los archivos coinciden con tamaño, MD5 y SHA-256 del catálogo.")
        elif args.verificar:
            verify_local(root, files)
            print("Verificación local completa. No se ejecutó ADB ni se modificaron archivos.")
        elif args.copiar:
            if args.respaldo is None:
                raise PackageError("Con --copiar debes indicar una carpeta nueva mediante --respaldo.")
            verify_local(root, files)
            executable = shutil.which(args.adb)
            if executable is None:
                raise PackageError("No se encuentra ADB; instala Platform Tools oficiales.")
            adb = Adb(executable)
            select_device(adb, args.serial)
            copy_packages(adb, root, groups, files, args.respaldo)
        else:
            print("Solo inventario. Añade --descargar, --verificar o --copiar para actuar.")
        return 0
    except (PackageError, InstallerError, OSError, HTTPException, subprocess.SubprocessError,
            ValueError, KeyError, TypeError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
