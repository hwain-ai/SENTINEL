import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

from .errors import SentinelError


MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_JSON_DEPTH = 64
REFERENCE_PREFIX = "docker.io/library/ubuntu@sha256:"
OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
DOCKER_MANIFEST = "application/vnd.docker.distribution.manifest.v2+json"
CONFIG_MEDIA_TYPES = {
    OCI_MANIFEST: "application/vnd.oci.image.config.v1+json",
    DOCKER_MANIFEST: "application/vnd.docker.container.image.v1+json",
}
LAYER_MEDIA_TYPES = {
    OCI_MANIFEST: {
        "application/vnd.oci.image.layer.v1.tar",
        "application/vnd.oci.image.layer.v1.tar+gzip",
        "application/vnd.oci.image.layer.v1.tar+zstd",
        "application/vnd.oci.image.layer.nondistributable.v1.tar",
        "application/vnd.oci.image.layer.nondistributable.v1.tar+gzip",
        "application/vnd.oci.image.layer.nondistributable.v1.tar+zstd",
    },
    DOCKER_MANIFEST: {
        "application/vnd.docker.image.rootfs.diff.tar.gzip",
        "application/vnd.docker.image.rootfs.foreign.diff.tar.gzip",
    },
}
PRIVILEGE_KEYS = {
    "binds",
    "capadd",
    "devices",
    "devicecgroupRules".lower(),
    "groupadd",
    "ipcMode".lower(),
    "links",
    "mounts",
    "networkmode",
    "pidmode",
    "portbindings",
    "privileged",
    "securityopt",
    "utsmode",
    "volumesfrom",
}


@dataclass(frozen=True)
class ImageIdentity:
    reference: str
    image_id: str
    os: str
    architecture: str


def _failure() -> SentinelError:
    return SentinelError("ociImageFailed", "OCI image verification failed", 5)


def _digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _pairs(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _failure()
        result[key] = value
    return result


def _check_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise _failure()
    if isinstance(value, dict):
        for item in value.values():
            _check_depth(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _check_depth(item, depth + 1)


def _document(raw: bytes) -> Any:
    if type(raw) is not bytes or not raw or len(raw) > MAX_DOCUMENT_BYTES:
        raise _failure()

    def reject_constant(_value: str) -> None:
        raise ValueError

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=reject_constant,
        )
        _check_depth(value)
        return value
    except SentinelError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError, TypeError):
        raise _failure()


def _descriptor(value: Any, media_types: set) -> None:
    if not isinstance(value, dict):
        raise _failure()
    if value.get("mediaType") not in media_types or not _digest(value.get("digest")):
        raise _failure()
    size = value.get("size")
    if type(size) is not int or size < 0:
        raise _failure()


def _has_implicit_privilege(config: Dict[str, Any]) -> bool:
    for key, value in config.items():
        normalized = key.lower() if isinstance(key, str) else ""
        if normalized == "volumes" and value not in (None, {}):
            return True
        if normalized in PRIVILEGE_KEYS and value not in (None, False, "", [], {}):
            return True
    return False


def verify_image(reference: str, manifest: bytes, config: bytes) -> ImageIdentity:
    try:
        if (
            not isinstance(reference, str)
            or not reference.startswith(REFERENCE_PREFIX)
            or not _digest("sha256:" + reference[len(REFERENCE_PREFIX) :])
        ):
            raise _failure()
        manifest_value = _document(manifest)
        if hashlib.sha256(manifest).hexdigest() != reference[len(REFERENCE_PREFIX) :]:
            raise _failure()
        if not isinstance(manifest_value, dict) or type(manifest_value.get("schemaVersion")) is not int:
            raise _failure()
        if manifest_value["schemaVersion"] != 2:
            raise _failure()
        manifest_media_type = manifest_value.get("mediaType")
        if manifest_media_type not in CONFIG_MEDIA_TYPES:
            raise _failure()

        config_descriptor = manifest_value.get("config")
        _descriptor(config_descriptor, {CONFIG_MEDIA_TYPES[manifest_media_type]})
        config_value = _document(config)
        config_digest = "sha256:" + hashlib.sha256(config).hexdigest()
        if config_descriptor["digest"] != config_digest or config_descriptor["size"] != len(config):
            raise _failure()

        layers = manifest_value.get("layers")
        if not isinstance(layers, list):
            raise _failure()
        for layer in layers:
            _descriptor(layer, LAYER_MEDIA_TYPES[manifest_media_type])

        if not isinstance(config_value, dict):
            raise _failure()
        if config_value.get("os") != "linux" or config_value.get("architecture") != "amd64":
            raise _failure()
        rootfs = config_value.get("rootfs")
        if not isinstance(rootfs, dict) or rootfs.get("type") != "layers":
            raise _failure()
        diff_ids = rootfs.get("diff_ids")
        if not isinstance(diff_ids, list) or len(diff_ids) != len(layers):
            raise _failure()
        if any(not _digest(item) for item in diff_ids):
            raise _failure()
        execution_config = config_value.get("config", {})
        if execution_config is None:
            execution_config = {}
        if not isinstance(execution_config, dict) or _has_implicit_privilege(execution_config):
            raise _failure()

        return ImageIdentity(reference, config_digest, "linux", "amd64")
    except SentinelError as error:
        if error.code == "ociImageFailed" and error.exit_code == 5:
            raise
        raise _failure() from None
    except Exception:
        raise _failure() from None
