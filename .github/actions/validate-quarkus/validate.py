import re
import sys
from pathlib import Path

import yaml


APPLICATION_FILE = Path("src/main/resources/application.yml")
DEV_VARS_FILE = Path("devops/deploy/dev-vars.yaml")


errors = []
warnings = []


def error(rule, message, file=None):
    location = f" [{file}]" if file else ""
    errors.append(f"❌ {rule}{location}: {message}")


def warning(rule, message, file=None):
    location = f" [{file}]" if file else ""
    warnings.append(f"⚠️ {rule}{location}: {message}")


def get(data, *keys):
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def load_yaml(path):
    if not path.exists():
        error("FILE-001", "Archivo requerido no encontrado")
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    except yaml.YAMLError as exc:
        error(
            "FILE-002",
            f"YAML inválido: {exc}",
            path
        )
        return None


def validate_application():
    print("\n=== APPLICATION.YML ===")

    data = load_yaml(APPLICATION_FILE)

    if data is None:
        return None

    # APP-001
    application_name = get(
        data,
        "quarkus",
        "application",
        "name"
    )

    if not application_name:
        error(
            "APP-001",
            "quarkus.application.name es requerido",
            APPLICATION_FILE
        )
    elif not re.fullmatch(
        r"[a-z0-9]+-[a-z0-9]+-.+",
        str(application_name)
    ):
        error(
            "APP-001",
            "quarkus.application.name debe seguir "
            "la estructura channel-squad-descripcion",
            APPLICATION_FILE
        )

    # APP-002
    version = get(
        data,
        "quarkus",
        "application",
        "version"
    )

    if not version:
        error(
            "APP-002",
            "quarkus.application.version es requerido",
            APPLICATION_FILE
        )
    elif not re.fullmatch(r"v[0-9]+", str(version)):
        error(
            "APP-002",
            "La versión debe tener formato vx, por ejemplo v1",
            APPLICATION_FILE
        )

    # APP-003
    root_path = get(
        data,
        "quarkus",
        "http",
        "root-path"
    )

    if not root_path:
        error(
            "APP-003",
            "quarkus.http.root-path es requerido",
            APPLICATION_FILE
        )
    elif application_name and version:
        expected = f"/{application_name}/{version}"

        if root_path != expected:
            error(
                "APP-003",
                f"Debe ser '{expected}'",
                APPLICATION_FILE
            )

    # APP-004
    openapi_path = get(
        data,
        "quarkus",
        "smallrye-openapi",
        "path"
    )

    expected_openapi = "${quarkus.http.root-path}/openapi"

    if openapi_path != expected_openapi:
        error(
            "APP-004",
            f"Debe ser '{expected_openapi}'",
            APPLICATION_FILE
        )

    # APP-005
    health_path = get(
        data,
        "quarkus",
        "smallrye-health",
        "root-path"
    )

    expected_health = "${quarkus.http.root-path}/q/health"

    if health_path != expected_health:
        error(
            "APP-005",
            f"Debe ser '{expected_health}'",
            APPLICATION_FILE
        )

    return {
        "name": application_name,
        "version": version,
        "root_path": root_path
    }


def validate_dev_vars(application):
    print("\n=== DEV-VARS.YAML ===")

    data = load_yaml(DEV_VARS_FILE)

    if data is None:
        return

    root_path = application.get("root_path") if application else None

    # DEV-001
    readiness_path = get(
        data,
        "health_probes",
        "readiness",
        "path"
    )

    if root_path:
        expected = f"{root_path}/q/health/ready"

        if readiness_path != expected:
            error(
                "DEV-001",
                f"Debe ser '{expected}'",
                DEV_VARS_FILE
            )

    # DEV-002
    liveness_path = get(
        data,
        "health_probes",
        "liveness",
        "path"
    )

    if root_path:
        expected = f"{root_path}/q/health/live"

        if liveness_path != expected:
            error(
                "DEV-002",
                f"Debe ser '{expected}'",
                DEV_VARS_FILE
            )

    # DEV-003/004/005
    for key in [
        "hashicorp_vault_enable",
        "hashicorp_vault_quarkus_load_default",
        "hashicorp_vault_quarkus_load_app"
    ]:
        value = data.get(key)

        if value not in ("yes", "no"):
            error(
                "DEV-003",
                f"{key} debe tener valor 'yes' o 'no'",
                DEV_VARS_FILE
            )

    # DEV-006
    squad_name = data.get("squad_name")

    if not squad_name:
        error(
            "DEV-006",
            "squad_name es requerido",
            DEV_VARS_FILE
        )
    elif re.search(r"\s", str(squad_name)):
        error(
            "DEV-006",
            "squad_name no debe contener espacios",
            DEV_VARS_FILE
        )

    # DEV-007
    ms_type = data.get("ms_type")

    if ms_type not in ("UX", "BS"):
        error(
            "DEV-007",
            "ms_type debe ser 'UX' o 'BS'",
            DEV_VARS_FILE
        )

    # DEV-008
    azure_keyvault = data.get("azure_keyvault")

    if azure_keyvault not in ("yes", "no"):
        error(
            "DEV-008",
            "azure_keyvault debe ser 'yes' o 'no'",
            DEV_VARS_FILE
        )

    # DEV-009
    ingress_map = data.get("ingress_map", {})

    if isinstance(ingress_map, dict):
        for _, config in ingress_map.items():

            if isinstance(config, dict):
                ingress_path = config.get("path")

                if root_path and ingress_path != root_path:
                    error(
                        "DEV-009",
                        f"ingress_map.path debe ser '{root_path}'",
                        DEV_VARS_FILE
                    )

    # DEV-010
    configuration_name = get(
        data,
        "configuration",
        "name"
    )

    if application.get("name") and application.get("version"):
        expected = (
            f"{application['name']}-"
            f"{application['version']}"
        )

        if configuration_name != expected:
            error(
                "DEV-010",
                f"Debe ser '{expected}'",
                DEV_VARS_FILE
            )

    # DEV-011
    messages_enable = get(
        data,
        "configuration",
        "messages",
        "enable"
    )

    if messages_enable not in ("on", "off"):
        error(
            "DEV-011",
            "configuration.messages.enable "
            "debe ser 'on' u 'off'",
            DEV_VARS_FILE
        )


def main():
    application = validate_application()

    validate_dev_vars(application)

    print("\n==============================")
    print("QUARKUS VALIDATION RESULT")
    print("==============================")

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(item)

    if errors:
        print("\nErrors:")

        for item in errors:
            print(item)

        print(
            f"\n❌ Validation failed: "
            f"{len(errors)} error(s)"
        )

        sys.exit(1)

    print("\n✅ Validation successful")
    sys.exit(0)


if __name__ == "__main__":
    main()