import importlib.util
import json
from pathlib import Path
import sys
import unittest
from dataclasses import asdict
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sentinel.errors import SentinelError
from tests.test_oci_image import image_fixture
from tests.test_sandbox import DockerScript


class GoSandboxTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec("sentinel.go_sandbox"), "Closed Go sandbox is missing")
        from sentinel import go_sandbox
        return go_sandbox

    def test_arbitrary_command_and_timeout_are_rejected(self):
        module = self.module()
        for command, sources, timeout in [("/bin/sh", (), 1), ("original", (), True),
                                         ("original", (), 901), ("original", (), float('nan')),
                                         ("mutation", ("../evil.go",), 10), ("original", ("main.go",), 10)]:
            with self.subTest(command=command, sources=sources, timeout=timeout):
                with self.assertRaises(SentinelError):
                    module._request_arguments(module.GoRunRequest(command, sources, timeout))

    def test_profile_has_only_four_readonly_roots(self):
        module = self.module()
        roots = tuple('/tmp/approved/root-' + str(index) for index in range(4))
        profile = module._go_profile(1000, 1000, roots)
        self.assertEqual(len(profile.mounts), 4)
        self.assertEqual(profile.user, '1000:1000')
        self.assertEqual(profile.memory, 2147483648)
        self.assertEqual(profile.pids, 128)
        self.assertEqual(profile.nofile, 1024)
        self.assertEqual(set(dict(profile.tmpfs)), {'/tmp', '/work/project', '/opt/sentinel/go/toolchain/state'})

    def test_malformed_request_types_have_safe_errors(self):
        module = self.module()
        for request in (module.GoRunRequest([]), module.GoRunRequest({}),
                        module.GoRunRequest('mutation', ([],)), module.GoRunRequest('mutation', ({},))):
            with self.subTest(request=request):
                try:
                    module._request_arguments(request)
                except Exception as error:
                    self.assertIsInstance(error, SentinelError)
                else:
                    self.fail('malformed request accepted')

    def test_tampered_mount_never_passes_inspect(self):
        module = self.module()
        from sentinel import sandbox
        from sentinel.oci_image import verify_image
        reference, manifest, config = image_fixture()
        identity = verify_image(reference, manifest, config)
        roots = tuple('/tmp/approved/root-' + str(index) for index in range(4))
        profile = module._go_profile(1000, 1000, roots)
        argv = ['/usr/bin/true']
        fake = DockerScript(self, identity, argv)
        fake.name, fake.nonce = 'sentinel-fixture', 'nonce'
        value = json.loads(fake.container_inspect('created'))
        value['Config']['User'] = profile.user
        value['HostConfig'].update({'NanoCpus':profile.nano_cpus, 'Memory':profile.memory,
                                   'MemorySwap':profile.memory, 'PidsLimit':profile.pids,
                                   'Tmpfs':dict(profile.tmpfs),
                                   'Ulimits':[{'Name':'nofile','Hard':1024,'Soft':1024},{'Name':'core','Hard':0,'Soft':0}],
                                   'Mounts':sandbox._host_mounts(profile)})
        value['Mounts'] = sandbox._inspected_mounts(profile)
        def verify(record):
            sandbox._verify_created_container(identity, fake.container_id, fake.name, fake.nonce, argv,
                                              json.dumps(record).encode(), profile)
        verify(value)
        for location, key, replacement in [('mount','RW',True), ('mount','Source','/run'),
                                          ('mount','Propagation','rshared'), ('host','ReadonlyRootfs',False),
                                          ('host','Memory',True), ('host','PidsLimit',0)]:
            changed = json.loads(json.dumps(value))
            target = changed['Mounts'][0] if location == 'mount' else changed['HostConfig']
            target[key] = replacement
            with self.subTest(location=location,key=key):
                with self.assertRaises(SentinelError):
                    verify(changed)
        for extra in [value['Mounts'] + [value['Mounts'][0]], value['Mounts'][:-1]]:
            changed = dict(value, Mounts=extra)
            with self.assertRaises(SentinelError):
                verify(changed)

    def test_observation_keeps_raw_diagnostics_private_and_rejects_bad_records(self):
        module = self.module()
        from sentinel import sandbox
        box = module.GoSandbox.__new__(module.GoSandbox)
        box._inputs = SimpleNamespace(release_hashes=('a'*64,'b'*64,'c'*64,'d'*64))
        value = {'schemaVersion':'sentinel-go-observation-v1','commandExitCode':6,
                 'stdoutBytes':10,'stderrBytes':0,'stdoutSha256':'e'*64,
                 'stderrSha256':'f'*64,'corpusSha256':'d'*64}
        def observe(record, suffix=b'private source and /absolute/path'):
            child = sandbox._CommandResult(json.dumps(record).encode()+b'\n'+suffix,b'',0,None)
            return box._observation(child,{'ExitCode':0,'OOMKilled':False},False)
        observed = observe(value)
        self.assertEqual(observed.command_exit_code,6)
        self.assertNotIn('private source',json.dumps(asdict(observed)))
        self.assertNotIn('/absolute/path',json.dumps(asdict(observed)))
        for field, invalid in [('commandExitCode',True),('stdoutBytes',False),('stderrBytes',-1),
                               ('corpusSha256','0'*64),('stdoutSha256','bad'),('extra','unknown')]:
            with self.subTest(field=field):
                with self.assertRaises(SentinelError):
                    observe(dict(value,**{field:invalid}))


if __name__ == '__main__':
    unittest.main()
