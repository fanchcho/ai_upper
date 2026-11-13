import { c as createLucideIcon, u as useI18n, r as reactExports, H as Hand, C as CircleCheckBig, U as Upload, S as ShieldCheck, K as KeyRound, s as siteOf, j as jsxRuntimeExports, A as ArrowLeft, t as tabTitle, L as LoaderCircle, X, P as PinOff, a as Pin, b as Lock, T as TriangleAlert, d as doingText, e as Square, G as Globe, f as PersonaFace, p as parseAvatarSpec, g as client, R as React, h as ThemeProvider, I as I18nProvider } from "./text-C9wd0hHJ.js";
/**
 * @license lucide-react v0.454.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const Ellipsis = createLucideIcon("Ellipsis", [
  ["circle", { cx: "12", cy: "12", r: "1", key: "41hilf" }],
  ["circle", { cx: "19", cy: "12", r: "1", key: "1wjl8i" }],
  ["circle", { cx: "5", cy: "12", r: "1", key: "1pcz8c" }]
]);
const BROWSER_CHROME = {
  tabBar: 40,
  statusBar: 36
};
const HANDOFF_ICON = {
  login: KeyRound,
  captcha: ShieldCheck,
  upload: Upload,
  confirm: CircleCheckBig,
  other: Hand
};
const IS_MAC = navigator.userAgent.includes("Macintosh");
function BrowserChrome() {
  const { t } = useI18n();
  const [s, setS] = reactExports.useState(null);
  const [personas, setPersonas] = reactExports.useState({});
  const [menuOpen, setMenuOpen] = reactExports.useState(false);
  reactExports.useEffect(() => {
    void window.deva.browser.ready().then(setS);
    return window.deva.browser.onState(setS);
  }, []);
  const personaKey = reactExports.useMemo(
    () => [...new Set((s?.tabs ?? []).map((x) => x.personaId).filter(Boolean))].sort().join(","),
    [s?.tabs]
  );
  reactExports.useEffect(() => {
    void window.deva.personas.list().then((list) => setPersonas(Object.fromEntries(list.map((p) => [p.id, p]))));
  }, [personaKey]);
  const tabs = s?.tabs ?? [];
  const active = tabs.find((x) => x.id === s?.active) ?? null;
  const sid = active?.sessionId;
  const handoff = s && sid ? s.handoff[sid] ?? null : null;
  const op = s && sid && !handoff && s.operating[sid]?.tab === active?.id ? s.operating[sid] : null;
  const chromeH = BROWSER_CHROME.tabBar + (handoff || op ? BROWSER_CHROME.statusBar : 0);
  const persona = (id) => id ? personas[id] : void 0;
  const face = (id) => {
    const p = persona(id);
    return p ? /* @__PURE__ */ jsxRuntimeExports.jsx(PersonaFace, { seed: p.id, spec: parseAvatarSpec(p.avatar), image: p.avatarImage, title: p.name, compact: true }) : /* @__PURE__ */ jsxRuntimeExports.jsx(Globe, { size: 12 });
  };
  const api = window.deva.browser;
  const who = handoff?.who || persona(active?.personaId)?.name || "Deva";
  const HandoffIcon = handoff ? HANDOFF_ICON[handoff.reason] ?? Hand : Hand;
  const site = handoff && active ? siteOf(active.url) : null;
  const openMenu = (btn) => {
    if (!active || menuOpen) return;
    const r = btn.getBoundingClientRect();
    setMenuOpen(true);
    void api.menu(
      active.id,
      {
        forward: t("browser.forward"),
        reload: t("browser.reload"),
        stopLoading: t("browser.stopLoading"),
        copyLink: t("browser.copyLink"),
        openExternal: t("browser.openExternal")
      },
      { x: r.left, y: r.bottom + 4 }
    ).finally(() => setMenuOpen(false));
  };
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: `bc${IS_MAC ? " is-mac" : ""}`, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "bc-tabs", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "bc-tabs__nav", children: /* @__PURE__ */ jsxRuntimeExports.jsx(
        "button",
        {
          type: "button",
          className: "bc-ib",
          title: t("browser.back"),
          disabled: !active?.canGoBack,
          onClick: () => active && void api.nav(active.id, "back"),
          children: /* @__PURE__ */ jsxRuntimeExports.jsx(ArrowLeft, { size: 16 })
        }
      ) }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "bc-tabs__sep" }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "bc-tabs__list", role: "tablist", children: tabs.map((tab) => {
        const on = tab.id === s?.active;
        const live = s?.operating[tab.sessionId]?.tab === tab.id;
        const waiting = s?.handoff[tab.sessionId]?.tab === tab.id;
        const p = persona(tab.personaId);
        const title = tabTitle(t, tab);
        const host = siteOf(tab.url)?.host;
        const tip = [title, host && host !== title ? host : "", p ? t("browser.openedBy").replace("{name}", p.name) : ""].filter(Boolean).join("\n");
        return /* @__PURE__ */ jsxRuntimeExports.jsxs(
          "div",
          {
            role: "tab",
            "aria-selected": on,
            className: `bc-tab${on ? " is-on" : ""}`,
            title: tip,
            onMouseDown: (e) => {
              if (e.button === 0) void api.activate(tab.id);
              if (e.button === 1) {
                e.preventDefault();
                void api.closeTab(tab.id);
              }
            },
            children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: `bc-tab__ava${live ? " is-live" : ""}${waiting ? " is-wait" : ""}`, children: face(tab.personaId) }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "bc-tab__title", children: title }),
              tab.loading && /* @__PURE__ */ jsxRuntimeExports.jsx(LoaderCircle, { size: 12, className: "spin bc-tab__spin" }),
              /* @__PURE__ */ jsxRuntimeExports.jsx(
                "button",
                {
                  type: "button",
                  className: "bc-tab__x",
                  title: t("browser.closeTab"),
                  onMouseDown: (e) => e.stopPropagation(),
                  onClick: () => void api.closeTab(tab.id),
                  children: /* @__PURE__ */ jsxRuntimeExports.jsx(X, { size: 12 })
                }
              )
            ]
          },
          tab.id
        );
      }) }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "bc-tabs__acts", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            type: "button",
            className: `bc-ib${menuOpen ? " is-press" : ""}`,
            title: t("browser.more"),
            disabled: !active,
            onClick: (e) => openMenu(e.currentTarget),
            children: /* @__PURE__ */ jsxRuntimeExports.jsx(Ellipsis, { size: 16 })
          }
        ),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            type: "button",
            className: `bc-ib${s?.pinned ? " is-on" : ""}`,
            title: s?.pinned ? t("browser.unpin") : t("browser.pin"),
            onClick: () => void api.pin(!s?.pinned),
            children: s?.pinned ? /* @__PURE__ */ jsxRuntimeExports.jsx(PinOff, { size: 15 }) : /* @__PURE__ */ jsxRuntimeExports.jsx(Pin, { size: 15 })
          }
        )
      ] })
    ] }),
    handoff && sid && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "bc-strip is-handoff", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx(HandoffIcon, { size: 15, className: "bc-strip__icon" }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { className: "bc-strip__text", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("b", { children: t(`browser.handoff.${handoff.reason}`).replace("{name}", who) }),
        site && /* @__PURE__ */ jsxRuntimeExports.jsxs(
          "span",
          {
            className: `bc-site${site.secure ? "" : " is-insecure"}`,
            title: site.secure ? void 0 : t("browser.insecure"),
            children: [
              site.secure ? /* @__PURE__ */ jsxRuntimeExports.jsx(Lock, { size: 12 }) : /* @__PURE__ */ jsxRuntimeExports.jsx(TriangleAlert, { size: 12 }),
              site.host
            ]
          }
        ),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { children: [
          " · ",
          handoff.message || t("browser.handoffHint")
        ] })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("button", { type: "button", className: "bc-btn", onClick: () => void api.handoff(sid, "skip"), children: t("browser.skip") }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("button", { type: "button", className: "bc-btn is-primary", onClick: () => void api.handoff(sid, "done"), children: t("browser.done") })
    ] }),
    op && sid && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "bc-strip is-op", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "bc-strip__ava", children: face(active?.personaId) }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { className: "bc-strip__text", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("b", { children: t("browser.operating").replace("{name}", who) }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { children: [
          " · ",
          doingText(t, op.action, op.label)
        ] })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("button", { type: "button", className: "bc-btn", title: t("browser.stopHint"), onClick: () => void api.stop(sid), children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(Square, { size: 9 }),
        t("browser.stop")
      ] })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: `bc-frame${op ? " is-op" : ""}${handoff ? " is-handoff" : ""}`, style: { top: chromeH }, children: tabs.length === 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "bc-empty", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx(Globe, { size: 28 }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "bc-empty__title", children: t("browser.emptyTitle") }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("p", { children: t("browser.emptyHint") })
    ] }) })
  ] });
}
client.createRoot(document.getElementById("root")).render(
  /* @__PURE__ */ jsxRuntimeExports.jsx(React.StrictMode, { children: /* @__PURE__ */ jsxRuntimeExports.jsx(ThemeProvider, { children: /* @__PURE__ */ jsxRuntimeExports.jsx(I18nProvider, { children: /* @__PURE__ */ jsxRuntimeExports.jsx(BrowserChrome, {}) }) }) })
);
