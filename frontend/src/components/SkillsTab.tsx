// Skills tab: registry listing with Hermes-style enable/disable toggles.
// Backend: GET /api/skills (admin view, disabled included) +
// POST /api/skills/{rel_dir}/enabled. Toggles apply to new sessions — the
// skills index is injected into the system prompt once per session.

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import { getSkills, setSkillEnabled } from "../api";
import type { SkillInfo } from "../types";

type Filter = "all" | "enabled" | "disabled";

const FILTERS: Filter[] = ["all", "enabled", "disabled"];

export default function SkillsTab() {
  const [skills, setSkills] = useState<SkillInfo[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());

  const toggleExpanded = useCallback((rel: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(rel)) next.delete(rel);
      else next.add(rel);
      return next;
    });
  }, []);

  const refresh = useCallback(() => {
    getSkills()
      .then((rows) => {
        setSkills(rows);
        setLoadError(null);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : String(err)));
  }, []);

  useEffect(refresh, [refresh]);

  const toggle = useCallback(
    async (skill: SkillInfo) => {
      if (busy) return;
      const rel = skill.rel_dir;
      const next = !skill.enabled;
      setBusy(rel);
      setBanner(null);
      // optimistic: flip immediately, roll back on failure
      setSkills((prev) => prev?.map((s) => (s.rel_dir === rel ? { ...s, enabled: next } : s)) ?? prev);
      try {
        await setSkillEnabled(rel, next);
      } catch (err) {
        setSkills((prev) => prev?.map((s) => (s.rel_dir === rel ? { ...s, enabled: !next } : s)) ?? prev);
        setBanner(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(null);
      }
    },
    [busy],
  );

  const shown = useMemo(() => {
    if (!skills) return [];
    const q = query.trim().toLowerCase();
    return skills.filter((s) => {
      if (filter === "enabled" && !s.enabled) return false;
      if (filter === "disabled" && s.enabled) return false;
      if (!q) return true;
      return s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q);
    });
  }, [skills, query, filter]);

  const enabledCount = skills?.filter((s) => s.enabled).length ?? 0;

  return (
    <main className="skills">
      <div className="skills-inner">
        <div className="skills-head">
          <div>
            <div className="skills-title">Skills</div>
            <div className="skills-count">
              {skills
                ? `${enabledCount} enabled · ${skills.length - enabledCount} disabled`
                : "loading…"}
            </div>
          </div>
          <button className="skills-refresh" onClick={refresh}>
            ↻ Refresh
          </button>
        </div>

        {banner && (
          <div className="skills-error" onClick={() => setBanner(null)} title="click to dismiss">
            {banner} — click to dismiss
          </div>
        )}

        {loadError ? (
          <div className="skills-error">
            {loadError} — <button className="skills-retry" onClick={refresh}>retry</button>
          </div>
        ) : (
          <>
            <div className="skills-controls">
              <input
                className="skills-search"
                placeholder="Filter skills…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {FILTERS.map((f) => (
                <button
                  key={f}
                  className={`chip${filter === f ? " active" : ""}`}
                  onClick={() => setFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>

            <div className="skills-list">
              {skills === null && <div className="skills-empty">loading…</div>}
              {skills !== null && skills.length === 0 && (
                <div className="skills-empty">
                  No skills in the registry yet — the agent creates them via skill_manage.
                </div>
              )}
              {skills !== null && skills.length > 0 && shown.length === 0 && (
                <div className="skills-empty">No skills match.</div>
              )}
              {shown.map((s) => {
                const open = expanded.has(s.rel_dir);
                return (
                  <div key={s.rel_dir} className={`skill-row${s.enabled ? "" : " disabled"}`}>
                    <button
                      className="skill-expand"
                      aria-expanded={open}
                      title={open ? "Collapse" : "Show full description"}
                      onClick={() => toggleExpanded(s.rel_dir)}
                    >
                      <span className="skill-row-head">
                        <span className="skill-name">{s.name}</span>
                        <ChevronRight size={14} aria-hidden className={`skill-chevron${open ? " open" : ""}`} />
                      </span>
                      {s.description && (
                        <span className={`skill-desc${open ? " open" : ""}`}>{s.description}</span>
                      )}
                    </button>
                    <button
                      className={`toggle${s.enabled ? " on" : ""}`}
                      role="switch"
                      aria-checked={s.enabled}
                      aria-label={`${s.enabled ? "Disable" : "Enable"} skill ${s.name}`}
                      disabled={busy !== null}
                      onClick={() => toggle(s)}
                    >
                      <span className="knob" />
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="skills-note">
              Toggles write to the registry immediately and apply to new sessions — the skills
              index is injected into the agent's prompt once per session
            </div>
          </>
        )}
      </div>
    </main>
  );
}
