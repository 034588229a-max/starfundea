/**
 * 試營運店家資料（PilotData.gs）：三多屋國際事業有限公司（品牌「三多屋爸爸嘴」）。
 * 在 Apps Script 編輯器選函式 createPilotSanduowu 按「執行」，就會一次建完：
 *   店家與免驗證碼登入 → 店家資料與配色 → 菜單 21 項（24 格）→ 桌號 QR → Wi-Fi 卡
 *   → 班別範本與員工建檔連結 → 固定廠商（記帳用）→ 試營運公告。
 * 已經有資料的項目不會覆蓋店主改過的內容（桌號、Wi-Fi、廠商、員工都是「沒有才建」）。
 * 菜單依店家提供的兩張菜單照片整理；看不清楚或要店主確認的地方在 PILOT_TODO 列出。
 * 登入：統編 27323989、密碼 Test27323989（試營運用，驗證碼隨便填）；正式上線前請改密碼並執行 disableTestMode()。
 */
var PILOT_SANDUOWU = {
  company: '三多屋國際事業有限公司', owner: '李奕立', taxId: '27323989', password: 'Test27323989',
  cfg: {
    name: '三多屋爸爸嘴', tagline: '新鮮・專業・美食',
    address: '臺北市大同區太原路19號1樓', addrCity: '臺北市', addrDist: '大同區', addrRoad: '太原路19號1樓',
    phone: '02-2555-7708', phoneLandArea: '02', phoneLandNum: '25557708',
    hours: '週二至週日 11:00–20:00', closedText: '公休：週一', openDays: [2, 3, 4, 5, 6, 0],
    channels: ['現場／電話點餐'], minDays: 1,
    primary: '#5B3A24', accent: '#D9622B'
  },
  shop: { name: '三多屋爸爸嘴', tagline: '新鮮・專業・美食', hours: '週二至週日 11:00–20:00', primary: '#5B3A24', accent: '#D9622B', chips: '每份附味噌湯（麵食除外）；每人低消 150 元' },
  draft: {
    sections: [
      { title: '熟食', columns: ['價格'], note: '每份附一碗味噌湯', items: [
        { name: '1 三多屋特餐（炒飯＋鯖魚）', prices: [250], star: true, tags: ['fish'], side: '三多屋名物' },
        { name: '2 鹽烤鮭魚親子丼', prices: [250], tags: ['fish'], side: '限量' },
        { name: '3 櫻花蝦鮭魚炒飯（XO醬）', prices: [150], tags: ['fish', 'shellfish'] } ] },
      { title: '蓋飯', columns: ['價格'], note: '每份附一碗味噌湯', items: [
        { name: '4 超級豪華鮪魚蓋飯', prices: [880], star: true, tags: ['fish'] },
        { name: '5 豪華蓋飯', prices: [480], tags: ['fish', 'shellfish'] },
        { name: '6 生魚片蓋飯', prices: [250], tags: ['fish'] },
        { name: '7 全鮭蓋飯', prices: [null], tags: ['fish'], side: '限量' } ] },
      { title: '壽司', columns: ['價格'], note: '每份附一碗味噌湯', items: [
        { name: '8 新鮮散壽司', prices: [200], tags: ['fish'], side: '限量' },
        { name: '9 綜合握壽司', prices: [200], tags: ['fish'], side: '限量' },
        { name: '10 鮭魚卵蓋飯', prices: [350], tags: ['fish'] } ] },
      { title: '麵食', columns: ['價格'], note: '此區不附湯', items: [
        { name: '11 白蝦拉麵', prices: [250], tags: ['shellfish', 'gluten'] },
        { name: '12 龍膽石斑拉麵', prices: [280], tags: ['fish', 'gluten'] },
        { name: '13 鰻魚飯／麵', prices: [390], tags: ['fish'] } ] },
      { title: '小菜', columns: ['價格'], note: '圖片僅供參考，以實際供應為準・每人低消 150 元', items: [
        { name: '14 現切綜合生魚片 小盤 A', prices: [200], tags: ['fish'] },
        { name: '14 現切綜合生魚片 小盤 B', prices: [300], tags: ['fish'] },
        { name: '14 現切綜合生魚片 大盤 A', prices: [500], tags: ['fish'] },
        { name: '14 現切綜合生魚片 大盤 B', prices: [1000], tags: ['fish'] },
        { name: '15 鹽烤挪威鯖魚', prices: [130], tags: ['fish'] },
        { name: '16 鹽烤鮭魚頭', prices: [300], tags: ['fish'], side: '限量' },
        { name: '17 辣味螺肉', prices: [200], tags: ['spicy'] },
        { name: '18 龍蝦沙拉', prices: [200], tags: ['shellfish'] },
        { name: '19 螺肉沙拉雙拼', prices: [200] },
        { name: '20 鱈魚肝', prices: [150], tags: ['fish'] },
        { name: '21 味噌湯', prices: [50], tags: ['soy'] } ] }
    ], warnings: []
  },
  /* 桌號 QR：掃了就看到這家店的電子菜單。每張網址後面加 #編號，才不會被判定成重複網址。桌數請店主確認。 */
  tables: { count: 12, wait: 1, take: 1 },
  /* Wi-Fi 卡：全部是範例值，請店主改成店內實際的名稱與密碼（改了之後要重新輸出卡片） */
  wifi: {
    ssid: 'TOCONFIRM-WIFI', pass: '請改成店內WiFi密碼', enc: 'WPA', hidden: false,
    title: '免費 Wi-Fi', note: '範例值：請改成店內實際的 Wi-Fi 名稱與密碼', showPass: true, layout: 'a6x4'
  },
  /* 班別範本（依營業時間 11:00–20:00 推算，含備料與收尾）。實際班別請店主確認。 */
  shifts: [
    { n: '早班', s: '10:00', e: '16:00' },
    { n: '晚班', s: '15:30', e: '20:30' },
    { n: '全天', s: '10:00', e: '20:30' }
  ],
  grace: 5,
  /* 員工：不代填真實姓名與 PIN。改成建立「待填寫」名額＋一次性建檔連結，員工自己填姓名、手機、PIN。 */
  invites: ['內場夥伴（待填寫）', '外場夥伴（待填寫）'],
  /* 固定廠商：記帳點一下就帶出分類與常用金額。名稱是範例，請店主改成實際的廠商名。 */
  vendors: [
    { name: '魚貨（待改）', cat: '進貨：食材', pay: '現金', quick: [1000, 2000, 3000, 5000] },
    { name: '蔬果（待改）', cat: '進貨：食材', pay: '現金', quick: [300, 500, 1000] },
    { name: '米與乾貨（待改）', cat: '進貨：食材', pay: '現金', quick: [500, 1000, 2000] },
    { name: '飲料（待改）', cat: '進貨：飲料', pay: '現金', quick: [500, 1000, 2000] },
    { name: '包材（待改）', cat: '進貨：包材', pay: '現金', quick: [300, 500, 1000] }
  ],
  /* 公告：試營運公告，勾「顧客頁顯示」，顧客掃桌號 QR 就看得到 */
  notices: [
    { title: '試營運公告', show: true, start: '', end: '', content: {
      cat: 'general', tag: '試營運',
      title: '三多屋爸爸嘴\n**試營運中**',
      lead: '魚貨每日新鮮直送，餐點都是現點現做，出餐需要一點時間，謝謝您的等候。',
      hiLabel: '營 業 時 間', hiBig: '11:00 – 20:00', hiSub: '週二至週日', hiNote: '每週一公休',
      info: '每份附一碗味噌湯（麵食除外）\n每人低消 150 元\n部分品項限量，售完為止',
      detTitle: '', det: '', q1Title: '', q1Url: '', q1Text: '', q2Label: '', q2Url: '',
      foot: '試營運期間部分品項與價格可能調整，以店內公告為準。', end: '謝謝大家的支持！'
    } }
  ]
};
/* 照片看不清楚、需要店家確認的地方（前 6 項來自菜單照片，後面是基本資料的範例值） */
var PILOT_TODO = [
  '14 現切綜合生魚片：照片上是「小 200/300、大 500/1000」，已拆成 小盤 A／B、大盤 A／B 四個品項，請確認各自的內容與價格',
  '7 全鮭蓋飯：價格被遮住，先留空白，請補上',
  '21 味噌湯：價格被手指遮住一部分，先填 50，請確認',
  '13 鰻魚：照片寫「鰻魚 Eel Rice／うなぎ麵」，先命名為「鰻魚飯／麵」，請確認是飯還是麵',
  '「限量」標示：2、7、8、9、16 有「限量」標籤，先寫在附餐說明欄',
  '過敏原標示是依品名推測（魚、甲殼、麩質、辣），請店家確認',
  '桌號：先建 12 桌＋候位區＋外帶自取，請確認店內實際桌數（在「店家工具→桌號 QR」增減）',
  'Wi-Fi：名稱與密碼是範例值（TOCONFIRM-WIFI），請改成店內實際的，再輸出 Wi-Fi 卡',
  '班別：早班 10:00–16:00、晚班 15:30–20:30、全天 10:00–20:30 是推算的，請確認實際上下班時間',
  '固定廠商：五家都是「（待改）」的範例名稱，請改成實際廠商名與常用金額',
  'Logo：還沒有圖檔，請店主上傳 800px 以上的正方形圖（「店家工具→Logo」）',
  '通知 Email：店家資料裡的「通知信箱」還是空的，填了才會收到請假／員工建檔的通知',
  'LINE 官方帳號 ID、Google 地圖網址：還沒填，填了名片與顧客頁才會出現對應按鈕'
];

/** 在 Apps Script 編輯器執行：建立三多屋試營運店家（可重複執行） */
function createPilotSanduowu() { return seedPilotShop_(PILOT_SANDUOWU); }

function seedPilotShop_(spec) {
  var id = seedTestShop(spec.taxId, spec.password, spec.company);       /* 建立或重設店家、開啟免驗證碼、建好試算表與資料夾 */
  var s = shopById_(id);
  s.owner = spec.owner; saveShop_(s, ['owner']);
  var r = withShop_(s, function () {
    cfgSave_(spec.cfg);                                                 /* 店家資料（走跟「店家設定」一樣的檢查） */
    themeSave_({ primary: spec.cfg.primary, accent: spec.cfg.accent });  /* 品牌主色與輔色 */
    tShopSave_(spec.shop);                                              /* 海報／菜單頁用的店名、標語、底部標籤 */
    var menu = menuApplyDraft_(spec.draft, { update: true, label: '試營運匯入菜單' });
    var b = seedPilotBasics_(spec);
    b.added = menu.added;
    return b;
  });
  Logger.log(pilotReport_(spec, id, r));
  return { id: id, added: r.added, basics: r };
}

/** 桌號 QR 清單：全部指向這家店的電子菜單，用 # 編號區分 */
function seedPilotTables_(t) {
  t = t || {};
  var base = tWebUrl_();
  if (!base) throw new Error('WEB_APP_URL 還沒設定，沒辦法產生桌號 QR 網址');
  var menu = base + '?s=' + CTX.shopId + '&p=menu', out = [], i;
  for (i = 1; i <= (t.count || 0); i++) out.push({ type: 'table', name: '第 ' + i + ' 桌', url: menu + '#t' + ('0' + i).slice(-2) });
  for (i = 1; i <= (t.wait || 0); i++) out.push({ type: 'wait', name: (t.wait > 1 ? '候位區 ' + i : '候位區'), url: menu + '#w' + i });
  for (i = 1; i <= (t.take || 0); i++) out.push({ type: 'take', name: (t.take > 1 ? '外帶自取 ' + i : '外帶自取'), url: menu + '#o' + i });
  return out;
}

/**
 * 補齊「開門做生意」要的其他基本資料。已經有資料的項目一律跳過，不會蓋掉店主改過的內容。
 * 必須在 withShop_ 裡面呼叫（需要 CTX）。
 */
function seedPilotBasics_(spec) {
  var out = { tables: 0, wifi: 0, shifts: 0, invites: 0, inviteUrls: [], vendors: 0, notices: 0, joinUrl: '', skipped: [] };

  /* 桌號 QR */
  var cur = tGetJson_('t_tables', []) || [];
  if (cur.length) out.skipped.push('桌號（已有 ' + cur.length + ' 筆）');
  else {
    var list = seedPilotTables_(spec.tables);
    tTablesSave_(list, { layout: 'a6x4', headline: {} });
    out.tables = list.length;
  }

  /* Wi-Fi 卡 */
  if (tGetJson_('t_wifi', null)) out.skipped.push('Wi-Fi（已設定過）');
  else { tWifiSave_(spec.wifi); out.wifi = 1; }

  /* 班別範本（店主自己調過就不動） */
  if (tGetJson_('st_cfg', null)) out.skipped.push('班別範本（已設定過）');
  else { stCfgSave_({ shifts: spec.shifts, grace: spec.grace }); out.shifts = spec.shifts.length; }

  /* 員工：通用建檔連結＋待填寫名額（不代填姓名與 PIN） */
  out.joinUrl = stJoinSet_(true, false).url;
  var have = {};
  stEmps_().forEach(function (e) { have[e.name] = 1; });
  (spec.invites || []).forEach(function (label) {
    if (have[label]) { out.skipped.push('員工「' + label + '」（已存在）'); return; }
    var inv = stEmpInviteForm_(label, '', '');
    out.invites++;
    out.inviteUrls.push(label + '：' + inv.url + '（' + inv.expires + ' 前有效，只能用一次）');
  });

  /* 固定廠商 */
  var hv = {};
  lgVendors_(true).forEach(function (v) { hv[v.name] = 1; });
  (spec.vendors || []).forEach(function (v) {
    if (hv[v.name]) { out.skipped.push('廠商「' + v.name + '」（已存在）'); return; }
    lgVendorSave_(v); out.vendors++;
  });

  /* 公告：同名公告就更新同一筆，不會一直新增 */
  var ex = {};
  tListNotices_(50).forEach(function (n) { if (!ex[n.title]) ex[n.title] = n.id; });
  (spec.notices || []).forEach(function (n) {
    tNoticeSave_({ id: ex[n.title] || '', title: n.title, start: n.start || '', end: n.end || '', show: n.show === true, content: n.content });
    out.notices++;
  });

  props_().setProperty('onboarded', '1');     /* 基本資料已經建好，店主登入直接進主畫面，不用再走設定精靈 */
  return out;
}

/** 執行後印在 Apps Script 執行紀錄的報告（店主照著看就知道哪些還要自己補） */
function pilotReport_(spec, id, r) {
  var L = [];
  L.push('試營運店家已建立：' + id + '（' + spec.company + '，統編 ' + spec.taxId + '）');
  L.push('登入：統編 ' + spec.taxId + '、密碼 ' + spec.password + '，驗證碼隨便填');
  L.push('');
  L.push('【這次建了什麼】');
  L.push('菜單品項：新增 ' + r.added + ' 個');
  L.push('桌號 QR：' + r.tables + ' 張');
  L.push('Wi-Fi 卡：' + (r.wifi ? '已建（範例值，請改）' : '略過'));
  L.push('班別範本：' + r.shifts + ' 種');
  L.push('固定廠商：' + r.vendors + ' 家（範例名稱，請改）');
  L.push('公告：' + r.notices + ' 則');
  L.push('員工建檔名額：' + r.invites + ' 個');
  if (r.joinUrl) L.push('通用建檔連結（給所有新員工，填完要店主核准）：' + r.joinUrl);
  r.inviteUrls.forEach(function (x) { L.push('個人建檔連結　' + x); });
  if (r.skipped.length) { L.push(''); L.push('【已經有資料、這次跳過】'); r.skipped.forEach(function (x) { L.push('・' + x); }); }
  L.push('');
  L.push('【請店主確認／補齊】');
  PILOT_TODO.forEach(function (x, i) { L.push((i + 1) + '. ' + x); });
  return L.join('\n');
}
