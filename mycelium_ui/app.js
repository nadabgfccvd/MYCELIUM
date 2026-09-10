const els = {
  mode: document.getElementById('mode'),
  rounds: document.getElementById('rounds'),
  minutes: document.getElementById('minutes'),
  hours: document.getElementById('hours'),
  guardWorkers: document.getElementById('guardWorkers'),
  ramMb: document.getElementById('ramMb'),
  startBtn: document.getElementById('startBtn'),
  repeatLastBtn: document.getElementById('repeatLastBtn'),
  stopBtn: document.getElementById('stopBtn'),
  wakeBtn: document.getElementById('wakeBtn'),
  refreshHistoryBtn: document.getElementById('refreshHistoryBtn'),
  applyRecommendedBtn: document.getElementById('applyRecommendedBtn'),
  openHelpPresetBtn: document.getElementById('openHelpPresetBtn'),
  terminal: document.getElementById('terminal'),
  commandInput: document.getElementById('commandInput'),
  sendCmdBtn: document.getElementById('sendCmdBtn'),
  runBadge: document.getElementById('runBadge'),
  backgroundBadge: document.getElementById('backgroundBadge'),
  freshnessBadge: document.getElementById('freshnessBadge'),
  statusMeta: document.getElementById('statusMeta'),
  statusSubMeta: document.getElementById('statusSubMeta'),
  modeHint: document.getElementById('modeHint'),
  nextRunSummary: document.getElementById('nextRunSummary'),
  wizardSummary: document.getElementById('wizardSummary'),
  onboardingBadge: document.getElementById('onboardingBadge'),
  onboardingTitle: document.getElementById('onboardingTitle'),
  onboardingText: document.getElementById('onboardingText'),
  onboardingRecommendation: document.getElementById('onboardingRecommendation'),
  metricRound: document.getElementById('metricRound'),
  metricScore: document.getElementById('metricScore'),
  metricExact: document.getElementById('metricExact'),
  metricCapability: document.getElementById('metricCapability'),
  metricSolved: document.getElementById('metricSolved'),
  metricClimate: document.getElementById('metricClimate'),
  metricMacros: document.getElementById('metricMacros'),
  metricStaging: document.getElementById('metricStaging'),
  metricFrontier: document.getElementById('metricFrontier'),
  metricFrontierDifficulty: document.getElementById('metricFrontierDifficulty'),
  metricNiches: document.getElementById('metricNiches'),
  metricEntropy: document.getElementById('metricEntropy'),
  metricTransfer: document.getElementById('metricTransfer'),
  metricFrontierProgress: document.getElementById('metricFrontierProgress'),
  metricHistoryCount: document.getElementById('metricHistoryCount'),
  frontierFrontierCount: document.getElementById('frontierFrontierCount'),
  frontierDominatedCount: document.getElementById('frontierDominatedCount'),
  frontierImpossibleCount: document.getElementById('frontierImpossibleCount'),
  bestProgram: document.getElementById('bestProgram'),
  challengeOracles: document.getElementById('challengeOracles'),
  projectTree: document.getElementById('projectTree'),
  profileSummary: document.getElementById('profileSummary'),
  helpBox: document.getElementById('helpBox'),
  reportPath: document.getElementById('reportPath'),
  reportPreview: document.getElementById('reportPreview'),
  openReportBtn: document.getElementById('openReportBtn'),
  historyList: document.getElementById('historyList'),
  alertFeed: document.getElementById('alertFeed'),
  toastStack: document.getElementById('toastStack'),
  tooltipBubble: document.getElementById('tooltipBubble'),
  terminalCard: document.getElementById('terminalCard'),
  terminalHint: document.getElementById('terminalHint'),
  opMode: document.getElementById('opMode'),
  opPhase: document.getElementById('opPhase'),
  opPid: document.getElementById('opPid'),
  opReturnCode: document.getElementById('opReturnCode'),
  opCycle: document.getElementById('opCycle'),
  opSessionRounds: document.getElementById('opSessionRounds'),
  opDaemonState: document.getElementById('opDaemonState'),
  opKill: document.getElementById('opKill'),
  opStateDir: document.getElementById('opStateDir'),
  opStatePath: document.getElementById('opStatePath'),
};

const modeHints = {
  run: 'Evolução normal para gerar progresso rápido, simples e direto.',
  'self-improve': 'Auto melhoria com guarda anti-regressão: compara candidatos antes de aplicar mudanças.',
  focused: 'Calibração focada: mira diversidade, fronteira, macro staging e recombinação com janela longa.',
};

const quickPresets = {
  explore: {
    title: 'Explorar',
    summary: 'Run normal • 120 rounds • 2 GB de RAM',
    values: { mode: 'run', rounds: 120, minutes: 25, hours: 8, guardWorkers: 2, ramMb: '2048' },
  },
  improve: {
    title: 'Auto melhorar',
    summary: 'Auto melhoria • 25 min • 3 GB • 4 workers',
    values: { mode: 'self-improve', rounds: 100, minutes: 25, hours: 8, guardWorkers: 4, ramMb: '3072' },
  },
  deep: {
    title: 'Calibrar a fundo',
    summary: 'Calibração focada • 8 h • 4 GB • 4 workers',
    values: { mode: 'focused', rounds: 100, minutes: 25, hours: 8, guardWorkers: 4, ramMb: '4096' },
  },
};

let activePresetKey = null;
let latestHistory = [];
let onboardingModel = { presetKey: 'explore', title: 'Sugestão padrão: Explorar', text: '', recommendation: '' };
let lastInteractionAt = Date.now();
let backgroundMode = false;
let lastReportPath = null;
let lastPreviewLoadedPath = null;
let lastStatusServerTime = null;
let lastPollCompletedAt = null;
let previousEventState = null;
let alertFeedItems = [];
let seenAlertKeys = new Set();

function touchInteraction() {
  lastInteractionAt = Date.now();
  if (backgroundMode) {
    backgroundMode = false;
    renderBackgroundMode();
    pollStatus();
  }
}

function setText(el, value) {
  if (!el) return;
  el.textContent = value ?? '-';
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function encodePayload(payload) {
  return encodeURIComponent(JSON.stringify(payload || {}));
}

function decodePayload(text) {
  try {
    return JSON.parse(decodeURIComponent(text || ''));
  } catch {
    return null;
  }
}

function formatNumber(value, digits = 3) {
  if (value === null || value === undefined || value === '') return '-';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toFixed(digits);
}

function formatInt(value) {
  if (value === null || value === undefined || value === '') return '-';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return String(Math.round(num));
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '-';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return `${(num * 100).toFixed(1)}%`;
}

function formatDuration(seconds) {
  if (!seconds) return '0s';
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m ${sec}s`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

function formatRelativeAge(epochSeconds) {
  if (!epochSeconds) return 'desconhecido';
  const diff = Math.max(0, Math.floor(Date.now() / 1000 - Number(epochSeconds)));
  if (diff < 5) return 'agora mesmo';
  if (diff < 60) return `${diff}s atrás`;
  const minutes = Math.floor(diff / 60);
  if (minutes < 60) return `${minutes} min atrás`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h atrás`;
}

function formatDateTime(epochSeconds) {
  if (!epochSeconds) return '-';
  try {
    return new Date(Number(epochSeconds) * 1000).toLocaleString('pt-BR');
  } catch {
    return '-';
  }
}

function formatCountdown(ms) {
  const remaining = Math.max(0, ms);
  const totalSeconds = Math.ceil(remaining / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function modeLabel(mode) {
  if (mode === 'run') return 'Explorar';
  if (mode === 'self-improve') return 'Auto melhorar';
  if (mode === 'focused') return 'Calibrar a fundo';
  return mode || 'Idle';
}

function historyBadgeClass(status) {
  if (status === 'success' || status === 'stopped_ok') return '';
  if (status === 'running' || status === 'idle') return 'secondary';
  if (status === 'stopping' || status === 'interrupted') return 'warn';
  return 'danger';
}

function renderBackgroundMode() {
  els.backgroundBadge.textContent = backgroundMode ? 'Segundo plano' : 'Foreground';
  els.backgroundBadge.className = 'statusBadge secondary' + (backgroundMode ? ' warn' : '');
  document.body.classList.toggle('background-mode', backgroundMode);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'Falha na API');
  }
  return response.json();
}

function appendTerminal(text) {
  els.terminal.textContent = text || '';
  els.terminal.scrollTop = els.terminal.scrollHeight;
}

async function openReportAtPath(path) {
  if (!path) return;
  const data = await api('/api/file?path=' + encodeURIComponent(path));
  els.reportPreview.textContent = data.content || '';
  lastPreviewLoadedPath = path;
  lastReportPath = path;
  els.reportPath.textContent = path;
}

async function openReport() {
  if (!lastReportPath) return;
  await openReportAtPath(lastReportPath);
}

function applyLaunchPayload(payload, sourceLabel = 'Sessão anterior', notify = true) {
  if (!payload || typeof payload !== 'object') {
    if (notify) pushAlert('warn', 'Não há parâmetros salvos', 'Ainda não encontrei uma sessão anterior com configuração reaproveitável.', `no-payload-${Date.now()}`);
    return false;
  }
  activePresetKey = null;
  els.mode.value = payload.mode || 'run';
  if (payload.rounds !== undefined) els.rounds.value = payload.rounds;
  if (payload.minutes !== undefined) els.minutes.value = payload.minutes;
  if (payload.hours !== undefined) els.hours.value = payload.hours;
  if (payload.guard_workers !== undefined) els.guardWorkers.value = payload.guard_workers;
  if (payload.ram_mb !== undefined && payload.ram_mb !== null && payload.ram_mb !== '') {
    els.ramMb.value = String(payload.ram_mb);
  }
  updateModeVisibility();
  renderWizardState();
  if (notify) {
    pushAlert('info', 'Parâmetros reaplicados', `${sourceLabel} deixou o formulário pronto. Clique em Iniciar para rodar de novo.`, `reuse-${sourceLabel}-${Date.now()}`);
  }
  return true;
}

function updateModeVisibility() {
  const mode = els.mode.value;
  document.querySelectorAll('.modeField').forEach((node) => {
    const modes = String(node.dataset.modes || '').split(',').map((v) => v.trim()).filter(Boolean);
    node.classList.toggle('hidden', modes.length > 0 && !modes.includes(mode));
  });
  els.modeHint.textContent = modeHints[mode] || 'Selecione um modo para ver a explicação.';
  renderNextRunSummary();
}

function renderWizardState() {
  document.querySelectorAll('.wizardCard').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.preset === activePresetKey);
  });
  els.wizardSummary.textContent = activePresetKey
    ? `Preset ativo: ${quickPresets[activePresetKey].summary}. Você ainda pode ajustar os campos manualmente.`
    : 'Nenhum preset ativo. Os campos atuais podem ter vindo de uma sessão anterior ou de edição manual.';
}

function applyPreset(key, notify = true) {
  const preset = quickPresets[key];
  if (!preset) return;
  activePresetKey = key;
  els.mode.value = preset.values.mode;
  els.rounds.value = preset.values.rounds;
  els.minutes.value = preset.values.minutes;
  els.hours.value = preset.values.hours;
  els.guardWorkers.value = preset.values.guardWorkers;
  els.ramMb.value = preset.values.ramMb;
  updateModeVisibility();
  renderWizardState();
  if (notify) {
    pushAlert('info', 'Preset aplicado', `${preset.title} deixou a próxima execução pronta para uso.`, `preset-${key}-${Date.now()}`);
  }
}

function renderNextRunSummary() {
  const mode = els.mode.value;
  const ram = els.ramMb.value === 'auto' ? 'RAM automática' : `${els.ramMb.value} MB de RAM`;
  const workers = Number(els.guardWorkers.value || 4);
  if (mode === 'run') {
    els.nextRunSummary.textContent = `Próxima execução: ${modeLabel(mode)} com ${Number(els.rounds.value || 100)} rounds e ${ram}.`;
    return;
  }
  if (mode === 'self-improve') {
    els.nextRunSummary.textContent = `Próxima execução: ${modeLabel(mode)} por ${Number(els.minutes.value || 25)} minuto(s), ${workers} worker(s) do guarda e ${ram}.`;
    return;
  }
  els.nextRunSummary.textContent = `Próxima execução: ${modeLabel(mode)} por ${Number(els.hours.value || 8)} hora(s), ${workers} worker(s) do guarda e ${ram}.`;
}

function renderFreshness() {
  if (!lastPollCompletedAt || !lastStatusServerTime) {
    els.freshnessBadge.textContent = 'Sem telemetria';
    els.freshnessBadge.className = 'statusBadge secondary';
    return;
  }
  const ageSeconds = Math.max(0, (Date.now() - lastPollCompletedAt) / 1000);
  const state = ageSeconds < 3 ? 'Telemetria fresca' : ageSeconds < 8 ? 'Telemetria recente' : 'Telemetria atrasada';
  els.freshnessBadge.textContent = state;
  els.freshnessBadge.className = 'statusBadge secondary' + (ageSeconds >= 8 ? ' warn' : '');
}

function updateTerminalHint() {
  const inactiveMs = Date.now() - lastInteractionAt;
  if (backgroundMode) {
    els.terminalHint.textContent = 'Modo segundo plano ativo. Clique no console ou no botão para voltar ao foreground.';
    return;
  }
  const remaining = 5 * 60 * 1000 - inactiveMs;
  els.terminalHint.textContent = `Sem interação, a UI entra em segundo plano em ${formatCountdown(remaining)}.`;
}

async function maybeAutoLoadReport() {
  if (!lastReportPath || lastPreviewLoadedPath === lastReportPath) return;
  try {
    await openReport();
  } catch (error) {
    els.reportPreview.textContent = `Falha ao abrir relatório: ${error.message}`;
  }
}

function profileSummaryText(profile) {
  if (!profile || typeof profile !== 'object') return 'Perfil default indisponível.';
  const lines = [
    `famílias: ${profile.family_count}`,
    `organismos por família: ${profile.family_size}`,
    `desafios/round: ${profile.challenges_per_round}`,
    `treino/teste: ${profile.train_cases}/${profile.test_cases}`,
    `probe treino/teste: ${profile.probe_train_cases}/${profile.probe_test_cases}`,
    `checkpoint/state save: ${profile.checkpoint_every}/${profile.state_save_every}`,
    `novelty/macro/transfer: ${profile.novelty_weight} / ${profile.macro_potential_weight} / ${profile.transfer_weight}`,
    `backend persistência: ${profile.persistence_backend}`,
  ];
  return lines.join('\n');
}

function pushAlert(level, title, message, key) {
  if (key && seenAlertKeys.has(key)) return;
  if (key) seenAlertKeys.add(key);
  const item = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    level,
    title,
    message,
    createdAt: Date.now(),
  };
  alertFeedItems.unshift(item);
  alertFeedItems = alertFeedItems.slice(0, 8);
  renderAlertFeed();
  renderToast(item);
}

function renderAlertFeed() {
  if (!alertFeedItems.length) {
    els.alertFeed.innerHTML = '<div class="emptyState">Nenhum alerta recente. Quando algo importante acontecer, ele aparece aqui em linguagem humana.</div>';
    return;
  }
  els.alertFeed.innerHTML = alertFeedItems.map((item) => `
    <article class="alertItem ${escapeHtml(item.level)}">
      <div class="alertHead">
        <div>
          <div class="alertTitle">${escapeHtml(item.title)}</div>
          <div class="alertMeta">${escapeHtml(item.message)}</div>
        </div>
        <span class="alertBadge ${item.level === 'warn' ? 'warn' : item.level === 'danger' ? 'danger' : item.level === 'info' ? 'secondary' : ''}">${escapeHtml(formatRelativeAge(item.createdAt / 1000))}</span>
      </div>
    </article>
  `).join('');
}

function renderToast(item) {
  const node = document.createElement('div');
  node.className = `toast ${item.level}`;
  node.innerHTML = `
    <div class="toastTitle">${escapeHtml(item.title)}</div>
    <div class="toastMeta">${escapeHtml(item.message)}</div>
  `;
  els.toastStack.prepend(node);
  while (els.toastStack.children.length > 4) {
    els.toastStack.removeChild(els.toastStack.lastElementChild);
  }
  setTimeout(() => {
    node.style.opacity = '0';
    setTimeout(() => node.remove(), 250);
  }, 5500);
}

function historyItemHtml(item) {
  const payload = item.launch_payload ? encodePayload(item.launch_payload) : '';
  return `
    <article class="historyItem ${escapeHtml(item.status || 'idle')}">
      <div class="historyHead">
        <div>
          <div class="historyTitle">${escapeHtml(item.mode_label || modeLabel(item.mode))}</div>
          <div class="historyMeta">${escapeHtml(formatDateTime(item.started_at))} • ${escapeHtml(formatDuration(item.elapsed_seconds))}</div>
        </div>
        <span class="historyBadge ${historyBadgeClass(item.status)}">${escapeHtml(item.status_label || 'Sem status')}</span>
      </div>
      <div class="historyMeta">Resultado: ${escapeHtml(item.returncode ?? '-')} • RAM: ${escapeHtml(item.ram_mb ?? 'auto')} MB</div>
      <pre class="historyStateDir">${escapeHtml(item.state_dir || 'Sem state dir registrado')}</pre>
      <div class="historyActions">
        ${item.last_auto_report_path ? `<button class="subtle historyAction" type="button" data-action="open-report" data-path="${escapeHtml(item.last_auto_report_path)}">Abrir relatório</button>` : ''}
        ${item.state_dir ? `<button class="subtle historyAction" type="button" data-action="copy-state-dir" data-path="${escapeHtml(item.state_dir)}">Copiar state dir</button>` : ''}
        ${payload ? `<button class="subtle historyAction" type="button" data-action="repeat-session" data-payload="${payload}">Repetir parâmetros</button>` : ''}
      </div>
    </article>
  `;
}

function renderHistory(history) {
  latestHistory = Array.isArray(history) ? history : [];
  if (!latestHistory.length) {
    els.historyList.innerHTML = '<div class="emptyState">Nenhuma execução recente registrada ainda.</div>';
    return;
  }
  els.historyList.innerHTML = latestHistory.map(historyItemHtml).join('');
}

async function copyToClipboard(text) {
  if (!navigator.clipboard?.writeText) {
    throw new Error('Clipboard não disponível neste navegador.');
  }
  await navigator.clipboard.writeText(text);
}

function computeOnboardingModel(history, session, daemon) {
  const latest = Array.isArray(history) && history.length ? history[0] : null;
  if (session?.running) {
    return {
      presetKey: latest?.mode === 'focused' ? 'deep' : latest?.mode === 'self-improve' ? 'improve' : 'explore',
      title: 'Há uma execução em andamento',
      text: 'O melhor próximo passo é acompanhar a telemetria e deixar o processo terminar com segurança.',
      recommendation: 'Enquanto isso, a recomendação automática fica em espera. Se precisar, você ainda pode abrir ajuda ou pedir parada segura.',
      badge: 'Acompanhando',
      buttonText: 'Aplicar sugestão',
      disabled: true,
    };
  }
  if (!latest) {
    return {
      presetKey: 'explore',
      title: 'Comece por Explorar',
      text: 'Boa opção para uma primeira rodada: é rápida, simples e ajuda a verificar se tudo está saudável.',
      recommendation: 'Recomendação automática: usar o preset Explorar para gerar progresso inicial sem entrar em calibração longa.',
      badge: 'Sugestão pronta',
      buttonText: 'Aplicar Explorar',
      disabled: false,
    };
  }
  if (daemon?.stale || latest.status === 'failed' || latest.status === 'stopped_error') {
    return {
      presetKey: 'explore',
      title: 'Faça uma checagem rápida primeiro',
      text: 'Como a telemetria anterior ficou velha ou houve erro recente, vale começar por uma execução curta e confiável.',
      recommendation: 'Recomendação automática: usar Explorar para validar a saúde do sistema antes de uma rodada mais pesada.',
      badge: 'Checagem sugerida',
      buttonText: 'Aplicar Explorar',
      disabled: false,
    };
  }
  if (latest.mode === 'run' && latest.status === 'success') {
    return {
      presetKey: 'improve',
      title: 'Hora de Auto melhorar',
      text: 'Sua última execução simples terminou bem. Agora faz sentido subir um degrau e deixar o guarda testar melhorias.',
      recommendation: 'Recomendação automática: usar Auto melhorar para tentar ganhos reais com proteção anti-regressão.',
      badge: 'Próximo passo',
      buttonText: 'Aplicar Auto melhorar',
      disabled: false,
    };
  }
  if (latest.mode === 'self-improve' && latest.status === 'success') {
    return {
      presetKey: 'deep',
      title: 'Você já pode calibrar a fundo',
      text: 'A fase de auto melhoria anterior terminou bem. Se quiser buscar ajustes mais profundos, este é o próximo passo natural.',
      recommendation: 'Recomendação automática: usar Calibrar a fundo para uma rodada longa focada em fronteira, diversidade e recombinação.',
      badge: 'Avançar',
      buttonText: 'Aplicar Calibrar a fundo',
      disabled: false,
    };
  }
  return {
    presetKey: latest.mode === 'focused' ? 'deep' : latest.mode === 'self-improve' ? 'improve' : 'explore',
    title: `Você pode repetir ${modeLabel(latest.mode)}`,
    text: 'O histórico recente já mostra um fluxo conhecido. Se preferir algo familiar, reaproveite a última configuração ou siga a sugestão automática.',
    recommendation: `Recomendação automática: continuar com ${modeLabel(latest.mode)} ou reaplicar a última sessão salva.`,
    badge: 'Continuidade',
    buttonText: `Aplicar ${modeLabel(latest.mode)}`,
    disabled: false,
  };
}

function renderOnboarding(model) {
  onboardingModel = model;
  els.onboardingTitle.textContent = model.title;
  els.onboardingText.textContent = model.text;
  els.onboardingRecommendation.textContent = model.recommendation;
  els.onboardingBadge.textContent = model.badge || 'Sugestão pronta';
  els.applyRecommendedBtn.textContent = model.buttonText || 'Aplicar sugestão';
  els.applyRecommendedBtn.disabled = Boolean(model.disabled);
  els.repeatLastBtn.disabled = latestHistory.length === 0;
}

function detectEvents(data) {
  const session = data.session || {};
  const daemon = data.daemon_status || {};
  const lastError = data.last_error || {};
  const reportPath = session.last_auto_report_path || data.latest_auto_report_path || null;
  const errorFingerprint = lastError.error_message || session.last_error || null;
  const current = {
    sessionId: session.session_id || null,
    running: Boolean(session.running),
    returncode: session.returncode,
    reportPath,
    daemonStale: Boolean(daemon.stale),
    errorFingerprint,
    stopRequested: Boolean(session.stop_requested),
  };

  if (!previousEventState) {
    if (current.daemonStale) {
      pushAlert('warn', 'Telemetria antiga detectada', 'O arquivo do daemon parou de ser atualizado. O status pode estar velho e precisa de conferência.', `daemon-stale-${daemon.timestamp || 'none'}`);
    }
    if (current.errorFingerprint) {
      pushAlert('danger', 'Erro persistido detectado', current.errorFingerprint, `error-${current.errorFingerprint}`);
    }
    previousEventState = current;
    return;
  }

  if (current.running && (!previousEventState.running || current.sessionId !== previousEventState.sessionId)) {
    pushAlert('info', 'Execução iniciada', `${modeLabel(session.mode)} começou com ${session.ram_mb || session.pending_ram_mb || 'auto'} MB de RAM.`, `start-${current.sessionId}`);
  }

  if (previousEventState.running && !current.running && current.sessionId === previousEventState.sessionId && session.returncode !== null && session.returncode !== undefined) {
    if (Number(session.returncode) === 0) {
      pushAlert('success', 'Execução finalizada', `${modeLabel(session.mode)} terminou com sucesso em ${formatDuration(session.elapsed_seconds)}.`, `finish-${current.sessionId}-${session.returncode}`);
    } else {
      pushAlert('danger', 'Execução terminou com erro', `${modeLabel(session.mode)} encerrou com código ${session.returncode}.`, `finish-${current.sessionId}-${session.returncode}`);
    }
  }

  if (!previousEventState.daemonStale && current.daemonStale) {
    pushAlert('warn', 'Daemon parece parado', 'A telemetria do daemon ficou antiga. Pode ser que a execução anterior tenha morrido ou parado de atualizar.', `daemon-stale-${daemon.timestamp || Date.now()}`);
  }

  if (current.reportPath && current.reportPath !== previousEventState.reportPath) {
    pushAlert('success', 'Relatório gerado', 'O relatório automático mais recente já está pronto para abrir.', `report-${current.reportPath}`);
  }

  if (current.errorFingerprint && current.errorFingerprint !== previousEventState.errorFingerprint) {
    pushAlert('danger', 'Erro persistido detectado', current.errorFingerprint, `error-${current.errorFingerprint}`);
  }

  if (current.stopRequested && !previousEventState.stopRequested) {
    pushAlert('warn', 'Parada solicitada', 'O MYCELIUM Auto-evolve recebeu um pedido de parada segura e deve encerrar após salvar o progresso.', `stop-request-${current.sessionId}`);
  }

  previousEventState = current;
}

function renderTooltip(text, anchorEl) {
  if (!text || !anchorEl) return;
  els.tooltipBubble.textContent = text;
  els.tooltipBubble.hidden = false;
  const rect = anchorEl.getBoundingClientRect();
  const bubbleRect = els.tooltipBubble.getBoundingClientRect();
  const top = Math.max(12, rect.top - bubbleRect.height - 10);
  const left = Math.min(window.innerWidth - bubbleRect.width - 12, Math.max(12, rect.left + rect.width / 2 - bubbleRect.width / 2));
  els.tooltipBubble.style.top = `${top}px`;
  els.tooltipBubble.style.left = `${left}px`;
}

function hideTooltip() {
  els.tooltipBubble.hidden = true;
}

function attachTooltips() {
  document.querySelectorAll('.infoDot').forEach((btn) => {
    const show = () => renderTooltip(btn.dataset.tooltip, btn);
    btn.addEventListener('mouseenter', show);
    btn.addEventListener('focus', show);
    btn.addEventListener('mouseleave', hideTooltip);
    btn.addEventListener('blur', hideTooltip);
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      if (els.tooltipBubble.hidden) show();
      else hideTooltip();
    });
  });
}

function updateUi(data) {
  const session = data.session || {};
  const runtime = data.runtime || {};
  const daemon = data.daemon_status || {};
  const lastError = data.last_error || {};
  appendTerminal(session.log || 'Terminal pronto. Use /help.');

  if (session.running) {
    els.runBadge.textContent = 'Rodando';
    els.runBadge.className = 'statusBadge';
  } else if (session.returncode !== null && session.returncode !== undefined) {
    els.runBadge.textContent = 'Finalizado';
    els.runBadge.className = 'statusBadge warn';
  } else {
    els.runBadge.textContent = 'Parado';
    els.runBadge.className = 'statusBadge danger';
  }

  const phase = daemon.phase || '-';
  const daemonStale = Boolean(daemon.stale);
  const daemonState = daemon.state ? `${daemon.state}${daemonStale ? ' (stale)' : ''}` : '-';
  const runtimeRounds = Number(runtime.round_index || 0);
  const sessionRounds = Math.max(0, runtimeRounds - Number(session.start_round_index || 0));
  const stateMtime = runtime.state_last_modified;
  const stateAge = formatRelativeAge(stateMtime);
  const startedAge = formatRelativeAge(session.started_at);

  els.statusMeta.textContent = `${modeLabel(session.mode)} • ${formatDuration(session.elapsed_seconds)} • RAM ${session.ram_mb || session.pending_ram_mb || 'auto'} MB • fase ${phase}${daemonStale ? ' (telemetria antiga)' : ''}`;
  const errorText = lastError.error_message || session.last_error || 'nenhum erro persistido';
  const daemonAge = daemon.telemetry_age_seconds ? formatDuration(daemon.telemetry_age_seconds) : 'desconhecida';
  els.statusSubMeta.textContent = `Estado salvo: ${stateAge} • daemon ${daemonState} • idade daemon: ${daemonAge} • iniciado: ${startedAge} • erro: ${errorText}`;

  setText(els.opMode, session.mode_label || modeLabel(session.mode));
  setText(els.opPhase, `${phase}${daemonStale ? ' (stale)' : ''}`);
  setText(els.opPid, session.pid ?? '-');
  setText(els.opReturnCode, session.returncode ?? '-');
  setText(els.opCycle, daemon.cycle_index ?? '-');
  setText(els.opSessionRounds, sessionRounds);
  setText(els.opDaemonState, daemonState);
  setText(els.opKill, runtime.kill_switch_present ? 'Presente' : 'Ausente');
  setText(els.opStateDir, runtime.state_dir || session.state_dir || '-');
  setText(els.opStatePath, runtime.state_path || '-');

  setText(els.metricRound, runtime.round_index ?? '-');
  setText(els.metricScore, formatNumber(runtime.best_score));
  setText(els.metricExact, formatPercent(runtime.best_exact_rate));
  setText(els.metricCapability, formatNumber(runtime.capability_signal));
  setText(els.metricSolved, formatInt(runtime.solved_by_best));
  setText(els.metricClimate, runtime.climate || '-');
  setText(els.bestProgram, runtime.best_program || 'Nenhum programa observado ainda.');

  setText(els.metricMacros, formatInt(runtime.macro_library_count));
  setText(els.metricStaging, formatInt(runtime.macro_staging_count));
  setText(els.metricFrontier, formatInt(runtime.frontier_archive_count));
  setText(els.metricFrontierDifficulty, formatInt(runtime.frontier_difficulty));
  setText(els.metricNiches, formatInt(runtime.active_niches));
  setText(els.metricEntropy, formatNumber(runtime.diversity_entropy));
  setText(els.metricTransfer, formatNumber(runtime.macro_transfer_mean));
  setText(els.metricFrontierProgress, formatNumber(runtime.frontier_learning_progress));
  setText(els.metricHistoryCount, formatInt(runtime.metrics_history_count));

  const frontierCounts = runtime.frontier_status_counts || {};
  setText(els.frontierFrontierCount, formatInt(frontierCounts.frontier));
  setText(els.frontierDominatedCount, formatInt(frontierCounts.dominated));
  setText(els.frontierImpossibleCount, formatInt(frontierCounts.impossible));

  const oracles = Array.isArray(runtime.challenge_oracles) ? runtime.challenge_oracles : [];
  els.challengeOracles.textContent = oracles.length ? oracles.join('\n') : 'Nenhum oráculo ativo visível neste momento.';

  lastReportPath = session.last_auto_report_path || data.latest_auto_report_path || null;
  els.reportPath.textContent = lastReportPath || 'Nenhum relatório automático ainda.';

  renderHistory(data.recent_history || []);
  renderOnboarding(computeOnboardingModel(data.recent_history || [], session, daemon));
  detectEvents(data);

  lastStatusServerTime = data.server_time || null;
  lastPollCompletedAt = Date.now();
  renderFreshness();
  maybeAutoLoadReport();
}

async function pollStatus() {
  try {
    const data = await api('/api/status');
    updateUi(data);
  } catch (error) {
    els.statusMeta.textContent = 'Erro ao atualizar interface: ' + error.message;
    els.statusSubMeta.textContent = 'A telemetria não pôde ser atualizada agora.';
  }
}

async function loadBootstrap() {
  try {
    const data = await api('/api/bootstrap');
    els.projectTree.textContent = data.project_tree || '';
    els.helpBox.textContent = data.help || '';
    els.profileSummary.textContent = profileSummaryText(data.default_profile || {});
    renderHistory(data.recent_history || []);
    renderOnboarding(computeOnboardingModel(data.recent_history || [], {}, {}));
  } catch (error) {
    els.projectTree.textContent = 'Falha ao carregar árvore do projeto: ' + error.message;
    els.helpBox.textContent = 'Falha ao carregar ajuda: ' + error.message;
    els.profileSummary.textContent = 'Falha ao carregar perfil default: ' + error.message;
  }
}

function repeatLastSession() {
  const latest = latestHistory[0];
  if (!latest?.launch_payload) {
    pushAlert('warn', 'Nada para repetir ainda', 'Ainda não há uma sessão anterior com parâmetros salvos para reaplicar.', 'repeat-empty');
    return;
  }
  applyLaunchPayload(latest.launch_payload, 'A última sessão', true);
}

async function startRun() {
  touchInteraction();
  const payload = {
    mode: els.mode.value,
    rounds: Number(els.rounds.value || 100),
    minutes: Number(els.minutes.value || 25),
    hours: Number(els.hours.value || 8),
    guard_workers: Number(els.guardWorkers.value || 4),
    ram_mb: els.ramMb.value,
  };
  try {
    await api('/api/start', { method: 'POST', body: JSON.stringify(payload) });
    await pollStatus();
  } catch (error) {
    appendTerminal((els.terminal.textContent || '') + `\n[UI] Falha ao iniciar: ${error.message}`);
    pushAlert('danger', 'Não foi possível iniciar', error.message, `start-error-${Date.now()}`);
  }
}

async function stopRun() {
  touchInteraction();
  try {
    await api('/api/stop', { method: 'POST', body: '{}' });
    await pollStatus();
  } catch (error) {
    appendTerminal((els.terminal.textContent || '') + `\n[UI] Falha ao parar: ${error.message}`);
    pushAlert('danger', 'Falha ao pedir parada', error.message, `stop-error-${Date.now()}`);
  }
}

async function sendCommand(cmd) {
  const command = cmd || els.commandInput.value;
  if (!command.trim()) return;
  touchInteraction();
  try {
    const data = await api('/api/command', { method: 'POST', body: JSON.stringify({ command }) });
    appendTerminal((els.terminal.textContent || '') + `\n> ${command}\n${data.output || ''}`);
    els.commandInput.value = '';
    await pollStatus();
  } catch (error) {
    appendTerminal((els.terminal.textContent || '') + `\n[UI] Falha ao enviar comando: ${error.message}`);
    pushAlert('danger', 'Comando não enviado', error.message, `command-error-${Date.now()}`);
  }
}

setInterval(() => {
  const inactiveMs = Date.now() - lastInteractionAt;
  const shouldBackground = inactiveMs >= 5 * 60 * 1000;
  if (shouldBackground !== backgroundMode) {
    backgroundMode = shouldBackground;
    renderBackgroundMode();
  }
  updateTerminalHint();
  renderFreshness();
}, 1000);

setInterval(() => {
  if (!backgroundMode) {
    pollStatus();
  }
}, 1500);

setInterval(() => {
  if (backgroundMode) {
    pollStatus();
  }
}, 10000);

els.startBtn.addEventListener('click', startRun);
els.repeatLastBtn.addEventListener('click', repeatLastSession);
els.stopBtn.addEventListener('click', stopRun);
els.sendCmdBtn.addEventListener('click', () => sendCommand());
els.openReportBtn.addEventListener('click', openReport);
els.wakeBtn.addEventListener('click', touchInteraction);
els.refreshHistoryBtn.addEventListener('click', pollStatus);
els.applyRecommendedBtn.addEventListener('click', () => applyPreset(onboardingModel.presetKey));
els.openHelpPresetBtn.addEventListener('click', () => sendCommand('/help'));
els.mode.addEventListener('change', () => {
  if (activePresetKey) {
    activePresetKey = null;
    renderWizardState();
  }
  updateModeVisibility();
});

[els.rounds, els.minutes, els.hours, els.guardWorkers, els.ramMb].forEach((el) => {
  const onEdit = () => {
    if (activePresetKey) {
      activePresetKey = null;
      renderWizardState();
    }
    renderNextRunSummary();
  };
  el.addEventListener('input', onEdit);
  el.addEventListener('change', onEdit);
});

els.commandInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') sendCommand();
});

els.historyList.addEventListener('click', async (event) => {
  const button = event.target.closest('.historyAction');
  if (!button) return;
  const action = button.dataset.action;
  const path = button.dataset.path;
  if (action === 'open-report' && path) {
    try {
      await openReportAtPath(path);
      pushAlert('success', 'Relatório aberto', 'O relatório selecionado foi carregado no preview da interface.', `open-report-${path}`);
    } catch (error) {
      pushAlert('danger', 'Falha ao abrir relatório', error.message, `open-report-error-${path}`);
    }
  }
  if (action === 'copy-state-dir' && path) {
    try {
      await copyToClipboard(path);
      pushAlert('info', 'State dir copiado', 'O caminho da sessão foi copiado para a área de transferência.', `copy-${path}`);
    } catch (error) {
      pushAlert('warn', 'Não consegui copiar automaticamente', `${path}`, `copy-error-${path}`);
    }
  }
  if (action === 'repeat-session') {
    const payload = decodePayload(button.dataset.payload);
    applyLaunchPayload(payload, 'A sessão escolhida', true);
  }
});

els.terminalCard.addEventListener('click', touchInteraction);
els.commandInput.addEventListener('focus', touchInteraction);
els.commandInput.addEventListener('input', touchInteraction);
els.sendCmdBtn.addEventListener('focus', touchInteraction);
document.addEventListener('click', (event) => {
  if (!event.target.closest('.infoDot')) {
    hideTooltip();
  }
});
window.addEventListener('resize', hideTooltip);
window.addEventListener('scroll', hideTooltip, true);

document.querySelectorAll('.chip').forEach((btn) => {
  btn.addEventListener('click', () => sendCommand(btn.dataset.cmd));
});

document.querySelectorAll('.wizardCard').forEach((btn) => {
  btn.addEventListener('click', () => applyPreset(btn.dataset.preset));
});

attachTooltips();
renderBackgroundMode();
renderAlertFeed();
renderWizardState();
updateModeVisibility();
updateTerminalHint();
loadBootstrap();
pollStatus();
