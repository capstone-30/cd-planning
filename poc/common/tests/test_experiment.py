import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from server.experiment import main, prepare_or_train
from server.store import Failure, Store, load, release, save


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.store = Store(self.root)
        self.project = self.store.create_project()
        self.run_id = str(uuid4())
        self.run = self.root/self.project/'runs'/self.run_id
        save(self.run/'status.json', dict(state='completed', reconstruction=dict(state='not_started')))
        save(self.run/'run-config.json', dict(selected_model='colmap/sparse/0', long_edge=960))
        self.args = SimpleNamespace(command='prepare', project=self.project, run=self.run_id,
                                    settings=self.root/'settings.json', argv=self.root/'argv.json')

    def test_prepare_uses_saved_model_and_preserves_existing_dataset(self):
        with patch('server.experiment.Runner.run') as command:
            prepare_or_train(self.args, self.store)
        argv, timeout = command.call_args.args
        self.assertEqual(timeout, 600)
        self.assertEqual(argv[argv.index('--input_path')+1], str(self.run/'colmap/sparse/0'))
        (self.run/'colmap/undistorted').mkdir(parents=True)
        with patch('server.experiment.Runner.run') as command:
            with self.assertRaisesRegex(ValueError, '이미 준비된'):
                prepare_or_train(self.args, self.store)
            command.assert_not_called()

    def test_failed_training_persists_failure_and_keeps_settings(self):
        self.args.command = 'train'
        (self.run/'colmap/undistorted/sparse').mkdir(parents=True)
        settings = dict(resolution=960, steps=3000, density='default')
        save(self.args.settings, settings)
        save(self.args.argv, ['brush', '{dataset}', '--output', '{output}'])
        with patch('server.experiment.Runner.run', side_effect=[
            '--version --output', 'fixture version', Failure('COMMAND_FAILED', 'fixture failure')
        ]):
            with self.assertRaises(Failure):
                prepare_or_train(self.args, self.store)
        status = load(self.run/'status.json')
        self.assertEqual(status['reconstruction'], dict(state='failed', message='fixture failure'))
        self.assertEqual(load(self.run/'run-config.json')['brush']['settings'], settings)

    def test_cli_dispatch_releases_lock_after_command_failure(self):
        with patch('sys.argv', ['experiment', '--data', str(self.root), 'doctor']), \
             patch('server.experiment.free_space'), \
             patch('server.experiment.doctor', side_effect=Failure('TOOL_UNAVAILABLE', 'fixture')):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 1)
        release(self.store.acquire())
