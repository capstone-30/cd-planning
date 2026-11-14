const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {test} = require('node:test');
const vm = require('node:vm');

const source = readFileSync(`${__dirname}/../index.html`, 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];

function client() {
  const elements = new Map();
  const storage = new Map();
  const videos = [];
  const revoked = [];
  const context = vm.createContext({
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, {value:'', addEventListener(){}, classList:{toggle(){}}, scrollIntoView(){}});
        return elements.get(id);
      },
      createElement(tag) {
        assert.equal(tag, 'video');
        const video = {};
        videos.push(video);
        return video;
      },
    },
    localStorage: {getItem:k => storage.get(k), setItem:(k,v) => storage.set(k,v), removeItem:k => storage.delete(k)},
    sessionStorage: {getItem:() => null},
    URL: {createObjectURL:() => 'blob:test', revokeObjectURL:url => revoked.push(url)},
  });
  vm.runInContext(source, context);
  return {context, storage, videos, revoked, elements, run:code => vm.runInContext(code, context)};
}

for (const [role, mode, ids, runKey] of [
  ['initial', 'initial', ['new-capture'], 'runA'],
  ['supplement', 'combined', ['original', 'new-capture'], 'runAB'],
]) {
  test(`${role} keeps capture IDs, mode and result selection together`, async () => {
    const app = client();
    app.run(`
      store.set('capA', 'original'); store.set('capB', 'old-B'); store.set('runAB', 'old-AB');
      duration = async () => 30;
      ensureProject = async () => 'project';
      upload = async (project, role, file, bar) => { globalThis.uploadArgs = [project, role, bar]; return {capture_id:'new-capture'}; };
      startRun = async (mode, ids) => { globalThis.runArgs = [mode, ids]; return 'new-run'; };
      poll = async () => ({state:'completed'});
      afterRun = async role => { globalThis.resultRole = role; };
    `);
    await app.run(`handle('${role}', {size:1024})`);
    assert.deepEqual(JSON.parse(app.run('JSON.stringify(runArgs)')), [mode, ids]);
    assert.equal(app.storage.get(`cg.${runKey}`), 'new-run');
    assert.equal(app.context.resultRole, role);
    assert.equal(app.context.uploadArgs[1], role);
    if (role === 'initial') {
      assert.equal(app.storage.has('cg.capB'), false);
      assert.equal(app.storage.has('cg.runAB'), false);
    }
  });
}

test('invalid clip duration prevents upload', async () => {
  const app = client();
  app.run(`duration = async () => 5; upload = () => { throw new Error('must not upload'); };`);
  await app.run("handle('initial', {size:1024})");
  assert.match(app.elements.get('m-a').textContent, /30~60/);
});

test('video metadata releases the blob URL on success and failure', async () => {
  for (const success of [true, false]) {
    const app = client();
    const result = app.run('duration({})');
    const video = app.videos[0];
    video.duration = 30;
    success ? video.onloadedmetadata() : video.onerror();
    const seconds = await result;
    assert.equal(success ? seconds === 30 : Number.isNaN(seconds), true);
    assert.deepEqual(app.revoked, ['blob:test']);
  }
});

test('missing project clears stale captures and runs during resume', async () => {
  const app = client();
  app.run(`
    for (const key of PROJECT_KEYS) store.set(key, 'old-value');
    poll = async () => { throw {error:{code:'NOT_FOUND'}}; };
  `);
  await app.run('resume()');
  assert.equal(app.storage.size, 0);
});
