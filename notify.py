"""邮件推送模块 — 信号扫描/持仓日报 HTML 邮件发送。"""
import logging
import re
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config

logger = logging.getLogger(__name__)


# ── SMTP 发送 ──────────────────────────────────────────────────

def send_email(subject, html_body, to_addrs=None):
    """通过 SMTP 发送 HTML 邮件。成功返回 True，失败返回 False。"""
    if not config.SMTP_USER or not config.SMTP_PASS:
        logger.error("SMTP 凭据未配置，请设置 STOCK_SMTP_USER / STOCK_SMTP_PASS 环境变量")
        return False

    if to_addrs is None:
        to_addrs = [a.strip() for a in config.SMTP_TO.split(",") if a.strip()]
    if not to_addrs:
        logger.error("收件人未配置，请设置 STOCK_SMTP_TO 环境变量或传入 to_addrs")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM or config.SMTP_USER
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if config.SMTP_USE_TLS:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        server.login(config.SMTP_USER, config.SMTP_PASS)
        server.send_message(msg)
        server.quit()
        logger.info("邮件已发送: %s -> %s", subject, to_addrs)
        return True
    except Exception as e:
        logger.error("邮件发送失败: %s", e)
        return False


# ── HTML 构建 ───────────────────────────────────────────────────

def build_signal_html(df):
    """将 scan_signals 返回的 DataFrame 渲染为 HTML 邮件表格。"""
    buy_n = int((df["signal"] == "buy").sum())
    sell_n = int((df["signal"] == "sell").sum())
    hold_n = int((df["signal"] == "hold").sum())
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    rows_parts = []
    for _, r in df.iterrows():
        signal = r["signal"]
        color_map = {"buy": "#27ae60", "sell": "#e74c3c", "hold": "#f39c12"}
        label_map = {"buy": "买入", "sell": "卖出", "hold": "观望"}
        bg = color_map.get(signal, "#95a5a6")
        label = label_map.get(signal, signal)

        rows_parts.append(f"""
        <tr style="border-bottom:1px solid #eee">
            <td style="padding:8px 12px;font-weight:bold;color:{bg}">{label}</td>
            <td style="padding:8px 12px">{r['code']}</td>
            <td style="padding:8px 12px">{r.get('name','')}</td>
            <td style="padding:8px 12px;text-align:right">{r['price']:.2f}</td>
            <td style="padding:8px 12px">{r['trend']}</td>
            <td style="padding:8px 12px;text-align:right">{r['buy_price']:.2f}</td>
            <td style="padding:8px 12px;text-align:right">{r['take_profit']:.2f}</td>
            <td style="padding:8px 12px;text-align:right">{r['stop_loss']:.2f}</td>
            <td style="padding:8px 12px;text-align:right">{r['risk_reward']:.1f}</td>
            <td style="padding:8px 12px;color:#888;font-size:90%">{r.get('reason','')}</td>
        </tr>""")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:900px;margin:0 auto;padding:16px">
<h2 style="color:#2c3e50">股票信号扫描</h2>
<p style="color:#888">{now}</p>
<div style="margin:12px 0">
    <span style="display:inline-block;background:#27ae60;color:#fff;padding:4px 14px;border-radius:4px;margin-right:8px;font-weight:bold">买入 {buy_n}</span>
    <span style="display:inline-block;background:#e74c3c;color:#fff;padding:4px 14px;border-radius:4px;margin-right:8px;font-weight:bold">卖出 {sell_n}</span>
    <span style="display:inline-block;background:#f39c12;color:#fff;padding:4px 14px;border-radius:4px;font-weight:bold">观望 {hold_n}</span>
</div>
<table style="width:100%;border-collapse:collapse;font-size:14px">
<thead>
<tr style="background:#ecf0f1;text-align:left">
    <th style="padding:8px 12px">信号</th>
    <th style="padding:8px 12px">代码</th>
    <th style="padding:8px 12px">名称</th>
    <th style="padding:8px 12px;text-align:right">现价</th>
    <th style="padding:8px 12px">趋势</th>
    <th style="padding:8px 12px;text-align:right">建议买入</th>
    <th style="padding:8px 12px;text-align:right">止盈</th>
    <th style="padding:8px 12px;text-align:right">止损</th>
    <th style="padding:8px 12px;text-align:right">盈亏比</th>
    <th style="padding:8px 12px">理由</th>
</tr>
</thead>
<tbody>
{''.join(rows_parts)}
</tbody>
</table>
<p style="color:#bdc3c7;font-size:12px;margin-top:16px">由股票分析系统自动生成 | 回复无效</p>
</body>
</html>"""


def build_daily_report_html(positions, summary):
    """将持仓数据渲染为每日持仓报告 HTML 邮件。"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    total_pnl = summary.get("total_pnl", 0) or 0
    unrealized = summary.get("unrealized_pnl", 0) or 0
    pnl_color = "#27ae60" if total_pnl >= 0 else "#e74c3c"
    ureal_color = "#27ae60" if unrealized >= 0 else "#e74c3c"

    rows_parts = []
    if positions is not None and not positions.empty:
        for _, p in positions.iterrows():
            pnl = p.get("pnl", 0) or 0
            pnl_pct = p.get("pnl_pct", 0) or 0
            cp = p.get("current_price", 0) or 0
            pnl_c = "#27ae60" if pnl >= 0 else "#e74c3c"
            rows_parts.append(f"""
            <tr style="border-bottom:1px solid #eee">
                <td style="padding:8px 12px">{p['code']}</td>
                <td style="padding:8px 12px">{p.get('name','')}</td>
                <td style="padding:8px 12px;text-align:right">{p['buy_price']:.2f}</td>
                <td style="padding:8px 12px;text-align:right">{cp:.2f}</td>
                <td style="padding:8px 12px;text-align:right">{int(p['quantity'])}</td>
                <td style="padding:8px 12px;text-align:right;color:{pnl_c};font-weight:bold">{pnl:+,.2f}</td>
                <td style="padding:8px 12px;text-align:right;color:{pnl_c}">{pnl_pct:+,.2f}%</td>
            </tr>""")
    else:
        rows_parts.append(
            '<tr><td colspan="7" style="padding:16px;text-align:center;color:#888">当前无持仓</td></tr>'
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:800px;margin:0 auto;padding:16px">
<h2 style="color:#2c3e50">持仓日报</h2>
<p style="color:#888">{now}</p>

<table style="width:100%;border-collapse:collapse;margin:16px 0">
<tr>
    <td style="width:25%;padding:12px;background:#ecf0f1;border-radius:4px;text-align:center">
        <div style="font-size:12px;color:#888">累计交易</div>
        <div style="font-size:20px;font-weight:bold">{summary.get('total_trades',0)}</div>
    </td>
    <td style="width:25%;padding:12px;background:#ecf0f1;border-radius:4px;text-align:center">
        <div style="font-size:12px;color:#888">胜率</div>
        <div style="font-size:20px;font-weight:bold">{summary.get('win_rate',0)}%</div>
    </td>
    <td style="width:25%;padding:12px;background:#ecf0f1;border-radius:4px;text-align:center">
        <div style="font-size:12px;color:#888">已实现盈亏</div>
        <div style="font-size:20px;font-weight:bold;color:{pnl_color}">{total_pnl:+,.2f}</div>
    </td>
    <td style="width:25%;padding:12px;background:#ecf0f1;border-radius:4px;text-align:center">
        <div style="font-size:12px;color:#888">未实现盈亏</div>
        <div style="font-size:20px;font-weight:bold;color:{ureal_color}">{unrealized:+,.2f}</div>
    </td>
</tr>
</table>

<h3 style="color:#2c3e50;margin-top:24px">当前持仓 ({summary.get('open_positions',0)}只)</h3>
<table style="width:100%;border-collapse:collapse;font-size:14px">
<thead>
<tr style="background:#ecf0f1;text-align:left">
    <th style="padding:8px 12px">代码</th>
    <th style="padding:8px 12px">名称</th>
    <th style="padding:8px 12px;text-align:right">买入价</th>
    <th style="padding:8px 12px;text-align:right">现价</th>
    <th style="padding:8px 12px;text-align:right">数量</th>
    <th style="padding:8px 12px;text-align:right">浮动盈亏</th>
    <th style="padding:8px 12px;text-align:right">盈亏%</th>
</tr>
</thead>
<tbody>
{''.join(rows_parts)}
</tbody>
</table>

<p style="color:#bdc3c7;font-size:12px;margin-top:16px">由股票分析系统自动生成 | 回复无效</p>
</body>
</html>"""


def _strip_html(html, max_len=500):
    """去除 HTML 标签，用于 CLI 预览。"""
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = text.strip()
    if len(text) > max_len:
        text = text[:max_len] + " ..."
    return text
