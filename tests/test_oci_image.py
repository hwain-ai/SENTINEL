import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


def raw(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def image_fixture(config_changes=None, manifest_changes=None):
    image_config = {
        "architecture": "amd64",
        "os": "linux",
        "config": {},
        "rootfs": {"type": "layers", "diff_ids": ["sha256:" + "a" * 64]},
    }
    if config_changes:
        image_config.update(config_changes)
    config = raw(image_config)
    manifest_value = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": "sha256:" + hashlib.sha256(config).hexdigest(),
            "size": len(config),
        },
        "layers": [
            {
                "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "digest": "sha256:" + "b" * 64,
                "size": 123,
            }
        ],
    }
    if manifest_changes:
        manifest_value.update(manifest_changes)
    manifest = raw(manifest_value)
    reference = "docker.io/library/ubuntu@sha256:" + hashlib.sha256(manifest).hexdigest()
    return reference, manifest, config


def fixture_for_raw_config(
    config,
    manifest_media_type="application/vnd.oci.image.manifest.v1+json",
    config_media_type="application/vnd.oci.image.config.v1+json",
    layer_media_type="application/vnd.oci.image.layer.v1.tar+gzip",
):
    manifest = raw({
        "schemaVersion": 2,
        "mediaType": manifest_media_type,
        "config": {
            "mediaType": config_media_type,
            "digest": "sha256:" + hashlib.sha256(config).hexdigest(),
            "size": len(config),
        },
        "layers": [{
            "mediaType": layer_media_type,
            "digest": "sha256:" + "b" * 64,
            "size": 123,
        }],
    })
    reference = "docker.io/library/ubuntu@sha256:" + hashlib.sha256(manifest).hexdigest()
    return reference, manifest, config


def verifier():
    spec = importlib.util.find_spec("sentinel.oci_image")
    if spec is None:
        raise AssertionError("sentinel.oci_image is not implemented")
    module = __import__("sentinel.oci_image", fromlist=["verify_image"])
    if not hasattr(module, "verify_image"):
        raise AssertionError("verify_image is not implemented")
    return module.verify_image


class ImageVerificationTests(unittest.TestCase):
    def test_image_module_and_public_verifier_exist(self):
        spec = importlib.util.find_spec("sentinel.oci_image")
        self.assertIsNotNone(spec, "sentinel.oci_image is not implemented")
        module = __import__("sentinel.oci_image", fromlist=["verify_image"])
        self.assertTrue(hasattr(module, "verify_image"), "verify_image is not implemented")

    def test_valid_manifest_returns_immutable_identity(self):
        verify_image = verifier()
        reference, manifest, config = image_fixture()
        identity = verify_image(reference, manifest, config)
        self.assertEqual(identity.reference, reference)
        self.assertEqual(identity.image_id, "sha256:" + hashlib.sha256(config).hexdigest())
        self.assertEqual((identity.os, identity.architecture), ("linux", "amd64"))
        with self.assertRaises((AttributeError, TypeError)):
            identity.os = "windows"

    def test_rejects_digest_descriptor_and_platform_mismatches(self):
        from sentinel.errors import SentinelError

        verify_image = verifier()
        reference, manifest, config = image_fixture()
        cases = [
            (reference[:-1] + ("0" if reference[-1] != "0" else "1"), manifest, config),
            image_fixture(config_changes={"architecture": "arm64"}),
            image_fixture(config_changes={"os": "windows"}),
            image_fixture(manifest_changes={"schemaVersion": 1}),
            image_fixture(manifest_changes={"mediaType": "application/vnd.oci.image.index.v1+json"}),
        ]
        bad_descriptor = json.loads(manifest)
        bad_descriptor["config"]["size"] += 1
        cases.append((
            "docker.io/library/ubuntu@sha256:" + hashlib.sha256(raw(bad_descriptor)).hexdigest(),
            raw(bad_descriptor),
            config,
        ))
        for arguments in cases:
            with self.subTest(arguments=arguments[0:1]):
                with self.assertRaises(SentinelError) as caught:
                    verify_image(*arguments)
                self.assertEqual((caught.exception.code, caught.exception.exit_code), ("ociImageFailed", 5))

    def test_rejects_malicious_or_unbounded_json(self):
        from sentinel.errors import SentinelError

        verify_image = verifier()
        reference, manifest, config = image_fixture()
        malicious = [
            b'{"schemaVersion":2,"schemaVersion":2}',
            b'{"schemaVersion":NaN}',
            (b'[' * 80) + b'0' + (b']' * 80),
            b"",
            b"x" * (1024 * 1024 + 1),
        ]
        for bad_manifest in malicious:
            with self.subTest(size=len(bad_manifest)):
                with self.assertRaises(SentinelError):
                    verify_image(reference, bad_manifest, config)

    def test_rejects_layer_rootfs_and_implicit_privilege(self):
        from sentinel.errors import SentinelError

        verify_image = verifier()
        cases = [
            image_fixture(config_changes={"rootfs": {"type": "layers", "diff_ids": []}}),
            image_fixture(config_changes={"config": {"Volumes": {"/data": {}}}}),
            image_fixture(config_changes={"config": {"Privileged": True}}),
            image_fixture(manifest_changes={"layers": [{"mediaType": "text/plain", "digest": "sha256:" + "b" * 64, "size": 1}]}),
        ]
        for arguments in cases:
            with self.subTest(reference=arguments[0]):
                with self.assertRaises(SentinelError):
                    verify_image(*arguments)

    def test_rejects_each_invalid_descriptor_field_independently(self):
        from sentinel.errors import SentinelError

        verify_image = verifier()
        _reference, manifest, config = image_fixture()
        base = json.loads(manifest)
        mutations = []

        wrong_digest = json.loads(manifest)
        wrong_digest["config"]["digest"] = "sha256:" + "c" * 64
        mutations.append(wrong_digest)

        wrong_config_media = json.loads(manifest)
        wrong_config_media["config"]["mediaType"] = "application/octet-stream"
        mutations.append(wrong_config_media)

        malformed_layer_digest = json.loads(manifest)
        malformed_layer_digest["layers"][0]["digest"] = "sha256:not-a-digest"
        mutations.append(malformed_layer_digest)

        negative_layer_size = json.loads(manifest)
        negative_layer_size["layers"][0]["size"] = -1
        mutations.append(negative_layer_size)

        self.assertEqual(base["config"]["size"], len(config))
        for value in mutations:
            with self.subTest(config=value["config"], layer=value["layers"][0]):
                changed_manifest = raw(value)
                changed_reference = "docker.io/library/ubuntu@sha256:" + hashlib.sha256(changed_manifest).hexdigest()
                with self.assertRaises(SentinelError):
                    verify_image(changed_reference, changed_manifest, config)

    def test_rejects_malicious_or_oversized_config_document(self):
        from sentinel.errors import SentinelError

        verify_image = verifier()
        digest = "sha256:" + "a" * 64
        configs = [
            (
                b'{"architecture":"amd64","architecture":"amd64","os":"linux",'
                b'"config":{},"rootfs":{"type":"layers","diff_ids":["' + digest.encode() + b'"]}}'
            ),
            (
                b'{"architecture":"amd64","os":"linux","created":NaN,'
                b'"config":{},"rootfs":{"type":"layers","diff_ids":["' + digest.encode() + b'"]}}'
            ),
            raw({
                "architecture": "amd64",
                "os": "linux",
                "config": {},
                "rootfs": {"type": "layers", "diff_ids": [digest]},
                "deep": json.loads("[" * 70 + "0" + "]" * 70),
            }),
            b" " * (1024 * 1024 + 1),
        ]
        for config in configs:
            with self.subTest(size=len(config)):
                arguments = fixture_for_raw_config(config)
                with self.assertRaises(SentinelError):
                    verify_image(*arguments)

    def test_accepts_valid_docker_schema_two_manifest(self):
        config = raw({
            "architecture": "amd64",
            "os": "linux",
            "config": {},
            "rootfs": {"type": "layers", "diff_ids": ["sha256:" + "a" * 64]},
        })
        arguments = fixture_for_raw_config(
            config,
            manifest_media_type="application/vnd.docker.distribution.manifest.v2+json",
            config_media_type="application/vnd.docker.container.image.v1+json",
            layer_media_type="application/vnd.docker.image.rootfs.diff.tar.gzip",
        )
        identity = verifier()(*arguments)
        self.assertEqual(identity.image_id, "sha256:" + hashlib.sha256(config).hexdigest())

    def test_rejects_tag_and_non_ubuntu_digest_references(self):
        from sentinel.errors import SentinelError

        verify_image = verifier()
        reference, manifest, config = image_fixture()
        references = ["ubuntu:latest", reference.replace("library/ubuntu", "library/alpine")]
        for changed_reference in references:
            with self.subTest(reference=changed_reference):
                with self.assertRaises(SentinelError):
                    verify_image(changed_reference, manifest, config)


if __name__ == "__main__":
    unittest.main()
