#!/usr/bin/env python3
"""Instala los APK originales de MAXOBD juntos; por defecto solo verifica."""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass

PACKAGE = "com.jiawei.maxobd"
ACTIVITY = PACKAGE + "/.obd.ObdActivity"
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 128 * 1024
MAX_ENTRIES = 64


class InstallerError(Exception):
    """Un problema que debe detener la operación sin borrar datos."""


@dataclass
class PreparedPackage:
    profile: dict
    files: list


def load_profiles():
    path = pathlib.Path(__file__).resolve().with_name("perfiles.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["profiles"]


def prepare_package(source, destination, profiles):
    """Extraer solo nombres conocidos y verificar los bytes antes de usar ADB."""
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > MAX_ENTRIES or len(names) != len(set(names)):
            raise InstallerError("XAPK con demasiadas entradas o nombres duplicados.")
        if sum(entry.file_size for entry in entries) > MAX_ARCHIVE_BYTES:
            raise InstallerError("El XAPK excede el límite descomprimido de 512 MiB.")
        if "manifest.json" not in names:
            raise InstallerError("Falta manifest.json: se necesita el XAPK completo.")
        if archive.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES:
            raise InstallerError("Manifiesto demasiado grande.")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if not isinstance(manifest, dict) or manifest.get("package_name") != PACKAGE:
            raise InstallerError("Este XAPK no identifica el paquete MAXOBD esperado.")
        profile = next((p for p in profiles if
                        str(p["version_code"]) == str(manifest.get("version_code"))
                        and p["version_name"] == manifest.get("version_name")
                        and set(p["sha256"]) == {n for n in names if n.lower().endswith(".apk")}), None)
        if not profile:
            raise InstallerError("Versión o conjunto de APK no reconocido; revisa docs/compatibilidad.md.")
        listed = manifest.get("split_apks")
        if (not isinstance(listed, list)
                or any(not isinstance(item, dict) for item in listed)
                or len(listed) != len(profile["sha256"])
                or {item.get("file") for item in listed} != set(profile["sha256"])):
            raise InstallerError("El manifiesto no enumera los componentes esperados.")
        if str(manifest.get("min_sdk_version")) != str(profile["min_sdk"]):
            raise InstallerError("El SDK mínimo del manifiesto no coincide con el perfil.")
        files = []
        for name, expected in profile["sha256"].items():
            # No extractall(): nunca se usan rutas arbitrarias del archivo.
            if pathlib.PurePosixPath(name).name != name or "\\" in name:
                raise InstallerError("Nombre de componente no permitido.")
            target = pathlib.Path(destination) / name
            digest = hashlib.sha256()
            with archive.open(name) as original, target.open("wb") as output:
                for chunk in iter(lambda: original.read(1024 * 1024), b""):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != expected:
                raise InstallerError("SHA-256 distinto del archivo examinado: " + name)
            files.append(target)
        return PreparedPackage(profile, files)


class Adb:
    def __init__(self, executable="adb", serial=None):
        self.executable = executable
        self.serial = serial

    def run(self, *arguments, device=True, timeout=30):
        command = [self.executable]
        if device:
            if not self.serial:
                raise InstallerError("No se ha seleccionado un dispositivo.")
            command += ["-s", self.serial]
        command += list(arguments)
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise InstallerError("ADB agotó el tiempo. Comprueba la conexión y el estado de instalación antes de repetir.") from error
        if result.returncode:
            raise InstallerError((result.stdout + "\n" + result.stderr).strip())
        return result.stdout.strip()


def select_device(adb, requested=None):
    output = adb.run("devices", "-l", device=False)
    devices = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1] in {"device", "unauthorized", "offline", "recovery", "sideload", "no"}:
            devices[fields[0]] = fields[1]
    if requested:
        state = devices.get(requested)
        serial = requested
    else:
        if not devices:
            raise InstallerError("No se detecta la tableta. Conecta un cable USB de datos y activa depuración USB.")
        if len(devices) != 1:
            raise InstallerError("Hay varios dispositivos. Selecciona uno con --serial; no se eligió ninguno.")
        serial, state = next(iter(devices.items()))
    if state == "unauthorized":
        raise InstallerError("Desbloquea la tableta y acepta el aviso «¿Permitir depuración USB?» para esta computadora.")
    if state != "device":
        raise InstallerError("Dispositivo no disponible o sin permiso USB: " + str(state))
    adb.serial = serial
    return serial


def parse_properties(text):
    properties = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\[([^]]+)\]: \[(.*)\]", line.strip())
        if match:
            properties[match[1]] = match[2]
    return properties


def validate_device(properties, profile):
    try:
        sdk = int(properties.get("ro.build.version.sdk", "0"))
    except ValueError as error:
        raise InstallerError("No se pudo leer el nivel API de Android.") from error
    if sdk < profile["min_sdk"]:
        raise InstallerError("Esta versión requiere Android 5.0 / API 21 o superior.")
    abi_text = properties.get("ro.product.cpu.abilist") or properties.get("ro.product.cpu.abi", "")
    abis = {abi.strip() for abi in abi_text.split(",")}
    if profile["abi"] not in abis:
        raise InstallerError("Arquitectura incompatible: el XAPK requiere " + profile["abi"])
    return sdk


def validate_installed_version(info, profile):
    name = re.search(r"\bversionName=(\S+)", info)
    code = re.search(r"\bversionCode=(\d+)", info)
    if (name is None) != (code is None):
        raise InstallerError("No se pudo determinar completamente la versión instalada.")
    if name and (name[1] != profile["version_name"] or int(code[1]) != profile["version_code"]):
        raise InstallerError("Hay otra versión de MAXOBD instalada. No se degrada ni se desinstala automáticamente.")
    return name[1] if name else None


def inspect_device(adb, profile):
    properties = parse_properties(adb.run("shell", "getprop"))
    sdk = validate_device(properties, profile)
    current = validate_installed_version(adb.run("shell", "dumpsys package " + PACKAGE), profile)
    print("Dispositivo:", properties.get("ro.product.model", "modelo no informado"))
    print("API:", sdk, "| ABI del conjunto:", profile["abi"])
    print("Versión instalada:", current or "no instalada")


def install_package(adb, prepared):
    output = adb.run("install-multiple", "-r", *(str(f) for f in prepared.files), timeout=180)
    if not re.search(r"^Success\s*$", output, re.MULTILINE):
        raise InstallerError("ADB no confirmó Success: " + output)
    info = adb.run("shell", "dumpsys package " + PACKAGE)
    if validate_installed_version(info, prepared.profile) is None:
        raise InstallerError("ADB informó éxito, pero no se pudo confirmar el paquete instalado.")
    paths = [line for line in adb.run("shell", "pm path " + PACKAGE).splitlines() if line.startswith("package:")]
    if len(paths) != len(prepared.files):
        raise InstallerError("No se pudo confirmar el número de componentes instalados; revisa pm path.")
    print("Success: instalación completa; no se solicitó borrar datos de MAXOBD.")
    print("Para abrir la aplicación: adb -s", adb.serial, "shell am start -n", ACTIVITY)
    print("Comprueba el inicio en pantalla. La conexión con el adaptador OBD es una prueba separada.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xapk", type=pathlib.Path, required=True, help="XAPK original completo")
    parser.add_argument("--serial", help="serial de adb devices; obligatorio si hay varios dispositivos")
    parser.add_argument("--adb", default="adb", help="ruta a adb/adb.exe o nombre en PATH")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--instalar", action="store_true", help="instalar juntos los componentes conservando datos")
    actions.add_argument("--solo-archivo", action="store_true", help="verificar XAPK sin conectar con la tableta")
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="maxobd-") as temporary:
            prepared = prepare_package(args.xapk, temporary, load_profiles())
            print("XAPK verificado:", prepared.profile["version_name"], "|", prepared.profile["abi"])
            print("Los tres APK coinciden con los SHA-256 de las copias examinadas.")
            if args.solo_archivo:
                print("Verificación local terminada. No se ejecutó ADB.")
                return 0
            executable = shutil.which(args.adb)
            if not executable:
                raise InstallerError("No se encuentra ADB. Obtén Platform Tools oficiales: https://developer.android.com/tools/releases/platform-tools")
            adb = Adb(executable)
            select_device(adb, args.serial)
            inspect_device(adb, prepared.profile)
            if args.instalar:
                install_package(adb, prepared)
            else:
                print("Verificación terminada. No se instaló nada. Añade --instalar para aplicar la reparación.")
        return 0
    except (InstallerError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
