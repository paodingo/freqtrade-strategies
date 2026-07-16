import type {
  DashboardPreferences,
  DashboardVariant,
  DensityMode,
  ExpertiseMode,
  PreviewState,
  DashboardTheme,
} from "../hooks/useDashboardPreferences";

interface TweaksPanelProps {
  open: boolean;
  preferences: DashboardPreferences;
  onClose: () => void;
  onUpdate: <Key extends keyof DashboardPreferences>(key: Key, value: DashboardPreferences[Key]) => void;
}

export function TweaksPanel({ open, preferences, onClose, onUpdate }: TweaksPanelProps) {
  if (!open) return null;
  return (
    <aside className="tweaks-panel" aria-label="Tweaks" aria-modal="false">
      <div className="tweaks-heading">
        <div>
          <p className="eyebrow">DESIGN V0</p>
          <h2>Tweaks</h2>
        </div>
        <button className="close-button" type="button" onClick={onClose} aria-label="关闭 Tweaks">关闭</button>
      </div>
      <label>
        <span>界面方向</span>
        <select
          value={preferences.variant}
          onChange={(event) => onUpdate("variant", event.target.value as DashboardVariant)}
        >
          <option value="cockpit">A · 决策驾驶舱</option>
          <option value="terminal">B · 研究终端</option>
          <option value="narrative">C · 解释型视图</option>
        </select>
      </label>
      <label>
        <span>信息深度</span>
        <select
          value={preferences.expertise}
          onChange={(event) => onUpdate("expertise", event.target.value as ExpertiseMode)}
        >
          <option value="guided">引导模式</option>
          <option value="professional">专业模式</option>
        </select>
      </label>
      <label>
        <span>主题</span>
        <select
          value={preferences.theme}
          onChange={(event) => onUpdate("theme", event.target.value as DashboardTheme)}
        >
          <option value="dark">深色</option>
          <option value="light">浅色</option>
        </select>
      </label>
      <label>
        <span>密度</span>
        <select
          value={preferences.density}
          onChange={(event) => onUpdate("density", event.target.value as DensityMode)}
        >
          <option value="comfortable">舒展</option>
          <option value="compact">紧凑</option>
        </select>
      </label>
      <label>
        <span>状态预览</span>
        <select
          value={preferences.previewState}
          onChange={(event) => onUpdate("previewState", event.target.value as PreviewState)}
        >
          <option value="live">真实数据</option>
          <option value="loading">加载状态</option>
          <option value="error">错误状态</option>
          <option value="empty">空状态</option>
        </select>
      </label>
      <p className="tweaks-note">状态预览只验证界面，不会改写 Registry 或运行数据。</p>
    </aside>
  );
}
