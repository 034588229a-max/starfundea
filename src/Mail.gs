/**
 * 品牌信件（Mail.gs）：所有系統信都經過 mailSend_，同時寄 HTML 與純文字。規範見技能 email-design。
   兩種身分：
   - brand:'sfd'  星樂創意寄給店主（深藍＋琥珀＋官方 Logo）
   - brand:'shop' 店家寄給員工／應徵者（店家名稱與主色，頁尾註明由 SFD 系統代寄）
   信件技術限制：表格排版、樣式全部內嵌、寬 600px、Logo 用 PNG（cid 內嵌）、Gmail 不載入網路字體所以給後備字體、一定附純文字版。 */
var MK = {
  navy: '#0E1623', panel: '#17233A', amber: '#FFB534', amberText: '#B26A00', amberDeco: '#F29A00',
  slate: '#8FA0B8', paper: '#F5F2EA', sheet: '#F7F3EA', ink: '#1F2937', mute: '#556176', line: '#E6E0D2',
  font: "'Noto Sans TC','PingFang TC','Microsoft JhengHei','Heiti TC',Arial,sans-serif",
  num: "'Barlow Condensed','Arial Narrow','Roboto Condensed','Helvetica Neue',Arial,sans-serif"
};
function mkEsc_(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
/* 主色太亮時（白字看不清）退回深藍 */
function mkDark_(hex) {
  var m = /^#?([0-9a-f]{6})$/i.exec(String(hex || '')); if (!m) return MK.navy;
  var n = parseInt(m[1], 16), r = n >> 16 & 255, g = n >> 8 & 255, b = n & 255;
  function L(c) { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
  var lum = 0.2126 * L(r) + 0.7152 * L(g) + 0.0722 * L(b);
  return (1.05) / (lum + 0.05) >= 4.5 ? '#' + m[1] : MK.navy;
}
function mkBtn_(text, url, bg, fg) {
  return '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 4px"><tr><td bgcolor="' + bg + '" style="border-radius:14px;background:' + bg + '">' +
    '<a href="' + mkEsc_(url) + '" style="display:inline-block;padding:0 28px;line-height:52px;min-width:180px;text-align:center;font-family:' + MK.font + ';font-size:17px;font-weight:700;color:' + fg + ';text-decoration:none;border-radius:14px">' + mkEsc_(text) + '</a></td></tr></table>';
}
function mkRows_(rows) {
  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0 4px;background:' + MK.sheet + ';border-radius:14px">' +
    rows.map(function (r, i) {
      return '<tr><td style="padding:' + (i ? '0' : '14px') + ' 18px ' + (i === rows.length - 1 ? '14px' : '10px') + ' 18px;font-family:' + MK.font + ';font-size:14px;color:' + MK.mute + ';width:30%;vertical-align:top;white-space:nowrap">' + mkEsc_(r[0]) + '</td>' +
        '<td style="padding:' + (i ? '0' : '14px') + ' 18px ' + (i === rows.length - 1 ? '14px' : '10px') + ' 0;font-family:' + (r[2] ? MK.num : MK.font) + ';font-size:' + (r[2] ? '17px' : '16px') + ';font-weight:700;color:' + MK.navy + ';vertical-align:top' + (r[2] ? ';white-space:nowrap' : '') + '">' + mkEsc_(r[1]) + '</td></tr>';
    }).join('') + '</table>';
}
function mkSteps_(steps, dot) {
  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0 4px">' + steps.map(function (s, i) {
    return '<tr><td style="width:40px;padding:0 0 12px;vertical-align:top"><div style="width:28px;height:28px;border-radius:14px;background:' + dot + ';color:#fff;font-family:' + MK.num + ';font-weight:700;font-size:16px;line-height:28px;text-align:center">' + (i + 1) + '</div></td>' +
      '<td style="padding:3px 0 12px;font-family:' + MK.font + ';font-size:16px;line-height:1.6;color:' + MK.ink + '">' + s + '</td></tr>';
  }).join('') + '</table>';
}
function mkTable_(head, rows, foot) {
  var th = 'padding:10px 12px;font-family:' + MK.font + ';font-size:13px;color:' + MK.mute + ';text-align:left;border-bottom:1.5px solid ' + MK.line;
  var td = 'padding:11px 12px;font-family:' + MK.font + ';font-size:15px;color:' + MK.ink + ';border-bottom:1px solid ' + MK.line;
  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0 4px;border-collapse:collapse">' +
    '<tr>' + head.map(function (h) { return '<th style="' + th + '">' + mkEsc_(h) + '</th>'; }).join('') + '</tr>' +
    rows.map(function (r) { return '<tr>' + r.map(function (c, i) { return '<td style="' + td + (i === 1 ? ';font-family:' + MK.num + ';font-size:17px;font-weight:700;color:' + MK.navy : '') + (r.off ? ';color:#9AA3B2' : '') + '">' + mkEsc_(c) + '</td>'; }).join('') + '</tr>'; }).join('') +
    (foot ? '<tr><td colspan="' + head.length + '" style="padding:12px;font-family:' + MK.font + ';font-size:15px;font-weight:700;color:' + MK.navy + '">' + mkEsc_(foot) + '</td></tr>' : '') + '</table>';
}

/* o = { brand, shop:{name, primary, accent, phone}, preheader, eyebrow, title, blocks:[html…], why } */
function mailHtml_(o) {
  var shopMail = o.brand === 'shop', s = o.shop || {};
  var head = shopMail ? mkDark_(s.primary) : MK.navy;
  var accent = shopMail ? (s.accent || MK.amber) : MK.amber;
  var logo = shopMail
    ? (s.logoCid ? '<img src="cid:' + s.logoCid + '" height="40" alt="' + mkEsc_(s.name) + '" style="display:block;height:40px;width:auto;border:0">' :
      '<div style="font-family:' + MK.font + ';font-size:20px;font-weight:900;color:#ffffff;letter-spacing:.04em">' + mkEsc_(s.name) + '</div>')
    : '<img src="cid:sfdLogo" width="168" height="30" alt="星樂創意 StarFunDea" style="display:block;width:168px;height:auto;border:0">';
  var foot = shopMail
    ? mkEsc_(s.name) + (s.phone ? '｜' + mkEsc_(s.phone) : '') + '<br><span style="color:#8A93A3">這封信由星樂創意 SFD 系統代「' + mkEsc_(s.name) + '」寄出。有問題請直接聯絡店家。</span>'
    : '<img src="cid:sfdMark" width="22" height="21" alt="" style="vertical-align:middle;border:0;margin-right:6px">星樂創意 StarFunDea｜把點子，走成亮點。<br><span style="color:#8A93A3">這是系統自動寄出的信，請不要直接回覆。</span>';
  return '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light">' +
    '<style>@media (max-width:620px){.px{padding-left:20px!important;padding-right:20px!important}.ttl{font-size:23px!important}}</style></head>' +
    '<body style="margin:0;padding:0;background:' + MK.paper + '">' +
    '<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">' + mkEsc_(o.preheader || '') + '</div>' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="' + MK.paper + '" style="background:' + MK.paper + '"><tr><td align="center" style="padding:24px 10px">' +
    '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px">' +
    '<tr><td class="px" bgcolor="' + head + '" style="background:' + head + ';border-radius:20px 20px 0 0;padding:26px 32px 24px">' + logo +
    '<div style="margin-top:26px;font-family:' + MK.num + ';font-size:14px;font-weight:700;letter-spacing:.2em;color:' + (shopMail ? '#DCE4EE' : MK.amber) + '">' + mkEsc_(o.eyebrow || '') + '</div>' +
    '<div class="ttl" style="margin-top:6px;font-family:' + MK.font + ';font-size:26px;line-height:1.35;font-weight:900;color:#ffffff">' + mkEsc_(o.title) + '</div>' +
    '<div style="margin-top:16px;width:72px;border-top:2px dashed ' + accent + ';font-size:0;line-height:0">&nbsp;</div></td></tr>' +
    '<tr><td class="px" bgcolor="#ffffff" style="background:#ffffff;border-radius:0 0 20px 20px;padding:28px 32px 32px;border:1.5px solid ' + MK.line + ';border-top:0">' +
    o.blocks.join('') + '</td></tr>' +
    '<tr><td class="px" style="padding:20px 32px 6px;font-family:' + MK.font + ';font-size:13px;line-height:1.7;color:' + MK.mute + '">' + foot +
    (o.why ? '<br><span style="color:#8A93A3">' + mkEsc_(o.why) + '</span>' : '') + '</td></tr>' +
    '</table></td></tr></table></body></html>';
}
function mkP_(t) { return '<p style="margin:0 0 14px;font-family:' + MK.font + ';font-size:16px;line-height:1.75;color:' + MK.ink + '">' + t + '</p>'; }
function mkNote_(t) { return '<div style="margin:20px 0 0;padding:12px 16px;background:#FFF6E3;border-left:4px solid ' + MK.amberDeco + ';border-radius:8px;font-family:' + MK.font + ';font-size:14px;line-height:1.7;color:#5A4300">' + t + '</div>'; }
function mkCode_(code, sub) {
  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:6px 0 4px"><tr><td align="center" bgcolor="' + MK.navy + '" style="background:' + MK.navy + ';border-radius:16px;padding:22px 12px 18px">' +
    '<div style="font-family:' + MK.num + ';font-size:44px;font-weight:700;letter-spacing:12px;color:' + MK.amber + ';padding-left:12px">' + mkEsc_(code) + '</div>' +
    '<div style="margin-top:6px;font-family:' + MK.font + ';font-size:13px;color:' + MK.slate + '">' + mkEsc_(sub) + '</div></td></tr></table>';
}
function mkBig_(num, unit, sub) {
  return '<div style="margin:4px 0 6px;font-family:' + MK.num + ';font-size:64px;line-height:1;font-weight:800;color:' + MK.navy + '">' + mkEsc_(num) + '<span style="font-family:' + MK.font + ';font-size:22px;font-weight:700;margin-left:6px">' + mkEsc_(unit) + '</span></div>' +
    '<div style="font-family:' + MK.font + ';font-size:14px;color:' + MK.mute + ';margin-bottom:6px">' + mkEsc_(sub) + '</div>';
}

/* 按鈕文字顏色：底色夠深用白字，否則用深藍字（對比 4.5:1 以上） */
function mkOn_(hex) { return mkDark_(hex) === MK.navy && String(hex).toUpperCase() !== MK.navy.toUpperCase() ? MK.navy : '#ffffff'; }
function mkList_(items) {
  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 14px">' + items.map(function (t) {
    return '<tr><td style="width:22px;vertical-align:top;padding:9px 0 0"><div style="width:8px;height:8px;background:' + MK.amberDeco + ';transform:rotate(45deg)"></div></td><td style="padding:2px 0 6px;font-family:' + MK.font + ';font-size:16px;line-height:1.7;color:' + MK.ink + '">' + t + '</td></tr>';
  }).join('') + '</table>';
}
function mkLink_(t, url) { return '<p style="margin:10px 0 0;font-family:' + MK.font + ';font-size:13px;line-height:1.6;color:' + MK.mute + ';word-break:break-all">' + mkEsc_(t) + '<br><a href="' + mkEsc_(url) + '" style="color:' + MK.mute + '">' + mkEsc_(url) + '</a></p>'; }
/* 純文字段落轉 HTML：保留換行、網址可點 */
function mkTxt_(s) {
  return mkEsc_(s).replace(/\n/g, '<br>').replace(/(https?:\/\/[^\s<]+)/g, function (u) { return '<a href="' + u + '" style="color:' + MK.navy + ';word-break:break-all">' + u + '</a>'; });
}

var MAIL_LOGO_B64 = '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';
var MAIL_MARK_B64 = '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';
function mailImgs_() {
  return { sfdLogo: Utilities.newBlob(Utilities.base64Decode(MAIL_LOGO_B64), 'image/png', 'starfundea-logo.png'), sfdMark: Utilities.newBlob(Utilities.base64Decode(MAIL_MARK_B64), 'image/png', 'starfundea-mark.png') };
}
/* 店家代寄用的店家資料（名稱、主色、強調色、電話） */
function mailShop_() {
  try { var c = shopCfg_(); return { name: c.name || '本店', primary: c.primary, accent: c.accent, phone: c.phone || c.phoneMobile || '' }; }
  catch (e) { return { name: '本店' }; }
}
var MAIL_EYEBROW = [[/驗證碼/, 'VERIFICATION'], [/開通|歡迎/, 'WELCOME'], [/收到款項|付款|收款/, 'PAYMENT'], [/提醒/, 'REMINDER'], [/班表|排班/, 'SCHEDULE'], [/請假|特休/, 'LEAVE'], [/面試|應徵/, 'HIRING'], [/打卡/, 'CLOCK'], [/交接/, 'HANDOVER'], [/叫貨/, 'ORDERING'], [/邀請/, 'INVITATION'], [/菜單/, 'MENU'], [/員工資料/, 'TEAM']];
/* 沒有指定版型時：用主旨與純文字自動排版。第一個網址變成按鈕，「・」開頭變清單 */
function mailAuto_(subject, text, brand, btnText) {
  var title = String(subject || '').replace(/^【[^】]*】\s*/, ''), eb = 'NOTICE', blocks = [], used = false;
  MAIL_EYEBROW.some(function (p) { if (p[0].test(subject)) { eb = p[1]; return true; } return false; });
  String(text || '').replace(/\r/g, '').split(/\n{2,}/).forEach(function (para) {
    para = para.replace(/^\n+|\n+$/g, ''); if (!para) return;
    var code = /驗證碼：(\d{6})/.exec(para);
    if (code) { blocks.push(mkCode_(code[1], '5 分鐘內有效，只能用一次')); return; }
    var lines = para.split('\n'), url = null;
    if (!used) lines.forEach(function (l) { var m = /^(?:[^\s]*[：:]\s*)?(https?:\/\/\S+)$/.exec(l.trim()); if (m && !url) url = m[1]; });
    if (url) {
      var rest = lines.filter(function (l) { return l.indexOf(url) < 0; }).join('\n').replace(/[：:]\s*$/, '');
      if (rest) blocks.push(mkP_(mkTxt_(rest)));
      blocks.push(mkBtn_(btnText || '打開連結', url, brand === 'shop' ? MK.navy : MK.amber, brand === 'shop' ? '#ffffff' : MK.navy));
      used = true; return;
    }
    var bul = lines.filter(function (l) { return /^\s*[・•\-]\s*/.test(l); });
    if (bul.length && bul.length === lines.length) { blocks.push(mkList_(bul.map(function (l) { return mkTxt_(l.replace(/^\s*[・•\-]\s*/, '')); }))); return; }
    if (bul.length && bul.length === lines.length - 1 && !/^\s*[・•\-]/.test(lines[0])) { blocks.push(mkP_(mkTxt_(lines[0]))); blocks.push(mkList_(lines.slice(1).map(function (l) { return mkTxt_(l.replace(/^\s*[・•\-]\s*/, '')); }))); return; }
    blocks.push(mkP_(mkTxt_(para)));
  });
  return { brand: brand || 'sfd', eyebrow: eb, title: title, preheader: String(text || '').replace(/\s+/g, ' ').slice(0, 80), blocks: blocks };
}
/** 寄信的唯一入口。text＝純文字版（一定要有）；o＝版型（可省略，省略時自動排版）；
    x = { brand:'shop', shop, name, attachments, replyTo, btn }。版型出錯時照樣寄純文字，不讓寄信失敗 */
function mailSend_(to, subject, text, o, x) {
  x = x || {};
  var opt = { to: to, subject: subject, body: text };
  var brand = (o && o.brand) || x.brand || 'sfd';
  opt.name = x.name || (brand === 'shop' ? (((o && o.shop) || x.shop || mailShop_()).name + '（SFD 代寄）') : (typeof productName_ === 'function' ? productName_() : '星樂創意 StarFunDea'));
  try {
    var spec = o || mailAuto_(subject, text, brand, x.btn);
    spec.brand = brand;
    if (brand === 'shop' && !spec.shop) spec.shop = x.shop || mailShop_();
    opt.htmlBody = mailHtml_(spec);
    if (brand !== 'shop') opt.inlineImages = mailImgs_();
  } catch (e) { delete opt.htmlBody; delete opt.inlineImages; }
  if (x.attachments && x.attachments.length) opt.attachments = x.attachments;
  if (x.replyTo) opt.replyTo = x.replyTo;
  MailApp.sendEmail(opt);
}
