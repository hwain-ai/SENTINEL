"""Inert sealed input profiles; no installed helper is executed."""

import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.test_go_inputs import sealed_fixture, unseal
from sentinel import content_root, go_inputs, go_runtime
from sentinel.errors import SentinelError


V1 = 'sentinel-go-support-v1'
V2 = 'sentinel-go-support-v2'
COMPANION = 'support/bin/sentinel-go-reference-runner'


class ReferenceInputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.addCleanup(unseal, self.base)
        self.sdk = sealed_fixture(self.base, 'sdk', {'bin/go': (b'inert Go', True)}, 'dependencies')
        self.dependencies = sealed_fixture(self.base, 'deps', {'module': (b'inert module', False)}, 'dependencies')
        self.corpus = sealed_fixture(self.base, 'corpus', {'value.go': (b'package fixture\n', False)}, 'corpus')
        pins = {'binarySha256': self.sdk._entries[0].sha256,
                'installedTreeSha256': go_runtime.release_tree_sha256(self.sdk)}
        patcher = mock.patch.dict(go_runtime.GO_LOCK, pins)
        patcher.start()
        self.addCleanup(patcher.stop)
        lock = json.dumps({'repository': 'SENTINEL_GO', 'status': 'locked',
                           'toolchains': {'go': go_runtime.GO_LOCK}}).encode()
        self.runtime = go_runtime.verify_go_runtime(self.sdk, lock, hashlib.sha256(lock).hexdigest())
        self.counter = 0

    def fixture(self, version=V2, mutate=None):
        files = {path: (('inert ' + path).encode(), True) for path in go_inputs.NATIVE_IDENTITIES}
        files.update({path: (('inert ' + path).encode(), '/bin/' in path) for path in go_inputs.SUPPORT_FILES})
        if version == V2:
            files[COMPANION] = (b'inert reference runner', True)
        record = {'schemaVersion': 'sentinel-go-artifact-v1', 'layoutVersion': 'sentinel-go-layout-v1',
                  'toolVersion': '0.1.0', 'buildSourceManifestSha256': 'a'*64,
                  'toolchainLockSha256': self.runtime.lock_sha256, 'backendLockSha256': 'b'*64,
                  'goModSha256': 'c'*64, 'goSumSha256': 'd'*64,
                  'runtimeTreeSha256': self.runtime.tree_sha256,
                  'files': [{'path': path, 'mode': '0500', 'bytes': len(files[path][0]),
                             'sha256': hashlib.sha256(files[path][0]).hexdigest(), 'identity': identity}
                            for path, identity in sorted(go_inputs.NATIVE_IDENTITIES.items())]}
        canonical = json.dumps(record, sort_keys=True, separators=(',', ':')).encode() + b'\n'
        record['manifestSha256'] = hashlib.sha256(canonical).hexdigest()
        artifact_raw = json.dumps(record, indent=2).encode() + b'\n'
        support_paths = set(go_inputs.SUPPORT_FILES) | ({COMPANION} if version == V2 else set())
        support = {'schemaVersion': version,
                   'makePackage': {'version': '4.3-4.1build2', 'sha256': '1fe6a815b56c7b6e9ce4086a363f09444bbd0a0d30e230c453d0b78e44b57a99'},
                   'goMutesting': 'v0.0.0-20251226130216-48d0401f00fb',
                   'files': [{'path': path, 'sha256': hashlib.sha256(files[path][0]).hexdigest()}
                             for path in sorted(support_paths)]}
        if version == V2:
            support.update(referenceOnly=True, certified=False, referenceRunner={
                'path': COMPANION, 'identity': 'sentinel-go-reference-runner/1',
                'executionSchema': 'sentinel-go-reference-execution-v1', 'profile': 'replay-identity-v1',
                'buildSourceManifestSha256': record['buildSourceManifestSha256'],
                'nativeArtifactJsonSha256': hashlib.sha256(artifact_raw).hexdigest()})
        files['artifact.json'] = (artifact_raw, False)
        if mutate:
            mutate(support, files, record)
        files['support.json'] = (json.dumps(support).encode(), False)
        self.counter += 1
        artifact = sealed_fixture(self.base, 'artifact-' + str(self.counter), files, 'artifact')
        return artifact

    def prepare(self, artifact, **kwargs):
        make_digest = hashlib.sha256(b'inert support/bin/make').hexdigest()
        with mock.patch.object(go_inputs, '_MAKE_SHA256', make_digest, create=True):
            return go_inputs.prepare_go_inputs(self.runtime, artifact, self.dependencies, self.corpus, **kwargs)

    def assert_failure(self, operation):
        with self.assertRaises(SentinelError) as caught:
            operation()
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ('goInputsFailed', 5))

    def test_explicit_profile_exists_and_real_v1_v2_validate(self):
        self.assertIn('support_schema', inspect.signature(go_inputs.prepare_go_inputs).parameters,
                      'explicit support-v2 selector is missing')
        with mock.patch('subprocess.Popen', side_effect=AssertionError('input validation executed a binary')):
            for version in (V1, V2):
                artifact = self.fixture(version)
                inputs = self.prepare(artifact, support_schema=version)
                self.assertEqual(inputs.support_schema, version)
                self.assertEqual(len(inputs.artifact._entries), 9 if version == V1 else 10)
                self.assertEqual(go_inputs.roots(inputs), (self.sdk, artifact, self.dependencies, self.corpus))
                with mock.patch.object(go_inputs, '_MAKE_SHA256', hashlib.sha256(b'inert support/bin/make').hexdigest()):
                    go_inputs.recheck_go_inputs(inputs)
                if version == V1:
                    self.assertEqual(self.prepare(artifact), inputs)
                self.assert_failure(lambda: self.prepare(artifact, support_schema=V2 if version == V1 else V1))

    def test_selector_rejects_before_any_lock_or_filesystem_io(self):
        self.assertIn('support_schema', inspect.signature(go_inputs.prepare_go_inputs).parameters)
        for selector in (None, True, 1, '', 'sentinel-go-support-v3'):
            with self.subTest(selector=selector), mock.patch.object(go_inputs, '_verify_lock', side_effect=AssertionError('lock I/O')):
                self.assert_failure(lambda: go_inputs.prepare_go_inputs(None, None, None, None, support_schema=selector))
                inputs = go_inputs.GoPreparedInputs(None, None, None, None, 1000, 1000, (), selector)
                self.assert_failure(lambda: go_inputs.recheck_go_inputs(inputs))

    def test_old_seven_positional_fields_retain_v1_default(self):
        inputs = go_inputs.GoPreparedInputs(None, None, None, None, 1000, 1000, ())
        self.assertEqual(getattr(inputs, 'support_schema', None), V1)

    def test_original_make_pin_is_unchanged(self):
        self.assertEqual(go_inputs._MAKE_SHA256,'d78b8f1d099fbcfb6f2f49ab87223b9b68fb3956642f92d6ec6de812e8afa965')

    def test_v1_retains_order_policy_but_rejects_reference_fields_and_companion(self):
        reordered = self.fixture(V1,lambda s,f,r: s.update(files=s['files'][::-1]))
        self.assertEqual(self.prepare(reordered).support_schema,V1)
        for mutate in [lambda s,f,r: s.update(referenceOnly=True),
                       lambda s,f,r: s.update(referenceRunner={}),
                       lambda s,f,r: f.update({COMPANION:(b'inert companion',True)}),
                       lambda s,f,r: s.update(schemaVersion=V2)]:
            self.assert_failure(lambda: self.prepare(self.fixture(V1,mutate)))

    def test_native_contract_keeps_three_rows_and_canonical_body_hash(self):
        def native_mutator(change):
            def mutate(support,files,record):
                change(record)
                body = {k:v for k,v in record.items() if k != 'manifestSha256'}
                record['manifestSha256'] = hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()+b'\n').hexdigest()
                raw = json.dumps(record,indent=2).encode()+b'\n'
                files['artifact.json'] = (raw,False)
                support['referenceRunner']['nativeArtifactJsonSha256'] = hashlib.sha256(raw).hexdigest()
            return mutate
        for change in [lambda r:r['files'].append(dict(r['files'][0])),
                       lambda r:r['files'].pop(), lambda r:r.update(extra=True),
                       lambda r:r['files'][0].update(bytes=True),
                       lambda r:r['files'][0].update(identity='wrong'),
                       lambda r:r.update(buildSourceManifestSha256='A'*64)]:
            self.assert_failure(lambda:self.prepare(self.fixture(mutate=native_mutator(change)),support_schema=V2))
        def wrong_body(s,f,r):
            r['manifestSha256'] = '0'*64
            raw = json.dumps(r).encode()
            f['artifact.json'] = (raw,False)
            s['referenceRunner']['nativeArtifactJsonSha256'] = hashlib.sha256(raw).hexdigest()
        self.assert_failure(lambda:self.prepare(self.fixture(mutate=wrong_body),support_schema=V2))

    def test_v2_recheck_detects_replacement_and_preserves_raw_interrupt(self):
        inputs = self.prepare(self.fixture(),support_schema=V2)
        path = inputs.artifact.root/'support.json'
        original = path.read_bytes()
        substitute = original.replace(b'replay-identity-v1',b'replay-identity-v0')
        read_regular = go_inputs.oci._read_regular
        def replace_during_read(target,*args):
            if target != path:
                return read_regular(target,*args)
            path.chmod(0o600)
            path.write_bytes(substitute)
            path.chmod(0o400)
            try:
                return read_regular(target,*args)
            finally:
                path.chmod(0o600)
                path.write_bytes(original)
                path.chmod(0o400)
        with mock.patch.object(go_inputs,'_MAKE_SHA256',hashlib.sha256(b'inert support/bin/make').hexdigest()):
            with mock.patch.object(go_inputs.oci,'_read_regular',side_effect=replace_during_read):
                self.assert_failure(lambda:go_inputs.recheck_go_inputs(inputs))
            go_inputs.recheck_go_inputs(inputs)
            with mock.patch.object(go_inputs.oci,'_read_regular',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    go_inputs.recheck_go_inputs(inputs)
            path.chmod(0o600)
            path.write_bytes(substitute)
            path.chmod(0o400)
            self.assert_failure(lambda:go_inputs.recheck_go_inputs(inputs))

    def test_v2_support_duplicate_json_key_cannot_replace_sealed_record(self):
        inputs = self.prepare(self.fixture(),support_schema=V2)
        raw = (inputs.artifact.root/'support.json').read_bytes()
        duplicate = raw.replace(b'"referenceOnly": true',b'"referenceOnly": true, "referenceOnly": true')
        self.assertNotEqual(raw,duplicate)
        root = sealed_fixture(self.base,'duplicate-record',{'support.json':(duplicate,False)},'artifact')
        self.assert_failure(lambda:go_inputs._record(root,'support.json'))

    def test_v2_closed_manifest_and_companion_failures(self):
        self.assertIn('support_schema', inspect.signature(go_inputs.prepare_go_inputs).parameters)
        mutations = [
            lambda s,f,r: s.update(extra=True), lambda s,f,r: s.pop('referenceOnly'),
            lambda s,f,r: s.update(referenceOnly=1), lambda s,f,r: s.update(certified=0),
            lambda s,f,r: s.update(files=s['files'][::-1]),
            lambda s,f,r: s['files'].__setitem__(0, s['files'][1]),
            lambda s,f,r: s['files'][0].update(sha256='A'*64),
            lambda s,f,r: s['files'][0].update(path=[]),
            lambda s,f,r: f.pop(COMPANION),
            lambda s,f,r: f.update({COMPANION: (b'inert reference runner', False)}),
            lambda s,f,r: f.update({'support/bin/extra': (b'extra', True)}),
            lambda s,f,r: s['referenceRunner'].update(nativeArtifactJsonSha256=r['manifestSha256']),
            lambda s,f,r: s.update(referenceRunner=[]),
            lambda s,f,r: s['referenceRunner'].pop('profile'),
            lambda s,f,r: s.update(makePackage={}),
            lambda s,f,r: s.update(goMutesting='wrong'),
            lambda s,f,r: s.update(files=s['files'][:-1]),
            lambda s,f,r: s.update(files=s['files']+[s['files'][0]]),
            lambda s,f,r: s['files'][0].update(extra=0),
        ]
        for field, value in [('path','wrong'), ('identity','wrong'), ('executionSchema','wrong'),
                             ('profile','wrong'), ('buildSourceManifestSha256','0'*64),
                             ('nativeArtifactJsonSha256',True), ('extra','wrong')]:
            mutations.append(lambda s,f,r,field=field,value=value: s['referenceRunner'].update({field:value}))
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                self.assert_failure(lambda: self.prepare(self.fixture(mutate=mutate), support_schema=V2))


if __name__ == '__main__':
    unittest.main()
