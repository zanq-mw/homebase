(function () {
  'use strict';

  const section = document.querySelector('.comments-section');
  if (!section) return;

  const PAGE_TYPE = section.dataset.pageType;
  const PAGE_ID   = parseInt(section.dataset.pageId, 10);
  const API_BASE  = '/api/comments';
  const LIKE_KEY  = 'hb_liked_comments';

  // Session keys (sessionStorage — cleared when tab closes)
  const SESSION_ID_KEY   = 'hb_session_id';
  const SESSION_NAME_KEY = 'hb_session_name';
  const MY_COMMENTS_KEY  = 'hb_my_comments';

  let currentSort = 'newest';

  // Client-side rate limit: max 5 posts per 60s
  const postTimestamps = [];
  const MAX_PER_MIN    = 5;

  // DOM refs
  const listEl      = section.querySelector('.comments-list');
  const identityEl  = section.querySelector('.comments-identity');
  const nameInput   = section.querySelector('.comments-name-input');
  const bodyInput   = section.querySelector('.comments-body-input');
  const charCount   = section.querySelector('.comments-char-count');
  const submitBtn   = section.querySelector('.comments-submit-btn');
  const errorEl     = section.querySelector('.comments-error');
  const sortBtns    = section.querySelectorAll('.comments-sort-btn');

  // -------------------------------------------------------------------------
  // Liked set (localStorage — persists across sessions)
  // -------------------------------------------------------------------------
  function getLiked() {
    try { return new Set(JSON.parse(localStorage.getItem(LIKE_KEY)) || []); }
    catch { return new Set(); }
  }
  function addLiked(id) {
    const s = getLiked(); s.add(id);
    localStorage.setItem(LIKE_KEY, JSON.stringify([...s]));
  }
  function removeLiked(id) {
    const s = getLiked(); s.delete(id);
    localStorage.setItem(LIKE_KEY, JSON.stringify([...s]));
  }

  // -------------------------------------------------------------------------
  // Session identity (sessionStorage — cleared when tab closes)
  // -------------------------------------------------------------------------
  function getSessionId() {
    let id = sessionStorage.getItem(SESSION_ID_KEY);
    if (!id) {
      id = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
      sessionStorage.setItem(SESSION_ID_KEY, id);
    }
    return id;
  }
  function getSessionName() { return sessionStorage.getItem(SESSION_NAME_KEY); }
  function setSessionName(n) { sessionStorage.setItem(SESSION_NAME_KEY, n); }
  function clearSessionName() { sessionStorage.removeItem(SESSION_NAME_KEY); }

  // Own comments this session — used to show delete button
  function getMyComments() {
    try { return new Set(JSON.parse(sessionStorage.getItem(MY_COMMENTS_KEY)) || []); }
    catch { return new Set(); }
  }
  function addMyComment(id) {
    const s = getMyComments(); s.add(id);
    sessionStorage.setItem(MY_COMMENTS_KEY, JSON.stringify([...s]));
  }

  // -------------------------------------------------------------------------
  // Avatar color — deterministic from name
  // -------------------------------------------------------------------------
  const AVATAR_COLORS = ['#3d7ab5','#e05c4a','#45b35a','#d4881a','#8e5bbf','#1aabab'];
  function avatarColor(name) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
    return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
  }

  // -------------------------------------------------------------------------
  // Identity chip — shows "Commenting as [name]" once name is set
  // -------------------------------------------------------------------------
  function renderIdentity() {
    const name = getSessionName();
    if (name) {
      nameInput.style.display = 'none';
      identityEl.innerHTML = '';

      const av = document.createElement('div');
      av.className = 'comments-identity-avatar';
      av.textContent = name[0].toUpperCase();
      av.style.background = avatarColor(name);

      const txt = document.createElement('span');
      txt.className = 'comments-identity-name';
      txt.textContent = 'Commenting as ' + name;

      const changeBtn = document.createElement('button');
      changeBtn.className = 'comments-identity-change';
      changeBtn.textContent = 'change';
      changeBtn.addEventListener('click', function () {
        clearSessionName();
        nameInput.value = '';
        nameInput.style.display = '';
        identityEl.style.display = 'none';
        identityEl.innerHTML = '';
      });

      identityEl.append(av, txt, changeBtn);
      identityEl.style.display = 'flex';
    } else {
      nameInput.style.display = '';
      identityEl.style.display = 'none';
      identityEl.innerHTML = '';
    }
  }

  // -------------------------------------------------------------------------
  // Timestamps — ET, absolute after 3h
  // -------------------------------------------------------------------------
  function formatTimestamp(iso) {
    const date = new Date(iso);
    const now  = new Date();
    const diffMs = now - date;
    const diffH  = diffMs / 3600000;

    const timePart = date.toLocaleTimeString('en-US', {
      hour: 'numeric', minute: '2-digit',
      timeZone: 'America/New_York', hour12: true,
    }) + ' ET';

    const fmt = { timeZone: 'America/New_York', year: 'numeric', month: 'numeric', day: 'numeric' };
    const commentDay   = new Intl.DateTimeFormat('en-US', fmt).format(date);
    const todayDay     = new Intl.DateTimeFormat('en-US', fmt).format(now);
    const yesterdayDay = new Intl.DateTimeFormat('en-US', fmt).format(new Date(now - 86400000));

    if (commentDay === todayDay) {
      if (diffH < 3) {
        if (diffMs < 60000) return 'just now';
        if (diffMs < 3600000) return Math.floor(diffMs / 60000) + ' min ago';
        return Math.floor(diffH) + ' hr ago';
      }
      return 'Today at ' + timePart;
    }
    if (commentDay === yesterdayDay) return 'Yesterday at ' + timePart;

    const sameYear = date.toLocaleDateString('en-US', { timeZone: 'America/New_York', year: 'numeric' })
                   === now.toLocaleDateString('en-US', { timeZone: 'America/New_York', year: 'numeric' });
    const monthDay = date.toLocaleDateString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric' });
    if (sameYear) return monthDay + ' at ' + timePart;
    return date.toLocaleDateString('en-US', {
      timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric',
    }) + ' at ' + timePart;
  }

  function refreshTimestamps() {
    section.querySelectorAll('[data-created-at]').forEach(function (el) {
      el.textContent = formatTimestamp(el.dataset.createdAt);
    });
  }
  setInterval(refreshTimestamps, 60000);

  // -------------------------------------------------------------------------
  // Render one comment
  // -------------------------------------------------------------------------
  function renderComment(c) {
    const liked   = getLiked().has(c.id);
    const isMine  = getMyComments().has(c.id);
    const initial = (c.name || 'A')[0].toUpperCase();

    const item = document.createElement('div');
    item.className = 'comment-item';
    item.dataset.commentId = c.id;

    // Avatar
    const avatar = document.createElement('div');
    avatar.className = 'comment-avatar';
    avatar.textContent = initial;
    avatar.style.background = avatarColor(c.name || 'A');

    // Main content
    const main = document.createElement('div');
    main.className = 'comment-main';

    const nameEl = document.createElement('span');
    nameEl.className = 'comment-name';
    nameEl.textContent = c.name;

    const textEl = document.createElement('span');
    textEl.className = 'comment-text';
    textEl.textContent = ' ' + c.body;

    const bodyLine = document.createElement('div');
    bodyLine.className = 'comment-body-line';
    bodyLine.append(nameEl, textEl);

    const timeRow = document.createElement('div');
    timeRow.className = 'comment-time-row';

    const timeEl = document.createElement('span');
    timeEl.className = 'comment-time';
    timeEl.dataset.createdAt = c.created_at;
    timeEl.textContent = formatTimestamp(c.created_at);
    timeRow.appendChild(timeEl);

    if (isMine) {
      const sep = document.createElement('span');
      sep.className = 'comment-time-sep';
      sep.textContent = '·';

      const delBtn = document.createElement('button');
      delBtn.className = 'comment-delete-btn';
      delBtn.textContent = 'delete';
      delBtn.addEventListener('click', function () { handleDelete(c.id, item); });

      timeRow.append(sep, delBtn);
    }

    main.append(bodyLine, timeRow);

    // Like column (right)
    const likeWrap = document.createElement('div');
    likeWrap.className = 'comment-like-wrap';

    const likeBtn = document.createElement('button');
    likeBtn.className = 'comment-like-btn' + (liked ? ' liked' : '');
    likeBtn.innerHTML = '&#9829;';
    likeBtn.addEventListener('click', function () { handleLike(c.id, likeBtn, likeCountEl); });

    const likeCountEl = document.createElement('span');
    likeCountEl.className = 'comment-like-count';
    likeCountEl.textContent = c.likes > 0 ? c.likes : '';

    likeWrap.append(likeBtn, likeCountEl);
    item.append(avatar, main, likeWrap);
    return item;
  }

  // -------------------------------------------------------------------------
  // Load comments
  // -------------------------------------------------------------------------
  function loadComments() {
    listEl.innerHTML = '<div class="comments-loading">Loading…</div>';
    fetch(API_BASE + '?page_type=' + PAGE_TYPE + '&page_id=' + PAGE_ID + '&sort=' + currentSort)
      .then(function (r) { return r.json(); })
      .then(function (comments) {
        listEl.innerHTML = '';
        if (!comments.length) {
          const empty = document.createElement('div');
          empty.className = 'comments-empty';
          empty.textContent = 'No comments yet. Be the first!';
          listEl.appendChild(empty);
          return;
        }
        comments.forEach(function (c) { listEl.appendChild(renderComment(c)); });
      })
      .catch(function () {
        listEl.innerHTML = '<div class="comments-loading">Could not load comments.</div>';
      });
  }

  // -------------------------------------------------------------------------
  // Sort toggle
  // -------------------------------------------------------------------------
  sortBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      sortBtns.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      currentSort = btn.dataset.sort;
      loadComments();
    });
  });

  // -------------------------------------------------------------------------
  // Char counter
  // -------------------------------------------------------------------------
  bodyInput.addEventListener('input', function () {
    const len = bodyInput.value.length;
    charCount.textContent = len + ' / 500';
    charCount.classList.toggle('over-limit', len > 500);
  });

  // -------------------------------------------------------------------------
  // Client-side rate limit (5 per 60s)
  // -------------------------------------------------------------------------
  function clientRateLimitOk() {
    const now = Date.now();
    while (postTimestamps.length && now - postTimestamps[0] > 60000) postTimestamps.shift();
    return postTimestamps.length < MAX_PER_MIN;
  }

  // -------------------------------------------------------------------------
  // Submit
  // -------------------------------------------------------------------------
  submitBtn.addEventListener('click', function () {
    const body = bodyInput.value.trim();
    if (body.length < 3)   { showError('Comment is too short (minimum 3 characters).'); return; }
    if (body.length > 500) { showError('Comment is too long (maximum 500 characters).'); return; }

    if (!clientRateLimitOk()) {
      showError('Too many comments — please wait 30 seconds before posting again.', 30000);
      return;
    }

    hideError();
    submitBtn.disabled = true;

    // Use session name if already set, otherwise use what they typed
    const nameToSend = getSessionName() || nameInput.value.trim();

    fetch(API_BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        page_type:     PAGE_TYPE,
        page_id:       PAGE_ID,
        name:          nameToSend,
        body:          body,
        session_token: getSessionId(),
      }),
    })
    .then(function (r) {
      return r.json().then(function (data) { return { ok: r.ok, status: r.status, data: data }; });
    })
    .then(function (res) {
      if (!res.ok) {
        submitBtn.disabled = false;
        showError(res.data.error || 'Could not post comment.');
        return;
      }
      submitBtn.disabled = false;
      postTimestamps.push(Date.now());

      // Lock in session name (may be server-assigned anon name)
      if (!getSessionName()) {
        setSessionName(res.data.name);
        renderIdentity();
      }

      // Track this comment as mine so delete button shows
      addMyComment(res.data.id);

      bodyInput.value = '';
      charCount.textContent = '0 / 500';
      charCount.classList.remove('over-limit');

      if (currentSort === 'newest') {
        const empty = listEl.querySelector('.comments-empty');
        if (empty) empty.remove();
        listEl.insertBefore(renderComment(res.data), listEl.firstChild);
      } else {
        loadComments();
      }
    })
    .catch(function () {
      submitBtn.disabled = false;
      showError('Network error. Please try again.');
    });
  });

  // -------------------------------------------------------------------------
  // Like / Unlike
  // -------------------------------------------------------------------------
  function handleLike(id, btn, countEl) {
    const isLiked = btn.classList.contains('liked');
    const endpoint = isLiked ? '/unlike' : '/like';
    btn.disabled = true;
    fetch(API_BASE + '/' + id + endpoint, { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        btn.disabled = false;
        if (isLiked) {
          btn.classList.remove('liked');
          removeLiked(id);
        } else {
          btn.classList.add('liked');
          addLiked(id);
        }
        countEl.textContent = data.likes > 0 ? data.likes : '';
      })
      .catch(function () { btn.disabled = false; });
  }

  // -------------------------------------------------------------------------
  // Delete (own comments only)
  // -------------------------------------------------------------------------
  function handleDelete(id, itemEl) {
    fetch(API_BASE + '/' + id, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_token: getSessionId() }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.ok) {
        itemEl.remove();
        if (!listEl.querySelector('.comment-item')) {
          const empty = document.createElement('div');
          empty.className = 'comments-empty';
          empty.textContent = 'No comments yet. Be the first!';
          listEl.appendChild(empty);
        }
      }
    });
  }

  // -------------------------------------------------------------------------
  // Error helpers
  // -------------------------------------------------------------------------
  let _rateLockTimer = null;

  function showError(msg, lockMs) {
    if (_rateLockTimer) { clearTimeout(_rateLockTimer); _rateLockTimer = null; }
    errorEl.innerHTML = '';
    const text = document.createElement('span');
    text.textContent = msg;
    const closeBtn = document.createElement('button');
    closeBtn.className = 'comments-error-close';
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', function () {
      hideError();
      submitBtn.disabled = false;
      if (_rateLockTimer) { clearTimeout(_rateLockTimer); _rateLockTimer = null; }
    });
    errorEl.append(text, closeBtn);
    errorEl.style.display = 'flex';
    if (lockMs) {
      submitBtn.disabled = true;
      _rateLockTimer = setTimeout(function () {
        hideError();
        submitBtn.disabled = false;
        _rateLockTimer = null;
      }, lockMs);
    }
  }

  function hideError() {
    if (_rateLockTimer) { clearTimeout(_rateLockTimer); _rateLockTimer = null; }
    errorEl.style.display = 'none';
    errorEl.innerHTML = '';
  }

  // -------------------------------------------------------------------------
  // Init
  // -------------------------------------------------------------------------
  renderIdentity();
  loadComments();
})();
