"""Render a project's timesheet ledger as charts and pages; regenerate the external CSV.

Outputs (default into <report_out>, from timesheet.json):
    timesheet_report.html            self-contained interactive page (plotly inlined; works offline)
    timesheet_report_external.html   external page from the task table (only when external_prefix is set)
    weekly_by_category.png           stacked column, hours per ISO week by category
    cumulative.png                   cumulative hours with milestone markers
    tiers.png                        A / B / C claim tiers
    (PNG via matplotlib; HTML via plotly)

Usage (any directory inside the project, or --project DIR):
    python timesheet_report.py
    python timesheet_report.py --uplift 0.25 0.35       # tier-C range multipliers on logged hours
    python timesheet_report.py --csv                    # also regenerate external_csv from the external table
    python timesheet_report.py --csv-only               # only the CSV, no charts

Project constants (categories, fold map, milestones, titles, claim) live in timesheet.json.
The script warns when the external task table's total differs from the ledger's.
"""
import argparse
import csv
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timesheet_common as tc  # noqa: E402

tc.utf8_stdio()

# validated reference palette (dataviz skill, light + dark selected)
LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
INK = {"surface": "#fcfcfb", "page": "#f9f9f7", "primary": "#0b0b0b", "secondary": "#52514e",
       "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7"}
FONT = "Microsoft YaHei, Segoe UI, system-ui, sans-serif"
EXTERNAL_CSV_HEADER = ["任务分类", "参与人员", "任务", "交付要求", "任务布置时间", "结束时间", "状态", "成果", "工时(h)"]


# ---------------------------------------------------------------- ledger
def parse_ledger(cfg):
    """Return rows: dict(date, cat, task, hours, source, people)."""
    cats, fold, fallback = cfg["report_categories"], cfg["fold"], cfg["fallback_category"]
    rows = []
    with open(cfg["ledger"], encoding="utf-8") as fh:
        for line in fh:
            if not tc.ROW_RX.match(line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 8:
                continue
            date, cat, task, deliver, people, hours, source, status = cells[:8]
            try:
                h = float(hours)
            except ValueError:
                continue  # "待补" etc.
            if status.startswith("草稿"):
                continue  # unarchived rows written by timesheet_audit.py --draft
            if cat in cfg["exclude_categories"]:
                continue  # work for another project parked in this ledger; excluded from totals
            cat = fold.get(cat, cat)
            if cat not in cats:
                cat = fallback
            src = "会议" if source.startswith("会议") else ("手记" if source.startswith("手记") else "日志")
            rows.append({"date": dt.date.fromisoformat(date), "cat": cat, "task": task,
                         "deliver": deliver, "people": people, "hours": h, "source": src, "status": status})
    if not rows:
        sys.exit(f"no rows parsed from {cfg['ledger']}")
    return rows


def external_rows(cfg):
    """Cells of task rows in the external table (rows starting with the configured prefix)."""
    out = []
    with open(cfg["external_ledger"], encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("| " + cfg["external_prefix"]):
                out.append([x.strip() for x in line.strip().strip("|").split("|")])
    return out


def parse_external(cfg):
    """Task rows from the external table (PP column structure)."""
    tasks = []
    for c in external_rows(cfg):
        if len(c) < 9:
            continue
        try:
            h = float(c[8])
        except ValueError:
            continue
        tasks.append({"people": c[1], "task": c[2], "deliver": c[3], "start": c[4], "end": c[5],
                      "status": c[6], "result": c[7], "hours": h})
    if not tasks:
        sys.exit(f"no task rows parsed from {cfg['external_ledger']}")
    return tasks


def write_external_csv(cfg):
    if not cfg["external_csv"]:
        print("[csv] timesheet.json 未配置 external_csv，跳过。")
        return
    rows = external_rows(cfg)
    with open(cfg["external_csv"], "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(EXTERNAL_CSV_HEADER)
        for c in rows:
            w.writerow(c)
    print(f"[csv] {len(rows)} 行 -> {tc.rel(cfg, cfg['external_csv'])}")


def week_start(d):
    return d - dt.timedelta(days=d.weekday())


def aggregate(cfg, rows):
    cats = cfg["report_categories"]
    weeks = sorted({week_start(r["date"]) for r in rows})
    by_week = {w: {c: 0.0 for c in cats} for w in weeks}
    for r in rows:
        by_week[week_start(r["date"])][r["cat"]] += r["hours"]
    by_day = {}
    for r in rows:
        by_day[r["date"]] = by_day.get(r["date"], 0.0) + r["hours"]
    by_cat = {c: 0.0 for c in cats}
    for r in rows:
        by_cat[r["cat"]] += r["hours"]
    logged = sum(r["hours"] for r in rows if r["source"] == "日志")
    manual = sum(r["hours"] for r in rows if r["source"] != "日志")
    return weeks, by_week, by_day, by_cat, logged, manual


def tiers(logged, manual, uplift):
    a = logged
    b = logged + manual
    c_lo = logged * (1 + uplift[0]) + manual
    c_hi = logged * (1 + uplift[1]) + manual
    return a, b, c_lo, c_hi


def fmt_h(x):
    return f"{x:g}"


def milestones(cfg):
    return [(dt.date.fromisoformat(d), label) for d, label in cfg["milestones"]]


# ---------------------------------------------------------------- matplotlib PNGs
def render_png(cfg, rows, out, uplift):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    cats, claim = cfg["report_categories"], cfg["claim_round"]
    names = {f.name for f in fm.fontManager.ttflist}
    plt.rcParams["font.family"] = [n for n in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC") if n in names] + ["sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    weeks, by_week, by_day, by_cat, logged, manual = aggregate(cfg, rows)
    active = [c for c in cats if by_cat[c] > 0]
    colors = {c: LIGHT[cats.index(c)] for c in cats}

    def style(ax):
        ax.set_facecolor(INK["surface"])
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(INK["axis"])
        ax.tick_params(colors=INK["muted"], labelsize=9)
        ax.yaxis.grid(True, color=INK["grid"], linewidth=0.8)
        ax.set_axisbelow(True)

    # 1. weekly stacked
    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=160, facecolor=INK["surface"])
    style(ax)
    x = list(range(len(weeks)))
    bottom = [0.0] * len(weeks)
    for c in active:
        vals = [by_week[w][c] for w in weeks]
        ax.bar(x, vals, bottom=bottom, width=0.62, color=colors[c], label=c,
               edgecolor=INK["surface"], linewidth=1.5)
        bottom = [b + v for b, v in zip(bottom, vals)]
    for xi, tot in zip(x, bottom):
        if tot > 0:
            ax.text(xi, tot + 0.3, fmt_h(tot), ha="center", va="bottom", fontsize=9, color=INK["secondary"])
    ax.set_xticks(x)
    ax.set_xticklabels([f"{w.month}/{w.day} 周" for w in weeks])
    ax.set_ylabel("工时 (h)", color=INK["secondary"])
    ax.set_title("每周工时 · 按分类", loc="left", fontsize=12, color=INK["primary"])
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="upper left", bbox_to_anchor=(0, -0.12))
    fig.tight_layout()
    fig.savefig(os.path.join(out, "weekly_by_category.png"))
    plt.close(fig)

    # 2. cumulative
    days = sorted(by_day)
    d0, d1 = days[0], days[-1]
    span = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
    cum, acc = [], 0.0
    for d in span:
        acc += by_day.get(d, 0.0)
        cum.append(acc)
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=160, facecolor=INK["surface"])
    style(ax)
    ax.plot(span, cum, color=LIGHT[0], linewidth=2)
    ax.fill_between(span, cum, color=LIGHT[0], alpha=0.08)
    for d, label in milestones(cfg):
        if d0 <= d <= d1:
            y = cum[(d - d0).days]
            ax.plot([d], [y], marker="o", markersize=7, color=LIGHT[0], markeredgecolor=INK["surface"], markeredgewidth=1.5)
            ax.annotate(label, (d, y), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=8, color=INK["secondary"])
    ax.text(span[-1], cum[-1], f"  {fmt_h(cum[-1])} h", va="center", fontsize=10, color=INK["primary"])
    ax.set_ylim(0, max(cum) * 1.18)
    ax.set_xlim(d0 - dt.timedelta(days=1), d1 + dt.timedelta(days=4))
    ax.set_ylabel("累计工时 (h)", color=INK["secondary"])
    ax.set_title("累计工时与节点", loc="left", fontsize=12, color=INK["primary"])
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(out, "cumulative.png"))
    plt.close(fig)

    # 3. tiers
    a, b, c_lo, c_hi = tiers(logged, manual, uplift)
    labels = ["A 日志留痕", "B + 会议", "C + 自行阅读/沟通估算"]
    vals = [a, b, c_hi]
    fig, ax = plt.subplots(figsize=(9, 2.9), dpi=160, facecolor=INK["surface"])
    style(ax)
    ax.xaxis.grid(True, color=INK["grid"], linewidth=0.8)
    ax.yaxis.grid(False)
    y = [2, 1, 0]
    ax.barh(y, vals, height=0.55, color=[SEQ[3], SEQ[7], SEQ[10]], edgecolor=INK["surface"], linewidth=1.5)
    ax.barh([0], [c_hi - c_lo], left=[c_lo], height=0.55, color=INK["surface"], alpha=0.45, edgecolor="none")
    ax.text(a + 0.8, 2, f"{fmt_h(a)} h", va="center", fontsize=10, color=INK["primary"])
    ax.text(b + 0.8, 1, f"{fmt_h(b)} h", va="center", fontsize=10, color=INK["primary"])
    ax.text(c_hi + 0.8, 0, f"{fmt_h(round(c_lo))}–{fmt_h(round(c_hi))} h", va="center", fontsize=10, color=INK["primary"])
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, c_hi * 1.25)
    ax.set_xlabel("工时 (h)", color=INK["secondary"])
    ax.set_title(f"申报口径 · 建议 {claim} h（{claim / 8:g} 个工作日）", loc="left", fontsize=12, color=INK["primary"])
    fig.tight_layout()
    fig.savefig(os.path.join(out, "tiers.png"))
    plt.close(fig)


# ---------------------------------------------------------------- plotly HTML
def render_html(cfg, rows, out, uplift, tasks=None):
    """tasks=None -> internal page; tasks=list -> external page (no tiers, no log detail)."""
    import plotly.graph_objects as go
    import plotly.io as pio
    cats, claim = cfg["report_categories"], cfg["claim_round"]
    external = tasks is not None
    weeks, by_week, by_day, by_cat, logged, manual = aggregate(cfg, rows)
    active = [c for c in cats if by_cat[c] > 0]
    a, b, c_lo, c_hi = tiers(logged, manual, uplift)

    def base_layout(title, height=380):
        return dict(title=dict(text=title, x=0, font=dict(size=15, color=INK["primary"])),
                    font=dict(family=FONT, size=12, color=INK["secondary"]),
                    paper_bgcolor=INK["surface"], plot_bgcolor=INK["surface"],
                    margin=dict(l=50, r=30, t=50, b=50), height=height,
                    hoverlabel=dict(bgcolor="#ffffff", font=dict(family=FONT, color=INK["primary"])),
                    xaxis=dict(showgrid=False, linecolor=INK["axis"], tickfont=dict(color=INK["muted"])),
                    yaxis=dict(gridcolor=INK["grid"], zerolinecolor=INK["axis"], tickfont=dict(color=INK["muted"])),
                    legend=dict(orientation="h", y=-0.18, x=0, traceorder="normal", font=dict(color=INK["secondary"])))

    # 1. weekly stacked
    f1 = go.Figure()
    for c in active:
        f1.add_bar(name=c, x=[f"{w.month}/{w.day} 周" for w in weeks], y=[by_week[w][c] for w in weeks],
                   marker=dict(color=LIGHT[cats.index(c)], line=dict(color=INK["surface"], width=2)),
                   hovertemplate="%{x}<br>" + c + "：%{y:g} h<extra></extra>")
    totals = [sum(by_week[w].values()) for w in weeks]
    f1.add_scatter(x=[f"{w.month}/{w.day} 周" for w in weeks], y=totals, mode="text", text=[fmt_h(t) for t in totals],
                   textposition="top center", textfont=dict(color=INK["secondary"]), showlegend=False, hoverinfo="skip")
    f1.update_layout(barmode="stack", bargap=0.38, **base_layout("每周工时 · 按分类"))
    f1.update_yaxes(title_text="工时 (h)", range=[0, max(totals) * 1.15])

    # 2. cumulative
    days = sorted(by_day)
    d0, d1 = days[0], days[-1]
    span = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
    cum, acc = [], 0.0
    for d in span:
        acc += by_day.get(d, 0.0)
        cum.append(acc)
    f2 = go.Figure()
    f2.add_scatter(x=span, y=cum, mode="lines", line=dict(color=LIGHT[0], width=2), fill="tozeroy",
                   fillcolor="rgba(42,120,214,0.08)", name="累计工时",
                   customdata=[by_day.get(d, 0.0) for d in span],
                   hovertemplate="%{x|%m-%d}<br>当日 %{customdata:g} h · 累计 %{y:g} h<extra></extra>")
    mx, my, mt = [], [], []
    for d, label in milestones(cfg):
        if d0 <= d <= d1:
            mx.append(d); my.append(cum[(d - d0).days]); mt.append(label)
    f2.add_scatter(x=mx, y=my, mode="markers+text", text=mt, textposition="top center",
                   textfont=dict(size=11, color=INK["secondary"]),
                   marker=dict(size=10, color=LIGHT[0], line=dict(color=INK["surface"], width=2)),
                   name="节点", hovertemplate="%{text}<br>%{x|%m-%d} · 累计 %{y:g} h<extra></extra>")
    f2.update_layout(hovermode="x unified", showlegend=False, **base_layout("累计工时与节点"))
    f2.update_yaxes(title_text="累计工时 (h)", range=[0, max(cum) * 1.2])
    f2.update_xaxes(showspikes=True, spikecolor=INK["axis"], spikethickness=1, spikedash="solid", spikemode="across")

    # 3. calendar heatmap (weeks x weekday)
    z, text, ylabels = [], [], []
    for w in weeks:
        rowz, rowt = [], []
        for i in range(7):
            d = w + dt.timedelta(days=i)
            h = by_day.get(d, 0.0)
            rowz.append(h if h > 0 else None)
            rowt.append(f"{d:%m-%d}<br>{fmt_h(h)} h" if h > 0 else f"{d:%m-%d}<br>无记录")
        z.append(rowz); text.append(rowt); ylabels.append(f"{w.month}/{w.day} 周")
    f3 = go.Figure(go.Heatmap(z=z, x=["一", "二", "三", "四", "五", "六", "日"], y=ylabels, text=text,
                              hovertemplate="%{text}<extra></extra>", xgap=3, ygap=3,
                              colorscale=[[0, SEQ[0]], [1, SEQ[12]]], zmin=0, zmax=max(by_day.values()),
                              colorbar=dict(title="h", thickness=10, tickfont=dict(color=INK["muted"]))))
    f3.update_layout(**base_layout("每日工时日历", height=80 + 46 * len(weeks)))
    f3.update_yaxes(autorange="reversed", showgrid=False)
    f3.update_xaxes(side="top")

    # 4. tiers
    f4 = go.Figure()
    labels = ["C + 自行阅读/沟通估算", "B + 会议", "A 日志留痕"]
    f4.add_bar(y=labels, x=[c_hi, b, a], orientation="h", marker=dict(color=[SEQ[10], SEQ[7], SEQ[3]], line=dict(color=INK["surface"], width=2)),
               text=[f"{fmt_h(round(c_lo))}–{fmt_h(round(c_hi))} h", f"{fmt_h(b)} h", f"{fmt_h(a)} h"], textposition="outside",
               textfont=dict(color=INK["primary"]), hovertemplate="%{y}：%{text}<extra></extra>")
    f4.update_layout(bargap=0.4, showlegend=False, **base_layout(f"申报口径 · 建议 {claim} h（{claim / 8:g} 个工作日）", height=260))
    f4.update_xaxes(title_text="工时 (h)", range=[0, c_hi * 1.25], gridcolor=INK["grid"], showgrid=True)
    f4.update_yaxes(showgrid=False)

    # 5. per-task bars (external page)
    f5 = None
    if external:
        tl = [f"{t['task']}" for t in tasks][::-1]
        th = [t["hours"] for t in tasks][::-1]
        tcd = [f"{t['start']} – {t['end']}<br>{t['people']}" for t in tasks][::-1]
        f5 = go.Figure(go.Bar(y=tl, x=th, orientation="h", customdata=tcd,
                              marker=dict(color=LIGHT[0], line=dict(color=INK["surface"], width=2)),
                              text=[f"{fmt_h(h)} h" for h in th], textposition="outside", textfont=dict(color=INK["primary"]),
                              hovertemplate="%{y}<br>%{customdata}<br>%{x:g} h<extra></extra>"))
        f5.update_layout(bargap=0.35, showlegend=False, **base_layout("各任务工时", height=60 + 34 * len(tasks)))
        f5.update_xaxes(title_text="工时 (h)", range=[0, max(th) * 1.2], gridcolor=INK["grid"], showgrid=True)
        f5.update_yaxes(showgrid=False, tickfont=dict(color=INK["primary"], size=12))

    cat_rows = "".join(f"<tr><td><span class='sw' style='background:{LIGHT[cats.index(c)]}'></span>{c}</td><td class='num'>{fmt_h(by_cat[c])}</td></tr>"
                       for c in active)
    n_days = len(by_day)
    total = logged + manual
    if external:
        kpis = [("合计工时", f"{fmt_h(total)} h", f"{days[0]:%m-%d} 至 {days[-1]:%m-%d}"),
                ("任务数", f"{len(tasks)}", f"{sum(1 for t in tasks if t['status'] == '完成')} 项完成"),
                ("有记录天数", f"{n_days}", f"日均 {total / n_days:.1f} h"),
                ("会议", f"{fmt_h(by_cat.get('会议', 0))} h", "含会前对稿")]
        detail_head = "<tr><th>任务</th><th>交付要求</th><th>参与人员</th><th>布置</th><th>结束</th><th>状态</th><th>成果</th><th class='num'>工时</th></tr>"
        detail_rows = "".join(f"<tr><td>{t['task']}</td><td>{t['deliver']}</td><td>{t['people']}</td><td class='nw'>{t['start']}</td><td class='nw'>{t['end']}</td><td class='nw'>{t['status']}</td><td>{t['result']}</td><td class='num'>{fmt_h(t['hours'])}</td></tr>"
                              for t in tasks)
        detail_title = f"任务明细（{len(tasks)} 项）"
        figs = [f1, f2, f3, f5]
        page_title = cfg["report_title_external"]
        sub = f"统计区间 {days[0]:%Y-%m-%d} 至 {days[-1]:%Y-%m-%d} · 生成日 {dt.date.today()} · 口径：连续工作块进一法取整到半小时；会议按实际时长；不含自行阅读与微信沟通时间"
        fname = "timesheet_report_external.html"
    else:
        kpis = [("合计工时", f"{fmt_h(total)} h", f"日志 {fmt_h(logged)} + 会议 {fmt_h(manual)}"),
                ("有记录天数", f"{n_days}", f"{days[0]:%m-%d} 至 {days[-1]:%m-%d}"),
                ("日均（有记录日）", f"{total / n_days:.1f} h", "进一法取整到半小时"),
                ("建议申报", f"{claim} h", f"≈ {claim / 8:g} 个工作日")]
        detail_head = "<tr><th>日期</th><th>分类</th><th>任务</th><th>参与人</th><th class='num'>工时</th><th>来源</th></tr>"
        detail_rows = "".join(f"<tr><td>{r['date']}</td><td>{r['cat']}</td><td>{r['task']}</td><td>{r['people']}</td><td class='num'>{fmt_h(r['hours'])}</td><td>{r['source']}</td></tr>"
                              for r in sorted(rows, key=lambda r: r["date"]))
        detail_title = f"逐条明细（{len(rows)} 行）"
        figs = [f1, f2, f3, f4]
        page_title = cfg["report_title"]
        sub = f"数据源 {tc.rel(cfg, cfg['ledger'])} · 生成日 {dt.date.today()} · 规则：连续工作块进一法取整到半小时；会议与手记单列"
        fname = "timesheet_report.html"
    kpi_html = "".join(f"<div class='tile'><div class='k'>{k}</div><div class='v'>{v}</div><div class='s'>{s}</div></div>" for k, v, s in kpis)

    cfg_plot = dict(displaylogo=False, responsive=True, modeBarButtonsToRemove=["select2d", "lasso2d"])
    parts = [pio.to_html(f, full_html=False, include_plotlyjs=(i == 0), config=cfg_plot) for i, f in enumerate(figs)]
    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<style>
  body{{margin:0;background:{INK['page']};color:{INK['primary']};font-family:{FONT};}}
  .wrap{{max-width:1040px;margin:0 auto;padding:28px 20px 60px;}}
  h1{{font-size:22px;margin:0 0 4px;}} .sub{{color:{INK['secondary']};font-size:13px;margin-bottom:20px;}}
  .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px;}}
  .tile{{background:{INK['surface']};border:1px solid rgba(11,11,11,.10);border-radius:8px;padding:14px 16px;}}
  .tile .k{{font-size:12px;color:{INK['secondary']};}} .tile .v{{font-size:26px;font-weight:600;margin:4px 0 2px;}}
  .tile .s{{font-size:12px;color:{INK['muted']};}}
  .card{{background:{INK['surface']};border:1px solid rgba(11,11,11,.10);border-radius:8px;padding:8px 8px 4px;margin-bottom:16px;overflow-x:auto;}}
  table{{border-collapse:collapse;width:100%;font-size:13px;}} th,td{{text-align:left;padding:6px 10px;border-bottom:1px solid {INK['grid']};}}
  th{{color:{INK['secondary']};font-weight:500;}} td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;}}
  .nw{{white-space:nowrap;}}
  .sw{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:8px;vertical-align:middle;}}
  details summary{{cursor:pointer;color:{INK['secondary']};font-size:13px;padding:6px 0;}}
</style></head><body><div class="wrap">
<h1>{page_title}</h1>
<div class="sub">{sub}</div>
<div class="kpis">{kpi_html}</div>
<div class="card">{parts[0]}</div>
<div class="card">{parts[1]}</div>
<div class="card">{parts[2]}</div>
<div class="card">{parts[3]}</div>
<div class="card"><table><thead><tr><th>分类</th><th class="num">工时 (h)</th></tr></thead><tbody>{cat_rows}
<tr><td><b>合计</b></td><td class="num"><b>{fmt_h(total)}</b></td></tr></tbody></table></div>
<details{" open" if external else ""}><summary>{detail_title}</summary><div class="card"><table><thead>{detail_head}</thead><tbody>{detail_rows}</tbody></table></div></details>
</div></body></html>"""
    with open(os.path.join(out, fname), "w", encoding="utf-8") as fh:
        fh.write(html)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    tc.add_project_arg(ap)
    ap.add_argument("--ledger", help="override the ledger path from timesheet.json")
    ap.add_argument("--out", help="override report_out from timesheet.json")
    ap.add_argument("--uplift", nargs=2, type=float, help="tier-C low/high multipliers on logged hours (default from config)")
    ap.add_argument("--external-ledger", help="override external_ledger from timesheet.json")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--no-html", action="store_true")
    ap.add_argument("--no-external", action="store_true", help="skip the external HTML page")
    ap.add_argument("--csv", action="store_true", help="also regenerate external_csv from the external table")
    ap.add_argument("--csv-only", action="store_true", help="only regenerate external_csv; no charts")
    args = ap.parse_args()
    cfg = tc.load(args.project)
    if args.ledger:
        cfg["ledger"] = os.path.abspath(args.ledger)
    if args.external_ledger:
        cfg["external_ledger"] = os.path.abspath(args.external_ledger)
    out = os.path.abspath(args.out) if args.out else cfg["report_out"]
    uplift = tuple(args.uplift) if args.uplift else tuple(cfg["uplift"])
    if len(cfg["report_categories"]) > len(LIGHT):
        sys.exit(f"report_categories has {len(cfg['report_categories'])} entries; the palette supports {len(LIGHT)}")
    if args.csv_only:
        write_external_csv(cfg)
        return 0

    rows = parse_ledger(cfg)
    os.makedirs(out, exist_ok=True)
    if not args.no_png:
        render_png(cfg, rows, out, uplift)
    external_ok = bool(cfg["external_prefix"]) and os.path.exists(cfg["external_ledger"]) and not args.no_external
    if not args.no_html:
        render_html(cfg, rows, out, uplift)
        if external_ok:
            render_html(cfg, rows, out, uplift, tasks=parse_external(cfg))
    if external_ok:
        ext_total = sum(t["hours"] for t in parse_external(cfg))
        led_total = sum(r["hours"] for r in rows)
        if abs(ext_total - led_total) > 1e-6:
            print(f"[warn] external task table {ext_total:g} h != ledger {led_total:g} h", file=sys.stderr)
    if args.csv:
        write_external_csv(cfg)
    weeks, by_week, by_day, by_cat, logged, manual = aggregate(cfg, rows)
    print(f"{len(rows)} rows, {len(by_day)} days, logged {logged:g} h + manual {manual:g} h = {logged + manual:g} h -> {tc.rel(cfg, out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
