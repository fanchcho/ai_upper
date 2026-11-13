// py_upper 宿主注入脚本：在页面文档创建前补齐 `window.deva`。
//
// 原版渲染层只认 `window.deva`（Electron preload 用 contextBridge 暴露）。QtWebEngine 里没有
// preload，所以这里复刻同一份对象形状：每个方法把调用转成一次 `bridge.invoke(requestId, channel, argsJson)`，
// Python 侧处理后回调 `window.__devaResolve(id, ok, payload)` 兑现 Promise。
//
// 频道名与参数顺序必须与 `apps/desktop/src/preload/index.ts` 的 `ipcRenderer.invoke(...)` 一致——
// 这一层的唯一职责就是「形状对齐」，不含任何业务判断。
//
// 生成方式：脚本源码里 `__CONFIG_JSON__` / `__PLATFORM__` 由 Python 侧替换。
(function () {
  'use strict';
  if (window.__devaBridgeInstalled) return;
  window.__devaBridgeInstalled = true;

  var pending = new Map();
  var seq = 0;
  var emitters = {};
  var channel = null;
  var ready = new Promise(function (resolve) {
    function finish(qwebchannel) {
      new qwebchannel(qt.webChannelTransport, function (ch) {
        channel = ch.objects.bridge;
        resolve(channel);
      });
    }
    if (window.QWebChannel) finish(window.QWebChannel);
    else if (window.qt && window.qt.webChannelTransport) {
      // qwebchannel.js 已由 QWebEngineScript 在更早一轮注入时缺失，这里补不上；
      // 由 Python 侧保证注入顺序（qwebchannel.js → shim.js），故此处只兜底报错。
      console.error('QWebChannel 未加载：注入顺序错误');
    } else {
      console.error('qt.webChannelTransport 缺失：页面未配置 QWebChannel');
    }
  });

  /** 一次 `ipcRenderer.invoke`：返回 Promise，结果由 Python 侧回填。 */
  function invoke(name) {
    var extra = Array.prototype.slice.call(arguments, 1);
    return ready.then(function (bridge) {
      return new Promise(function (resolve, reject) {
        var id = ++seq;
        pending.set(id, { resolve: resolve, reject: reject });
        try {
          bridge.invoke(String(id), name, JSON.stringify(extra));
        } catch (err) {
          pending.delete(id);
          reject(err);
        }
      });
    });
  }

  /** `ipcRenderer.on` 的对应物：返回退订函数。 */
  function on(name) {
    return function (cb) {
      var set = emitters[name] || (emitters[name] = new Set());
      set.add(cb);
      return function () {
        set.delete(cb);
      };
    };
  }

  window.__devaResolve = function (id, ok, payload) {
    var entry = pending.get(Number(id));
    if (!entry) return;
    pending.delete(Number(id));
    if (ok) entry.resolve(payload);
    else {
      var err = new Error((payload && payload.message) || '通道调用失败');
      err.name = (payload && payload.name) || 'Error';
      err.channelError = payload || {};
      entry.reject(err);
    }
  };

  window.__devaEmit = function (name, payload) {
    var set = emitters[name];
    if (!set) return;
    set.forEach(function (cb) {
      try {
        cb(payload);
      } catch (err) {
        console.error(err);
      }
    });
  };

  var okTrue = function () {
    return Promise.resolve({ ok: true });
  };
  var okFalse = function () {
    return Promise.resolve({ ok: false });
  };

  window.deva = {
    platform: '__PLATFORM__',
    window: {
      minimize: function () { return invoke('window:minimize'); },
      toggleMaximize: function () { return invoke('window:toggle-maximize'); },
      close: function () { return invoke('window:close'); },
      isFullScreen: function () { return invoke('window:is-fullscreen'); },
      onFullScreen: on('window:fullscreen'),
      setOverlaySymbolColor: function (color) {
        return invoke('window:set-overlay', color);
      }
    },
    fs: {
      openFolder: function () { return invoke('fs:open-folder'); },
      revealFolder: function (p) { return invoke('fs:reveal-folder', p); },
      readDir: function (p) { return invoke('fs:read-dir', p); },
      readFile: function (p) { return invoke('fs:read-file', p); },
      writeFile: function (p, c) { return invoke('fs:write-file', p, c); },
      pickAttachments: function () { return invoke('fs:pick-attachments'); },
      pasteAttachment: function (f) { return invoke('fs:paste-attachment', f); },
      attachmentImage: function (p, full) { return invoke('fs:attachment-image', p, full); },
      droppedEntries: function (files) { return invoke('fs:dropped-entries', files); }
    },
    config: {
      getSync: function () { return __CONFIG_JSON__; },
      get: function () { return invoke('config:get'); },
      set: function (patch) { return invoke('config:set', patch); }
    },
    skills: {
      list: function () { return invoke('skills:list'); },
      get: function (id) { return invoke('skills:get', id); },
      import: function () { return invoke('skills:import'); },
      remove: function (id) { return invoke('skills:remove', id); },
      setEnabled: function (id, on0) { return invoke('skills:set-enabled', id, on0); },
      setRoles: function (id, roles) { return invoke('skills:set-roles', id, roles); },
      onChanged: on('skills:changed')
    },
    profile: {
      get: function () { return invoke('profile:get'); },
      setAvatar: function (spec) { return invoke('profile:set-avatar', spec); },
      setAvatarImage: function (uri) { return invoke('profile:set-avatar-image', uri); }
    },
    memory: {
      list: function (root) { return invoke('memory:list', root); },
      write: function (content, id, root) { return invoke('memory:write', content, id, root); },
      remove: function (id, root) { return invoke('memory:delete', id, root); },
      clear: function (root) { return invoke('memory:clear', root); }
    },
    personas: {
      list: function () { return invoke('personas:list'); },
      get: function (id) { return invoke('personas:get', id); },
      upsert: function (input) { return invoke('personas:upsert', input); },
      remove: function (id) { return invoke('personas:remove', id); },
      setEnabled: function (id, on0) { return invoke('personas:set-enabled', id, on0); },
      reorder: function (ids) { return invoke('personas:reorder', ids); },
      setAvatarImage: function (id, uri) { return invoke('personas:set-avatar-image', id, uri); },
      clearAvatarImage: function (id) { return invoke('personas:clear-avatar-image', id); }
    },
    mcp: {
      list: function () { return invoke('mcp:list'); },
      get: function (id) { return invoke('mcp:get', id); },
      upsert: function (input) { return invoke('mcp:upsert', input); },
      remove: function (id) { return invoke('mcp:remove', id); },
      setEnabled: function (id, on0) { return invoke('mcp:set-enabled', id, on0); },
      setRoles: function (id, roles) { return invoke('mcp:set-roles', id, roles); },
      retry: function (id) { return invoke('mcp:retry', id); },
      setSecret: function (id, field, value) { return invoke('mcp:set-secret', id, field, value); },
      hasSecret: function (id, field) { return invoke('mcp:has-secret', id, field); },
      onStatus: on('mcp:status')
    },
    secrets: {
      set: function (pid, key) { return invoke('secrets:set', pid, key); },
      has: function (pid) { return invoke('secrets:has', pid); },
      delete: function (pid) { return invoke('secrets:delete', pid); },
      list: function () { return invoke('secrets:list'); },
      available: function () { return invoke('secrets:available'); }
    },
    provider: {
      listModels: function (cfg) { return invoke('provider:list-models', cfg); }
    },
    chat: {
      send: function (req) { return invoke('chat:send', req); },
      insert: function (req) { return invoke('chat:insert', req); },
      withdrawInserts: function (sid) { return invoke('chat:withdraw-inserts', sid); },
      compact: function (req) { return invoke('chat:compact', req); },
      createSession: function (req) { return invoke('chat:create-session', req); },
      setModel: function (req) { return invoke('chat:set-model', req); },
      setEffort: function (req) { return invoke('chat:set-effort', req); },
      setFocus: function (req) { return invoke('chat:set-focus', req); },
      renameSession: function (req) { return invoke('chat:rename-session', req); },
      setArchived: function (req) { return invoke('chat:set-archived', req); },
      abort: function (tid) { return invoke('chat:abort', tid); },
      stopSubagent: function (sid, tuid) { return invoke('chat:stop-subagent', sid, tuid); },
      reset: function (sid, root) { return invoke('chat:reset', sid, root); },
      listSessions: function (root) { return invoke('chat:list-sessions', root); },
      loadSession: function (sid, root) { return invoke('chat:load-session', sid, root); },
      attachmentImage: function (sid, ref, full) { return invoke('chat:attachment-image', sid, ref, full); },
      attachSession: function (sid) { return invoke('chat:attach-session', sid); },
      deleteSession: function (sid, root) { return invoke('chat:delete-session', sid, root); },
      removeMember: function (sid, mid) { return invoke('chat:remove-member', sid, mid); },
      deleteTurns: function (sid, root, turns) { return invoke('chat:delete-turns', sid, root, turns); },
      todos: function (sid) { return invoke('chat:todos', sid); },
      cancelTodoList: function (sid) { return invoke('chat:todo-cancel', sid); },
      rewindList: function (sid) { return invoke('chat:rewind-list', sid); },
      rewindPreview: function (sid, turn) { return invoke('chat:rewind-preview', sid, turn); },
      rewindApply: function (req) { return invoke('chat:rewind-apply', req); },
      rewindUndo: function (sid) { return invoke('chat:rewind-undo', sid); },
      resolveProposal: function (sid, tuid, status) { return invoke('chat:resolve-proposal', sid, tuid, status); },
      resolveAutotask: function (sid, tuid, action, input) { return invoke('chat:resolve-autotask', sid, tuid, action, input); },
      respondAsk: function (p) { return invoke('chat:ask-response', p); },
      respondPlan: function (p) { return invoke('chat:plan-response', p); },
      respondMount: function (p) { return invoke('chat:mount-response', p); },
      onEvent: on('chat:event'),
      onSessionsChanged: on('chat:sessions-changed')
    },
    terminal: {
      listShells: function () { return invoke('terminal:list-shells'); },
      create: function (opts) { return invoke('terminal:create', opts); },
      write: function (id, data) { invoke('terminal:input', id, data); },
      resize: function (id, cols, rows) { invoke('terminal:resize', id, cols, rows); },
      dispose: function (id) { invoke('terminal:dispose', id); },
      onData: on('terminal:data'),
      onExit: on('terminal:exit')
    },
    git: {
      available: function () { return invoke('git:available'); },
      status: function (dir) { return invoke('git:status', dir); },
      diff: function (dir, path, staged) { return invoke('git:diff', dir, path, staged); },
      stage: function (dir, paths) { return invoke('git:stage', dir, paths); },
      unstage: function (dir, paths) { return invoke('git:unstage', dir, paths); },
      discard: function (dir, tracked, untracked) { return invoke('git:discard', dir, tracked, untracked); },
      commit: function (dir, message) { return invoke('git:commit', dir, message); },
      setConfig: function (dir, name, email, global) { return invoke('git:set-config', dir, name, email, global); },
      branches: function (dir) { return invoke('git:branches', dir); },
      checkout: function (dir, ref) { return invoke('git:checkout', dir, ref); },
      createBranch: function (dir, name, checkout) { return invoke('git:create-branch', dir, name, checkout); },
      checkoutRemote: function (dir, ref) { return invoke('git:checkout-remote', dir, ref); },
      merge: function (dir, ref) { return invoke('git:merge', dir, ref); },
      mergeAbort: function (dir) { return invoke('git:merge-abort', dir); },
      deleteBranch: function (dir, name, force) { return invoke('git:delete-branch', dir, name, force); },
      renameBranch: function (dir, oldName, newName) { return invoke('git:rename-branch', dir, oldName, newName); },
      deleteRemoteBranch: function (dir, remote, branch) { return invoke('git:delete-remote-branch', dir, remote, branch); },
      log: function (dir, depth) { return invoke('git:log', dir, depth); },
      init: function (dir) { return invoke('git:init', dir); },
      fetch: function (dir) { return invoke('git:fetch', dir); },
      pull: function (dir) { return invoke('git:pull', dir); },
      push: function (dir, up) { return invoke('git:push', dir, up); },
      generateCommitMessage: function (dir, model, locale, reqId) { return invoke('git:generate-commit-message', dir, model, locale, reqId); },
      cancelCommitMessage: function (id) { return invoke('git:cancel-commit-message', id); },
      onCommitMessageDelta: on('git:commit-gen-delta')
    },
    tasks: {
      list: function () { return invoke('tasks:list'); },
      get: function (id) { return invoke('tasks:get', id); },
      create: function (input) { return invoke('tasks:create', input); },
      update: function (input) { return invoke('tasks:update', input); },
      remove: function (id) { return invoke('tasks:delete', id); },
      setStatus: function (id, status) { return invoke('tasks:set-status', id, status); },
      runNow: function (id) { return invoke('tasks:run-now', id); },
      preview: function (schedule, locale, allowPast) { return invoke('tasks:preview', schedule, locale, allowPast); },
      onChanged: on('tasks:changed'),
      onNavigate: on('tasks:navigate')
    },
    clipboard: {
      readText: function () { return invoke('clipboard:read-text'); },
      writeText: function (text) { return invoke('clipboard:write-text', text); }
    },
    deliverables: {
      inspect: function (sid, tuid) { return invoke('deliverables:inspect', sid, tuid); },
      thumbnail: function (sid, tuid, index) { return invoke('deliverables:thumbnail', sid, tuid, index); },
      open: function (sid, tuid, index) { return invoke('deliverables:open', sid, tuid, index); },
      reveal: function (sid, tuid, index) { return invoke('deliverables:reveal', sid, tuid, index); }
    },
    browser: {
      getState: function () { return invoke('browser:state'); },
      ready: function () { return invoke('browser:ready'); },
      onState: on('browser:state'),
      open: function (opts) { return invoke('browser:open', opts); },
      dock: function () { return invoke('browser:dock'); },
      closeSession: function (sid) { return invoke('browser:close-session', sid); },
      setPreviewPinned: function (tab) { return invoke('browser:preview-pinned', tab); },
      liveStart: function (tab) { return invoke('browser:live-start', tab); },
      liveStop: function () { return invoke('browser:live-stop'); },
      onLiveFrame: on('browser:live-frame'),
      pin: function (on0) { return invoke('browser:pin', on0); },
      activate: function (tab) { return invoke('browser:activate', tab); },
      closeTab: function (tab) { return invoke('browser:close-tab', tab); },
      nav: function (tab, what) { return invoke('browser:nav', tab, what); },
      menu: function (tab, labels, at) { return invoke('browser:menu', tab, labels, at); },
      thumbnail: function (tab) { return invoke('browser:thumbnail', tab); },
      handoff: function (sid, answer) { return invoke('browser:handoff', sid, answer); },
      stop: function (sid) { return invoke('browser:stop', sid); }
    },
    update: {
      getState: function () { return invoke('update:get-state'); },
      check: function () { return invoke('update:check'); },
      download: function () { return invoke('update:download'); },
      install: function () { return invoke('update:install'); },
      onState: on('update:state')
    },
    remote: {
      getState: function () { return invoke('remote:get-state'); },
      scanStart: function (platform, opts) { return invoke('remote:scan-start', platform, opts); },
      scanCancel: function (id) { return invoke('remote:scan-cancel', id); },
      setEnabled: function (id, on0) { return invoke('remote:set-enabled', id, on0); },
      setReplyMode: function (id, mode) { return invoke('remote:set-reply-mode', id, mode); },
      setScope: function (id, scope) { return invoke('remote:set-scope', id, scope); },
      deleteBot: function (id) { return invoke('remote:delete-bot', id); },
      pairCode: function (id) { return invoke('remote:pair-code', id); },
      pairCancel: function (id) { return invoke('remote:pair-cancel', id); },
      removeUser: function (id, uid) { return invoke('remote:remove-user', id, uid); },
      onChanged: on('remote:changed'),
      onScan: on('remote:scan')
    }
  };
})();
