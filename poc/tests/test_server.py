import json
import itertools
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import cv2
import numpy as np
from fastapi.testclient import TestClient

from poc import read_images
from server.app import create_app
from server.experiment import similarity
from server.guides import make_report
from server.pipeline import DEFAULTS, check_model, execute, probe
from server.runner import Runner
from server.store import Failure, Store, load, release, save


TOKEN = 'test-only-token-1234567890'


def model_fixture(run, names=None, model=None):
    names = names or [f'a/{i:06}.jpg' for i in range(30)]
    model = model or run/'colmap/text'
    model.mkdir(parents=True, exist_ok=True)
    image_lines = []
    for i, name in enumerate(names, 1):
        frame = run/'frames'/name
        frame.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(frame), np.full((100, 200, 3), 128, np.uint8))
        # All observations are in the top-left quarter; the box must follow these, not a pinhole assumption.
        xy = ' '.join(f'{10+pid%20} {20+pid%20} {pid}' for pid in range(1, 101))
        image_lines += [f'{i} 1 0 0 0 {-i} 0 0 1 {name}', xy]
    (model/'images.txt').write_text('\n'.join(image_lines)+'\n')
    (model/'cameras.txt').write_text('1 SIMPLE_RADIAL 200 100 120 100 50 0\n')
    tracks = ' '.join(f'{i} 0' for i in range(1, len(names)+1))
    (model/'points3D.txt').write_text('\n'.join(f'{pid} {pid/100} 0 0 255 255 255 0.5 {tracks}' for pid in range(1,101))+'\n')
    return model


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.running = threading.Event()
        self.finish = threading.Event()
        def processor(run, project, captures, config):
            self.running.set()
            self.finish.wait(5)
            status = load(run/'status.json')
            status.update(state='failed', finished_at=time.time(), error={'code': 'TEST', 'message': 'fixture'})
            save(run/'status.json', status)
        self.app = create_app(self.root, TOKEN, processor=processor)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        self.client.headers['Authorization'] = 'Bearer '+TOKEN
        self.project = self.client.post('/projects').json()['project_id']
        self.path = self.root/self.project

    def tearDown(self):
        self.finish.set()
        self.context.__exit__(None, None, None)
        self.temporary.cleanup()

    def captures(self):
        ids = [str(uuid4()), str(uuid4())]
        value = load(self.path/'project.json')
        value['captures'] = [dict(capture_id=cid, role=role, duration=30) for cid, role in zip(ids, ('initial', 'supplement'))]
        save(self.path/'project.json', value)
        return ids

    def test_auth_ids_and_roles(self):
        self.assertEqual(self.client.get('/health', headers={'Authorization': 'Bearer wrong'}).status_code, 401)
        self.assertEqual(self.client.get('/projects/not-uuid/runs/not-uuid').status_code, 404)
        ids = self.captures()
        for mode, captures in [('initial', ids), ('combined', ids[:1]), ('combined', [ids[0]]*2), ('initial', [str(uuid4())])]:
            result = self.client.post(f'/projects/{self.project}/runs', json=dict(mode=mode, capture_ids=captures))
            self.assertEqual(result.status_code, 422, result.text)

    def test_busy_and_results_not_ready(self):
        ids = self.captures()
        result = self.client.post(f'/projects/{self.project}/runs', json=dict(mode='initial', capture_ids=ids[:1]))
        self.assertEqual(result.status_code, 202)
        run = result.json()['run_id']
        self.assertTrue(self.running.wait(1))
        self.assertTrue(self.client.get('/health').json()['busy'])
        duplicate = self.client.post(f'/projects/{self.project}/runs', json=dict(mode='initial', capture_ids=ids[:1]))
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.client.get(f'/projects/{self.project}/runs/{run}/report').status_code, 409)
        another = self.client.post('/projects').json()['project_id']
        self.assertEqual(self.client.get(f'/projects/{another}/runs/{run}').status_code, 404)

    def test_upload_commit_and_cleanup(self):
        with patch('server.app.probe', return_value={'duration':30, 'width':1920, 'height':1080, 'codec':'h264'}):
            response = self.client.post(f'/projects/{self.project}/captures', data={'role':'initial'},
                                        files={'file':('../../unsafe.mov', b'fixture', 'video/quicktime')})
        self.assertEqual(response.status_code, 201, response.text)
        cid = response.json()['capture_id']
        self.assertEqual((self.path/'captures'/f'{cid}.mov').read_bytes(), b'fixture')
        with patch('server.app.probe', side_effect=Failure('INVALID_VIDEO', 'invalid')):
            response = self.client.post(f'/projects/{self.project}/captures', data={'role':'initial'}, files={'file':('a.mov', b'bad')})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(list((self.path/'captures').iterdir())), 1)
        with patch('server.app.MAX_VIDEO_BYTES', 4):
            response = self.client.post(f'/projects/{self.project}/captures', data={'role':'initial'}, files={'file':('a.mov', b'12345')})
        self.assertEqual(response.status_code, 413)

    def test_body_bounded_before_multipart(self):
        with patch('server.app.MAX_VIDEO_BYTES', 1):
            response = self.client.post(f'/projects/{self.project}/captures', content=b'x'*(1024**2+2),
                                        headers={'Content-Type':'multipart/form-data; boundary=a'})
        self.assertEqual(response.status_code, 413)

    def test_media_is_registered_and_authenticated(self):
        rid = str(uuid4())
        run = self.path/'runs'/rid
        save(run/'status.json', {'state':'completed'})
        aid = str(uuid4())
        save(run/'analysis/assets.json', {aid:'guide.png'})
        (run/'analysis/guide.png').write_bytes(b'png-fixture')
        url = f'/projects/{self.project}/runs/{rid}/media/{aid}'
        self.assertEqual(self.client.get(url).content, b'png-fixture')
        self.assertEqual(self.client.get(url, headers={'Authorization':''}).status_code, 401)
        self.assertEqual(self.client.get(url.rsplit('/',1)[0]+'/'+str(uuid4())).status_code, 404)


class PipelineTests(unittest.TestCase):
    def test_atomic_save_restart_and_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(temporary)
            pid = store.create_project()
            path = store.root/pid/'runs'/str(uuid4())/'status.json'
            save(path, {'state':'running'})
            with self.assertRaises(ValueError):
                save(path, {'invalid':float('nan')})
            self.assertEqual(load(path), {'state':'running'})
            store.recover()
            self.assertEqual(load(path)['error']['code'], 'SERVER_RESTARTED')
            lock = store.acquire()
            try:
                with self.assertRaises(Failure):
                    Store(temporary).acquire()
            finally:
                release(lock)

    def test_command_failure_and_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner = Runner(temporary)
            for script, seconds, code in [('raise SystemExit(7)', 2, 'COMMAND_FAILED'), ('import time; time.sleep(10)', .05, 'TIMEOUT')]:
                with self.assertRaises(Failure) as error:
                    runner.run([sys.executable, '-c', script], seconds)
                self.assertEqual(error.exception.code, code)
            self.assertEqual(len(list(Path(temporary).glob('*.command.json'))), 2)

    def test_sustained_memory_pressure_stops_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            clock = itertools.count(0, 15)
            with patch('server.runner.sample', return_value={'pressure':'2'}), patch('server.runner.time.monotonic', side_effect=lambda: next(clock)):
                with self.assertRaises(Failure) as error:
                    Runner(temporary).run([sys.executable, '-c', 'import time; time.sleep(10)'], 100)
            self.assertEqual(error.exception.code, 'MEMORY_PRESSURE')

    def test_stderr_help_is_opt_in_and_preserves_json_stdout(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner = Runner(temporary)
            command = [sys.executable, '-c', 'import sys; print("{}"); print("--FeatureExtraction.use_gpu", file=sys.stderr)']
            self.assertEqual(json.loads(runner.run(command, 5)), {})
            self.assertIn('--FeatureExtraction.use_gpu', runner.run(command, 5, include_stderr=True))

    def test_probe_rejects_hdr_duration_and_invalid(self):
        class ProbeRunner:
            def __init__(self, value): self.value = value
            def run(self, *args): return json.dumps(self.value)
        valid = dict(streams=[dict(width=1920,height=1080,codec_name='h264')], format={'duration':'30'})
        self.assertEqual(probe('fixture', ProbeRunner(valid), 'initial')['duration'], 30)
        for value, code in [({}, 'INVALID_VIDEO'), ({**valid, 'format':{'duration':'61'}}, 'VIDEO_DURATION'),
            ({**valid, 'streams':[{**valid['streams'][0], 'color_transfer':'arib-std-b67'}]}, 'HDR_UNSUPPORTED')]:
            with self.assertRaises(Failure) as error: probe('fixture', ProbeRunner(value), 'initial')
            self.assertEqual(error.exception.code, code)

    def test_real_observations_boxes_and_direction(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            model_fixture(run)
            report = make_report(run, 30, 'fixture')
            candidates = [r for r in report['regions'] if r['recommended']]
            self.assertEqual(len(candidates), 3)
            for row in candidates:
                x,y,w,h = row['bounding_box']
                self.assertTrue(0 <= x <= x+w <= 1 and 0 <= y <= y+h <= 1)
                self.assertLess(x+w, .3)
                self.assertLess(y+h, .6)
                self.assertEqual(row['capture_from'], '후보 위치 미확인')
                self.assertIsNone(row['direction_vector'])
                self.assertIsNone(row['direction_asset_id'])
                self.assertIn('표시 영역', row['instruction'])
            self.assertEqual(report['source'], 'real')
            self.assertEqual(report['viewpoint_status'], 'candidate_pose_required')
            self.assertEqual(len(load(run/'analysis/assets.json')), 3)

    def test_registration_and_disconnected_supplement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = [f'a/{i:06}.jpg' for i in range(30)]
            model = model_fixture(root, names)
            frames = [dict(name=n, role='initial') for n in names]
            self.assertEqual(check_model(model, frames, 'initial'), 30)
            with self.assertRaises(Failure): check_model(model, frames*2, 'initial')
            frames += [dict(name=f'b/{i}.jpg', role='supplement') for i in range(20)]
            with self.assertRaises(Failure) as error: check_model(model, frames, 'combined')
            self.assertEqual(error.exception.code, 'SUPPLEMENT_DISCONNECTED')

    def test_missing_tool_marks_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)/'run'
            save(run/'status.json', dict(run_id='fixture', mode='initial', state='queued'))
            with patch('server.pipeline.shutil.which', return_value=None):
                execute(run, Path(temporary), [], dict(DEFAULTS))
            status = load(run/'status.json')
            self.assertEqual(status['state'], 'failed')
            self.assertEqual(status['error']['code'], 'TOOL_UNAVAILABLE')

    def test_pipeline_orchestration_with_fixture_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            run = project/'runs'/str(uuid4())
            cid = str(uuid4())
            save(run/'status.json', dict(run_id=run.name, mode='initial', state='queued'))
            commands = []
            original = Runner.run
            def fixture_command(runner, args, timeout, deadline=None, cwd=None, include_stderr=False):
                commands.append(list(map(str, args)))
                if str(args[0]) == sys.executable:
                    return original(runner, args, timeout, deadline, cwd, include_stderr)
                if args[0] == 'ffprobe':
                    return json.dumps(dict(streams=[dict(width=1920,height=1080,codec_name='h264')], format={'duration':'30'}))
                if args[0] == 'ffmpeg' and '-i' in args:
                    folder = Path(args[-1]).parent
                    for i in range(1,61): cv2.imwrite(str(folder/f'{i:06}.jpg'), np.ones((100,200,3),np.uint8)*128)
                if args[0] == 'colmap' and args[1] == 'mapper' and '-h' not in args:
                    (Path(args[args.index('--output_path')+1])/'0').mkdir()
                if args[0] == 'colmap' and args[1] == 'model_converter' and '-h' not in args:
                    output = Path(args[args.index('--output_path')+1])
                    names = sorted(str(p.relative_to(run/'frames')) for p in (run/'frames').glob('*/*.jpg'))
                    model_fixture(run, names, output)
                return '--FeatureExtraction.use_gpu --FeatureMatching.use_gpu'
            with patch('server.pipeline.shutil.which', return_value='/fixture/tool'), patch.object(Runner, 'run', fixture_command):
                execute(run, project, [dict(capture_id=cid, role='initial', duration=30)], dict(DEFAULTS))
            status = load(run/'status.json')
            self.assertEqual(status['state'], 'completed', status)
            report = load(run/'analysis/report.json')
            self.assertEqual(report['registered_frames'], 60)
            self.assertEqual(report['input_frames'], 60)
            config = load(run/'run-config.json')
            self.assertIn('cli_help', config)
            self.assertTrue(any('sequential_matcher' in c and '-h' not in c for c in commands))
            self.assertEqual(len(load(run/'frames.json')), 60)

    def test_similarity_recovers_transform_and_rejects_degenerate(self):
        source = np.array([[0,0,0], [1,0,0], [0,1,0], [0,0,1]], dtype=float)
        rotation = np.array([[0,-1,0], [1,0,0], [0,0,1]])
        target = 2*source@rotation.T + [3,4,5]
        result = similarity(source, target)
        self.assertAlmostEqual(result['scale'], 2)
        np.testing.assert_allclose(result['rotation'], rotation, atol=1e-10)
        self.assertLess(result['rmse'], 1e-10)
        with self.assertRaises(ValueError): similarity([[0,0,0],[1,0,0],[2,0,0]], [[0,0,0],[1,0,0],[2,0,0]])


if __name__ == '__main__':
    unittest.main()
