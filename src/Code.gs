/**
 * 弘林早午餐｜菜單價格系統（Google Apps Script）
 * ------------------------------------------------------------
 * 放在：價格試算表 → 擴充功能 → Apps Script → Code.gs（整份貼上取代）
 * 另外新增一個 HTML 檔，名稱必須叫「Page」，貼上 Page.html 的內容。
 *
 * 功能
 *  - 試算表選單「🍳 弘林菜單」：建立／整理價格表、顯示菜單工具網址
 *  - 菜單工具網頁（部署成網頁應用程式）：手機改價格 → 直接寫回這份試算表
 *  - 產生 A3 菜單 PDF → 存到雲端硬碟資料夾，並記錄「上次印製」價格
 *  - 修改紀錄、印製紀錄兩個分頁自動記錄誰在什麼時候改了什麼
 */

const SHEET_NAME = '價格表';
const LOG_NAME = '修改紀錄';
const PRINT_NAME = '印製紀錄';
const FOLDER_NAME = '弘林早午餐_菜單PDF';
const HEAD = 5;   // 標題列在第 5 列，資料從第 6 列開始
const NCOL = 10;  // 代碼、分類、品項、規格、價格、上次印製、隱藏、推薦、附餐說明、標示
// 品項標示：過敏原（g:a）、飲食（g:d）、口味（g:f）。代碼存在價格表「標示」欄，用逗號分開
const TAG_DEFS = [
  { c: 'egg', t: '蛋', g: 'a' }, { c: 'milk', t: '奶', g: 'a' }, { c: 'peanut', t: '花生', g: 'a' }, { c: 'nut', t: '堅果', g: 'a' }, { c: 'gluten', t: '麩質', g: 'a' },
  { c: 'soy', t: '大豆', g: 'a' }, { c: 'shellfish', t: '甲殼', g: 'a' }, { c: 'fish', t: '魚', g: 'a' }, { c: 'sesame', t: '芝麻', g: 'a' },
  { c: 'veg', t: '素', g: 'd' }, { c: 'vegan', t: '純素', g: 'd' }, { c: 'spicy', t: '辣', g: 'f' }
];
const tagsClean_ = v => (Array.isArray(v) ? v : String(v || '').split(',')).map(x => String(x).trim()).filter((x, i, a) => TAG_DEFS.some(d => d.c === x) && a.indexOf(x) === i);
// 已從菜單拿掉的內建品項（建立／整理價格表時會移除）
const REMOVED_KEYS = ['single|炸物拼盤 MIX|0'];
// 換了分類的品項：新代碼 ← 舊代碼（沿用舊價格）
const KEY_ALIAS = { 'single|塔香蘿蔔糕牽絲乳酪炒蛋|0': 'teppan|塔香蘿蔔糕牽絲乳酪炒蛋|0' };

/* ================= 店家設定（可以自己改） ================= */
// 夥伴專用「菜單工具」的鑰匙：網址後面要加 ?staff=這串字 才能改價格。外洩時換一串新的即可。
const STAFF_KEY = 'hl7q2x9m';
// 你的正式部署網址（部署 → 管理部署作業 裡看得到）。換了新的部署作業就把這行改掉。
const WEB_APP_URL = 'https://script.google.com/macros/s/AKfycbwPhHfsMZ-cXx3r_YLv1hQsk6lf_isDBN8GXybqTb46qKceAC8CVXhhpi6WWPTAYGE/exec';
const LINKS = {
  order: 'https://iding.tw/store/b48e3778',           // 線上點餐網站
  line:  'https://lin.ee/VpY3C6z',                    // LINE 官方帳號
  map:   'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent('弘林早午餐 桃園市中壢區廣州路11號'),
  fb:    '',                                          // ← 請貼上臉書粉專網址，例如 https://www.facebook.com/xxxx
};
const CHANNELS = ['微碧', 'Uber Eats', 'foodpanda', '現場／電話／LINE 點餐'];   // 異常回報可選的點餐管道
const ISSUE_TYPES = ['少送／漏餐', '送錯品項', '餐點品質（冷掉、灑出、壓壞）', '口味或做法不對', '等太久／延遲', '包裝問題', '其他'];
const OPEN_DAYS = [1, 2, 5, 6, 0];   // 營業日：週一、二、五、六、日（週三、四公休）
const PREORDER_MIN_DAYS = 1;         // 預訂最早要提前幾天
const NOTIFY_EMAIL = '';             // 顧客送出表單時通知哪個信箱；空白＝寄給你自己（部署者）
const LOGO_FILE_ID = '127GzuunkHYpQ2q7W4TVhkJIMsTTMbMKS';   // 吉祥物圖片（雲端硬碟檔案 ID）；店家工具上傳的 Logo 會優先使用
const LOGO_NAME = '弘林logo';   // 把吉祥物圖片上傳到雲端硬碟，檔名以「弘林logo」開頭即可
const MENU_EMAIL = 'patricia3194299@yahoo.com.tw';   // 菜單 PDF「寄到 Email」預設收件人（工具裡可以改）
const CUSTOMER_SHEETS = {
  help:  { name: '異常回報', prefix: 'H', head: ['單號', '時間', '點餐管道', '訂單編號', '訂餐日期', '異常類型', '有問題的品項', '說明', '希望怎麼處理', '聯絡方式', '照片', '狀態', '處理人', '處理紀錄'] },
  wish:  { name: '許願池',   prefix: 'W', head: ['單號', '時間', '想吃的品項', '說明', '聯絡方式（選填）', '狀態', '處理紀錄'] },
  knock: { name: '敲敲老闆', prefix: 'K', head: ['單號', '時間', '給誰', '訊息', '需要回覆', '聯絡方式', '狀態', '處理紀錄'] },
  pre:   { name: '預訂單',   prefix: 'R', head: ['單號', '送出時間', '取餐日期', '取餐時間', '姓名', '電話', '品項明細', '總件數', '預估金額', '備註', '狀態', '處理紀錄'] },
};

// [代碼, 分類, 品項, 規格, 預設價格, 店長推薦(1)]；代碼要跟菜單工具一致，請勿修改
const ITEMS = [
  ["chao|辣培根薯泥起司蛋堡套餐|0", "超值特餐", "辣培根薯泥起司蛋堡套餐", "", 150, 1],
  ["chao|炸物拼盤套餐|0", "超值特餐", "炸物拼盤套餐", "", 160, 0],
  ["chao|花醬美式總匯套餐|0", "超值特餐", "花醬美式總匯套餐", "", 155, 0],
  ["chao|焗烤招牌厚片套餐|0", "超值特餐", "焗烤招牌厚片套餐", "", 160, 0],
  ["chao|起司辣肉醬麵肉蛋雙拼套餐|0", "超值特餐", "起司辣肉醬麵肉蛋雙拼套餐", "", 150, 1],
  ["chao|鮪魚玉米乳酪蛋餅|0", "超值特餐", "鮪魚玉米乳酪蛋餅", "", 155, 0],
  ["chao|塔香豬排起司蛋抓餅套餐|0", "超值特餐", "塔香豬排起司蛋抓餅套餐", "", 165, 1],
  ["jing|01 火腿起司蛋吐司|0", "經濟特餐", "01 火腿起司蛋吐司", "", 75, 0],
  ["jing|02 豬肉起司蛋堡|0", "經濟特餐", "02 豬肉起司蛋堡", "", 80, 1],
  ["jing|03 玉米起司蛋餅|0", "經濟特餐", "03 玉米起司蛋餅", "", 70, 0],
  ["jing|04 香雞起司蛋堡|0", "經濟特餐", "04 香雞起司蛋堡", "", 85, 0],
  ["jing|05 煎餃＋熱狗（2根）|0", "經濟特餐", "05 煎餃＋熱狗（2根）", "", 75, 1],
  ["jing|06 豬排蛋蔥抓餅|0", "經濟特餐", "06 豬排蛋蔥抓餅", "", 85, 0],
  ["jing|07 果醬厚片＋薯條|0", "經濟特餐", "07 果醬厚片＋薯條", "", 85, 0],
  ["jing|08 薯條＋雞塊（4塊）|0", "經濟特餐", "08 薯條＋雞塊（4塊）", "", 90, 0],
  ["jing|09 火腿起司蛋乳酪餅|0", "經濟特餐", "09 火腿起司蛋乳酪餅", "", 80, 0],
  ["jing|10 美式炒蛋＋薯餅＋熱狗（2根）|0", "經濟特餐", "10 美式炒蛋＋薯餅＋熱狗（2根）", "", 85, 0],
  ["jing|11 鐵板麵（蘑菇／黑胡椒）＋蛋|0", "經濟特餐", "11 鐵板麵（蘑菇／黑胡椒）＋蛋", "", 80, 1],
  ["jing|12 港式蘿蔔糕炒蛋|0", "經濟特餐", "12 港式蘿蔔糕炒蛋", "", 80, 0],
  ["danbing|原味|0", "蛋餅／抓餅蛋／河粉", "原味", "蛋餅", 30, 0],
  ["danbing|原味|1", "蛋餅／抓餅蛋／河粉", "原味", "抓餅蛋", 50, 0],
  ["danbing|原味|2", "蛋餅／抓餅蛋／河粉", "原味", "河粉", 35, 0],
  ["danbing|九層塔／香蔥|0", "蛋餅／抓餅蛋／河粉", "九層塔／香蔥", "蛋餅", 40, 0],
  ["danbing|九層塔／香蔥|1", "蛋餅／抓餅蛋／河粉", "九層塔／香蔥", "抓餅蛋", 60, 0],
  ["danbing|九層塔／香蔥|2", "蛋餅／抓餅蛋／河粉", "九層塔／香蔥", "河粉", 45, 0],
  ["danbing|蔬菜／起司／玉米|0", "蛋餅／抓餅蛋／河粉", "蔬菜／起司／玉米", "蛋餅", 45, 0],
  ["danbing|蔬菜／起司／玉米|1", "蛋餅／抓餅蛋／河粉", "蔬菜／起司／玉米", "抓餅蛋", 60, 0],
  ["danbing|蔬菜／起司／玉米|2", "蛋餅／抓餅蛋／河粉", "蔬菜／起司／玉米", "河粉", 50, 0],
  ["danbing|火腿／熱狗／肉鬆|0", "蛋餅／抓餅蛋／河粉", "火腿／熱狗／肉鬆", "蛋餅", 45, 0],
  ["danbing|火腿／熱狗／肉鬆|1", "蛋餅／抓餅蛋／河粉", "火腿／熱狗／肉鬆", "抓餅蛋", 60, 0],
  ["danbing|火腿／熱狗／肉鬆|2", "蛋餅／抓餅蛋／河粉", "火腿／熱狗／肉鬆", "河粉", 50, 0],
  ["danbing|鮪魚／培根／豬肉|0", "蛋餅／抓餅蛋／河粉", "鮪魚／培根／豬肉", "蛋餅", 45, 0],
  ["danbing|鮪魚／培根／豬肉|1", "蛋餅／抓餅蛋／河粉", "鮪魚／培根／豬肉", "抓餅蛋", 60, 0],
  ["danbing|鮪魚／培根／豬肉|2", "蛋餅／抓餅蛋／河粉", "鮪魚／培根／豬肉", "河粉", 50, 0],
  ["danbing|檸檬雞柳／洋蔥起司|0", "蛋餅／抓餅蛋／河粉", "檸檬雞柳／洋蔥起司", "蛋餅", 50, 0],
  ["danbing|檸檬雞柳／洋蔥起司|1", "蛋餅／抓餅蛋／河粉", "檸檬雞柳／洋蔥起司", "抓餅蛋", 65, 0],
  ["danbing|檸檬雞柳／洋蔥起司|2", "蛋餅／抓餅蛋／河粉", "檸檬雞柳／洋蔥起司", "河粉", 55, 0],
  ["danbing|燻雞／薯餅／豬排|0", "蛋餅／抓餅蛋／河粉", "燻雞／薯餅／豬排", "蛋餅", 55, 0],
  ["danbing|燻雞／薯餅／豬排|1", "蛋餅／抓餅蛋／河粉", "燻雞／薯餅／豬排", "抓餅蛋", 70, 0],
  ["danbing|燻雞／薯餅／豬排|2", "蛋餅／抓餅蛋／河粉", "燻雞／薯餅／豬排", "河粉", 60, 0],
  ["danbing|蝦排起司／鮪魚玉米|0", "蛋餅／抓餅蛋／河粉", "蝦排起司／鮪魚玉米", "蛋餅", 60, 0],
  ["danbing|蝦排起司／鮪魚玉米|1", "蛋餅／抓餅蛋／河粉", "蝦排起司／鮪魚玉米", "抓餅蛋", 75, 0],
  ["danbing|蝦排起司／鮪魚玉米|2", "蛋餅／抓餅蛋／河粉", "蝦排起司／鮪魚玉米", "河粉", 65, 0],
  ["danbing|薯泥培根|0", "蛋餅／抓餅蛋／河粉", "薯泥培根", "蛋餅", 65, 0],
  ["danbing|薯泥培根|1", "蛋餅／抓餅蛋／河粉", "薯泥培根", "抓餅蛋", 80, 0],
  ["danbing|薯泥培根|2", "蛋餅／抓餅蛋／河粉", "薯泥培根", "河粉", 70, 0],
  ["danbing|蒙特婁熱狗起司|0", "蛋餅／抓餅蛋／河粉", "蒙特婁熱狗起司", "蛋餅", 70, 0],
  ["danbing|蒙特婁熱狗起司|1", "蛋餅／抓餅蛋／河粉", "蒙特婁熱狗起司", "抓餅蛋", 85, 0],
  ["danbing|蒙特婁熱狗起司|2", "蛋餅／抓餅蛋／河粉", "蒙特婁熱狗起司", "河粉", 75, 0],
  ["danbing|川麻辣五花（辣）|0", "蛋餅／抓餅蛋／河粉", "川麻辣五花（辣）", "蛋餅", 70, 0],
  ["danbing|川麻辣五花（辣）|1", "蛋餅／抓餅蛋／河粉", "川麻辣五花（辣）", "抓餅蛋", 85, 0],
  ["danbing|川麻辣五花（辣）|2", "蛋餅／抓餅蛋／河粉", "川麻辣五花（辣）", "河粉", 75, 0],
  ["danbing|泡菜豬排|0", "蛋餅／抓餅蛋／河粉", "泡菜豬排", "蛋餅", 70, 0],
  ["danbing|泡菜豬排|1", "蛋餅／抓餅蛋／河粉", "泡菜豬排", "抓餅蛋", 85, 0],
  ["danbing|泡菜豬排|2", "蛋餅／抓餅蛋／河粉", "泡菜豬排", "河粉", 75, 0],
  ["danbing|德腸菜菜|0", "蛋餅／抓餅蛋／河粉", "德腸菜菜", "蛋餅", 75, 0],
  ["danbing|德腸菜菜|1", "蛋餅／抓餅蛋／河粉", "德腸菜菜", "抓餅蛋", 90, 0],
  ["danbing|德腸菜菜|2", "蛋餅／抓餅蛋／河粉", "德腸菜菜", "河粉", 80, 0],
  ["danbing|美式|0", "蛋餅／抓餅蛋／河粉", "美式", "蛋餅", 80, 1],
  ["danbing|美式|1", "蛋餅／抓餅蛋／河粉", "美式", "抓餅蛋", 95, 1],
  ["danbing|美式|2", "蛋餅／抓餅蛋／河粉", "美式", "河粉", 85, 1],
  ["danbing|香辣皮蛋肉鬆|0", "蛋餅／抓餅蛋／河粉", "香辣皮蛋肉鬆", "蛋餅", 80, 0],
  ["danbing|香辣皮蛋肉鬆|1", "蛋餅／抓餅蛋／河粉", "香辣皮蛋肉鬆", "抓餅蛋", 95, 0],
  ["danbing|香辣皮蛋肉鬆|2", "蛋餅／抓餅蛋／河粉", "香辣皮蛋肉鬆", "河粉", 85, 0],
  ["chiyan|原味|0", "赤焰蛋餅", "原味", "", "", 0],
  ["chiyan|九層塔／香蔥|0", "赤焰蛋餅", "九層塔／香蔥", "", "", 0],
  ["chiyan|蔬菜／起司／玉米|0", "赤焰蛋餅", "蔬菜／起司／玉米", "", "", 0],
  ["chiyan|火腿／熱狗／肉鬆|0", "赤焰蛋餅", "火腿／熱狗／肉鬆", "", "", 0],
  ["chiyan|鮪魚／培根／豬肉|0", "赤焰蛋餅", "鮪魚／培根／豬肉", "", "", 0],
  ["chiyan|檸檬雞柳／洋蔥起司|0", "赤焰蛋餅", "檸檬雞柳／洋蔥起司", "", "", 0],
  ["chiyan|燻雞／薯餅／豬排|0", "赤焰蛋餅", "燻雞／薯餅／豬排", "", "", 0],
  ["chiyan|蝦排起司／鮪魚玉米|0", "赤焰蛋餅", "蝦排起司／鮪魚玉米", "", "", 0],
  ["chiyan|薯泥培根|0", "赤焰蛋餅", "薯泥培根", "", "", 0],
  ["chiyan|蒙特婁熱狗起司|0", "赤焰蛋餅", "蒙特婁熱狗起司", "", "", 0],
  ["chiyan|川麻辣五花（辣）|0", "赤焰蛋餅", "川麻辣五花（辣）", "", "", 0],
  ["chiyan|泡菜豬排|0", "赤焰蛋餅", "泡菜豬排", "", "", 0],
  ["chiyan|德腸菜菜|0", "赤焰蛋餅", "德腸菜菜", "", "", 0],
  ["chiyan|美式|0", "赤焰蛋餅", "美式", "", "", 0],
  ["chiyan|香辣皮蛋肉鬆|0", "赤焰蛋餅", "香辣皮蛋肉鬆", "", "", 0],
  ["cheese|歐陸香料乳酪|0", "招牌牽絲乳酪", "歐陸香料乳酪", "蛋餅", 65, 0],
  ["cheese|歐陸香料乳酪|1", "招牌牽絲乳酪", "歐陸香料乳酪", "抓餅蛋", 80, 0],
  ["cheese|肉鬆乳酪|0", "招牌牽絲乳酪", "肉鬆乳酪", "蛋餅", 75, 0],
  ["cheese|肉鬆乳酪|1", "招牌牽絲乳酪", "肉鬆乳酪", "抓餅蛋", 90, 0],
  ["cheese|培根乳酪|0", "招牌牽絲乳酪", "培根乳酪", "蛋餅", 75, 0],
  ["cheese|培根乳酪|1", "招牌牽絲乳酪", "培根乳酪", "抓餅蛋", 90, 0],
  ["cheese|塔香豬肉乳酪|0", "招牌牽絲乳酪", "塔香豬肉乳酪", "蛋餅", 75, 1],
  ["cheese|塔香豬肉乳酪|1", "招牌牽絲乳酪", "塔香豬肉乳酪", "抓餅蛋", 90, 1],
  ["cheese|薯泥乳酪|0", "招牌牽絲乳酪", "薯泥乳酪", "蛋餅", 80, 1],
  ["cheese|薯泥乳酪|1", "招牌牽絲乳酪", "薯泥乳酪", "抓餅蛋", 95, 1],
  ["cheese|燻雞乳酪|0", "招牌牽絲乳酪", "燻雞乳酪", "蛋餅", 80, 0],
  ["cheese|燻雞乳酪|1", "招牌牽絲乳酪", "燻雞乳酪", "抓餅蛋", 95, 0],
  ["cheese|塔香椒鹽皮蛋|0", "招牌牽絲乳酪", "塔香椒鹽皮蛋", "蛋餅", 90, 1],
  ["cheese|塔香椒鹽皮蛋|1", "招牌牽絲乳酪", "塔香椒鹽皮蛋", "抓餅蛋", 105, 1],
  ["cheese|德式香腸乳酪|0", "招牌牽絲乳酪", "德式香腸乳酪", "蛋餅", 95, 1],
  ["cheese|德式香腸乳酪|1", "招牌牽絲乳酪", "德式香腸乳酪", "抓餅蛋", 110, 1],
  ["spread|花生／奶酥|0", "抹醬吐司／厚片／乳酪餅", "花生／奶酥", "薄片", 20, 0],
  ["spread|花生／奶酥|1", "抹醬吐司／厚片／乳酪餅", "花生／奶酥", "厚片", 35, 0],
  ["spread|花生／奶酥|2", "抹醬吐司／厚片／乳酪餅", "花生／奶酥", "乳酪餅", 35, 0],
  ["spread|香蒜／奶油|0", "抹醬吐司／厚片／乳酪餅", "香蒜／奶油", "薄片", 20, 0],
  ["spread|香蒜／奶油|1", "抹醬吐司／厚片／乳酪餅", "香蒜／奶油", "厚片", 35, 0],
  ["spread|香蒜／奶油|2", "抹醬吐司／厚片／乳酪餅", "香蒜／奶油", "乳酪餅", 35, 0],
  ["spread|巧克力／草莓|0", "抹醬吐司／厚片／乳酪餅", "巧克力／草莓", "薄片", 20, 0],
  ["spread|巧克力／草莓|1", "抹醬吐司／厚片／乳酪餅", "巧克力／草莓", "厚片", 35, 0],
  ["spread|巧克力／草莓|2", "抹醬吐司／厚片／乳酪餅", "巧克力／草莓", "乳酪餅", 35, 0],
  ["spread|鹹鹹厚片|1", "抹醬吐司／厚片／乳酪餅", "鹹鹹厚片", "厚片", 40, 0],
  ["spread|四色厚片|1", "抹醬吐司／厚片／乳酪餅", "四色厚片", "厚片", 50, 1],
  ["spread|蒜香雙料厚片|1", "抹醬吐司／厚片／乳酪餅", "蒜香雙料厚片", "厚片", 65, 1],
  ["bake|焗烤花生厚片|0", "焗烤厚片", "焗烤花生厚片", "厚片", 55, 0],
  ["bake|焗烤香蒜厚片|0", "焗烤厚片", "焗烤香蒜厚片", "厚片", 55, 0],
  ["bake|焗烤奶油厚片|0", "焗烤厚片", "焗烤奶油厚片", "厚片", 55, 0],
  ["bake|焗烤招牌厚片|0", "焗烤厚片", "焗烤招牌厚片", "厚片", 70, 1],
  ["bake|焗烤薯泥厚片|0", "焗烤厚片", "焗烤薯泥厚片", "厚片", 70, 0],
  ["bake|焗烤川麻燒豬|0", "焗烤厚片", "焗烤川麻燒豬", "厚片", 75, 1],
  ["toast|玉米／蔬菜／起司|0", "吐司／漢堡／乳酪餅", "玉米／蔬菜／起司", "吐司", 45, 0],
  ["toast|玉米／蔬菜／起司|1", "吐司／漢堡／乳酪餅", "玉米／蔬菜／起司", "漢堡", 50, 0],
  ["toast|玉米／蔬菜／起司|2", "吐司／漢堡／乳酪餅", "玉米／蔬菜／起司", "乳酪餅", 60, 0],
  ["toast|火腿／香雞／肉鬆|0", "吐司／漢堡／乳酪餅", "火腿／香雞／肉鬆", "吐司", 45, 0],
  ["toast|火腿／香雞／肉鬆|1", "吐司／漢堡／乳酪餅", "火腿／香雞／肉鬆", "漢堡", 50, 0],
  ["toast|火腿／香雞／肉鬆|2", "吐司／漢堡／乳酪餅", "火腿／香雞／肉鬆", "乳酪餅", 60, 0],
  ["toast|培根／豬肉／鮪魚|0", "吐司／漢堡／乳酪餅", "培根／豬肉／鮪魚", "吐司", 45, 0],
  ["toast|培根／豬肉／鮪魚|1", "吐司／漢堡／乳酪餅", "培根／豬肉／鮪魚", "漢堡", 50, 0],
  ["toast|培根／豬肉／鮪魚|2", "吐司／漢堡／乳酪餅", "培根／豬肉／鮪魚", "乳酪餅", 60, 0],
  ["toast|泰式醬鮮蔬|0", "吐司／漢堡／乳酪餅", "泰式醬鮮蔬", "吐司", 50, 0],
  ["toast|泰式醬鮮蔬|1", "吐司／漢堡／乳酪餅", "泰式醬鮮蔬", "漢堡", 55, 0],
  ["toast|泰式醬鮮蔬|2", "吐司／漢堡／乳酪餅", "泰式醬鮮蔬", "乳酪餅", 65, 0],
  ["toast|豬排／燻雞／薯餅|0", "吐司／漢堡／乳酪餅", "豬排／燻雞／薯餅", "吐司", 55, 0],
  ["toast|豬排／燻雞／薯餅|1", "吐司／漢堡／乳酪餅", "豬排／燻雞／薯餅", "漢堡", 60, 0],
  ["toast|豬排／燻雞／薯餅|2", "吐司／漢堡／乳酪餅", "豬排／燻雞／薯餅", "乳酪餅", 70, 0],
  ["toast|自製薯泥蛋沙拉|0", "吐司／漢堡／乳酪餅", "自製薯泥蛋沙拉", "吐司", 55, 0],
  ["toast|自製薯泥蛋沙拉|1", "吐司／漢堡／乳酪餅", "自製薯泥蛋沙拉", "漢堡", 60, 0],
  ["toast|自製薯泥蛋沙拉|2", "吐司／漢堡／乳酪餅", "自製薯泥蛋沙拉", "乳酪餅", 70, 0],
  ["toast|檸檬雞柳|0", "吐司／漢堡／乳酪餅", "檸檬雞柳", "吐司", 55, 0],
  ["toast|檸檬雞柳|1", "吐司／漢堡／乳酪餅", "檸檬雞柳", "漢堡", 60, 0],
  ["toast|檸檬雞柳|2", "吐司／漢堡／乳酪餅", "檸檬雞柳", "乳酪餅", 70, 0],
  ["toast|藍帶豬排|0", "吐司／漢堡／乳酪餅", "藍帶豬排", "吐司", 60, 0],
  ["toast|藍帶豬排|1", "吐司／漢堡／乳酪餅", "藍帶豬排", "漢堡", 65, 0],
  ["toast|藍帶豬排|2", "吐司／漢堡／乳酪餅", "藍帶豬排", "乳酪餅", 75, 0],
  ["toast|特製辣蝦|0", "吐司／漢堡／乳酪餅", "特製辣蝦", "吐司", 60, 0],
  ["toast|特製辣蝦|1", "吐司／漢堡／乳酪餅", "特製辣蝦", "漢堡", 65, 0],
  ["toast|特製辣蝦|2", "吐司／漢堡／乳酪餅", "特製辣蝦", "乳酪餅", 75, 0],
  ["toast|鮪魚玉米蛋|0", "吐司／漢堡／乳酪餅", "鮪魚玉米蛋", "吐司", 60, 0],
  ["toast|鮪魚玉米蛋|1", "吐司／漢堡／乳酪餅", "鮪魚玉米蛋", "漢堡", 65, 0],
  ["toast|鮪魚玉米蛋|2", "吐司／漢堡／乳酪餅", "鮪魚玉米蛋", "乳酪餅", 75, 0],
  ["toast|塔香豬排|0", "吐司／漢堡／乳酪餅", "塔香豬排", "吐司", 60, 1],
  ["toast|塔香豬排|1", "吐司／漢堡／乳酪餅", "塔香豬排", "漢堡", 65, 1],
  ["toast|塔香豬排|2", "吐司／漢堡／乳酪餅", "塔香豬排", "乳酪餅", 75, 1],
  ["toast|蒜香辣燻雞|0", "吐司／漢堡／乳酪餅", "蒜香辣燻雞", "吐司", 60, 0],
  ["toast|蒜香辣燻雞|1", "吐司／漢堡／乳酪餅", "蒜香辣燻雞", "漢堡", 65, 0],
  ["toast|蒜香辣燻雞|2", "吐司／漢堡／乳酪餅", "蒜香辣燻雞", "乳酪餅", 75, 0],
  ["toast|辣蝦排|0", "吐司／漢堡／乳酪餅", "辣蝦排", "吐司", 60, 1],
  ["toast|辣蝦排|1", "吐司／漢堡／乳酪餅", "辣蝦排", "漢堡", 65, 1],
  ["toast|辣蝦排|2", "吐司／漢堡／乳酪餅", "辣蝦排", "乳酪餅", 75, 1],
  ["toast|三層薯泥起司軟吐司|0", "吐司／漢堡／乳酪餅", "三層薯泥起司軟吐司", "吐司", 75, 1],
  ["toast|孟老師的大漢堡|1", "吐司／漢堡／乳酪餅", "孟老師的大漢堡", "漢堡", 105, 1],
  ["toast|辣鮪魚火腿|0", "吐司／漢堡／乳酪餅", "辣鮪魚火腿", "吐司", 65, 0],
  ["toast|辣鮪魚火腿|1", "吐司／漢堡／乳酪餅", "辣鮪魚火腿", "漢堡", 70, 0],
  ["toast|辣鮪魚火腿|2", "吐司／漢堡／乳酪餅", "辣鮪魚火腿", "乳酪餅", 80, 0],
  ["toast|泡菜辣培根|0", "吐司／漢堡／乳酪餅", "泡菜辣培根", "吐司", 65, 0],
  ["toast|泡菜辣培根|1", "吐司／漢堡／乳酪餅", "泡菜辣培根", "漢堡", 70, 0],
  ["toast|泡菜辣培根|2", "吐司／漢堡／乳酪餅", "泡菜辣培根", "乳酪餅", 80, 0],
  ["toast|卡啦雞腿（原／辣味）|0", "吐司／漢堡／乳酪餅", "卡啦雞腿（原／辣味）", "吐司", 70, 0],
  ["toast|卡啦雞腿（原／辣味）|1", "吐司／漢堡／乳酪餅", "卡啦雞腿（原／辣味）", "漢堡", 75, 0],
  ["toast|卡啦雞腿（原／辣味）|2", "吐司／漢堡／乳酪餅", "卡啦雞腿（原／辣味）", "乳酪餅", 85, 0],
  ["toast|川麻燒豬（辣）|0", "吐司／漢堡／乳酪餅", "川麻燒豬（辣）", "吐司", 70, 1],
  ["toast|川麻燒豬（辣）|1", "吐司／漢堡／乳酪餅", "川麻燒豬（辣）", "漢堡", 75, 1],
  ["toast|川麻燒豬（辣）|2", "吐司／漢堡／乳酪餅", "川麻燒豬（辣）", "乳酪餅", 85, 1],
  ["toast|辣鮪魚薯餅|0", "吐司／漢堡／乳酪餅", "辣鮪魚薯餅", "吐司", 75, 1],
  ["toast|辣鮪魚薯餅|1", "吐司／漢堡／乳酪餅", "辣鮪魚薯餅", "漢堡", 80, 1],
  ["toast|辣鮪魚薯餅|2", "吐司／漢堡／乳酪餅", "辣鮪魚薯餅", "乳酪餅", 90, 1],
  ["toast|花生醬雙培根起司|0", "吐司／漢堡／乳酪餅", "花生醬雙培根起司", "吐司", 75, 0],
  ["toast|花生醬雙培根起司|1", "吐司／漢堡／乳酪餅", "花生醬雙培根起司", "漢堡", 80, 0],
  ["toast|花生醬雙培根起司|2", "吐司／漢堡／乳酪餅", "花生醬雙培根起司", "乳酪餅", 90, 0],
  ["toast|雙金鮪魚|0", "吐司／漢堡／乳酪餅", "雙金鮪魚", "吐司", 75, 1],
  ["toast|雙金鮪魚|1", "吐司／漢堡／乳酪餅", "雙金鮪魚", "漢堡", 80, 1],
  ["toast|雙金鮪魚|2", "吐司／漢堡／乳酪餅", "雙金鮪魚", "乳酪餅", 90, 1],
  ["toast|辣德腸起司|0", "吐司／漢堡／乳酪餅", "辣德腸起司", "吐司", 75, 1],
  ["toast|辣德腸起司|1", "吐司／漢堡／乳酪餅", "辣德腸起司", "漢堡", 80, 1],
  ["toast|辣德腸起司|2", "吐司／漢堡／乳酪餅", "辣德腸起司", "乳酪餅", 90, 1],
  ["toast|泰式醬雞柳起司|0", "吐司／漢堡／乳酪餅", "泰式醬雞柳起司", "吐司", 75, 0],
  ["toast|泰式醬雞柳起司|1", "吐司／漢堡／乳酪餅", "泰式醬雞柳起司", "漢堡", 80, 0],
  ["toast|泰式醬雞柳起司|2", "吐司／漢堡／乳酪餅", "泰式醬雞柳起司", "乳酪餅", 90, 0],
  ["toast|豬排薯餅|0", "吐司／漢堡／乳酪餅", "豬排薯餅", "吐司", 75, 0],
  ["toast|豬排薯餅|1", "吐司／漢堡／乳酪餅", "豬排薯餅", "漢堡", 80, 0],
  ["toast|豬排薯餅|2", "吐司／漢堡／乳酪餅", "豬排薯餅", "乳酪餅", 90, 0],
  ["toast|豬排起司辣薯|0", "吐司／漢堡／乳酪餅", "豬排起司辣薯", "吐司", 80, 1],
  ["toast|豬排起司辣薯|1", "吐司／漢堡／乳酪餅", "豬排起司辣薯", "漢堡", 85, 1],
  ["toast|豬排起司辣薯|2", "吐司／漢堡／乳酪餅", "豬排起司辣薯", "乳酪餅", 95, 1],
  ["toast|辣培根薯泥起司|0", "吐司／漢堡／乳酪餅", "辣培根薯泥起司", "吐司", 80, 1],
  ["toast|辣培根薯泥起司|1", "吐司／漢堡／乳酪餅", "辣培根薯泥起司", "漢堡", 85, 1],
  ["toast|辣培根薯泥起司|2", "吐司／漢堡／乳酪餅", "辣培根薯泥起司", "乳酪餅", 95, 1],
  ["toast|草莓肉鬆豬排蛋|0", "吐司／漢堡／乳酪餅", "草莓肉鬆豬排蛋", "吐司", 80, 0],
  ["toast|草莓肉鬆豬排蛋|1", "吐司／漢堡／乳酪餅", "草莓肉鬆豬排蛋", "漢堡", 85, 0],
  ["toast|草莓肉鬆豬排蛋|2", "吐司／漢堡／乳酪餅", "草莓肉鬆豬排蛋", "乳酪餅", 95, 0],
  ["toast|花醬培根厚蛋燒|0", "吐司／漢堡／乳酪餅", "花醬培根厚蛋燒", "吐司", 85, 1],
  ["toast|花醬培根厚蛋燒|1", "吐司／漢堡／乳酪餅", "花醬培根厚蛋燒", "漢堡", 90, 1],
  ["toast|花醬培根厚蛋燒|2", "吐司／漢堡／乳酪餅", "花醬培根厚蛋燒", "乳酪餅", 100, 1],
  ["toast|豬排薯泥玉米蛋|0", "吐司／漢堡／乳酪餅", "豬排薯泥玉米蛋", "吐司", 95, 1],
  ["toast|豬排薯泥玉米蛋|1", "吐司／漢堡／乳酪餅", "豬排薯泥玉米蛋", "漢堡", 100, 1],
  ["toast|豬排薯泥玉米蛋|2", "吐司／漢堡／乳酪餅", "豬排薯泥玉米蛋", "乳酪餅", 110, 1],
  ["club|豬肉總匯|0", "總匯吐司", "豬肉總匯", "", 70, 0],
  ["club|鮪魚／香雞總匯|0", "總匯吐司", "鮪魚／香雞總匯", "", 75, 0],
  ["club|特製辣蝦／雙金鮪魚總匯|0", "總匯吐司", "特製辣蝦／雙金鮪魚總匯", "", 80, 0],
  ["club|豬排／美式／藍帶豬排總匯|0", "總匯吐司", "豬排／美式／藍帶豬排總匯", "", 85, 0],
  ["club|海陸總匯|0", "總匯吐司", "海陸總匯", "", 90, 1],
  ["club|泰式蝦排起司總匯|0", "總匯吐司", "泰式蝦排起司總匯", "", 90, 0],
  ["club|豬排薯餅總匯|0", "總匯吐司", "豬排薯餅總匯", "", 95, 0],
  ["club|雙層豬肉起司總匯|0", "總匯吐司", "雙層豬肉起司總匯", "", 95, 1],
  ["club|培根薯泥起司總匯|0", "總匯吐司", "培根薯泥起司總匯", "", 95, 0],
  ["club|花醬辣培根總匯|0", "總匯吐司", "花醬辣培根總匯", "", 95, 0],
  ["club|塔香雙豬排總匯|0", "總匯吐司", "塔香雙豬排總匯", "", 100, 1],
  ["club|綿羊羊超級總匯|0", "總匯吐司", "綿羊羊超級總匯", "", 110, 1],
  ["single|荷包蛋／炒蛋|0", "單點", "荷包蛋／炒蛋", "", 15, 0],
  ["single|薯餅|0", "單點", "薯餅", "", 25, 0],
  ["single|熱狗|0", "單點", "熱狗", "", 35, 0],
  ["single|黑胡椒豬排片|0", "單點", "黑胡椒豬排片", "", 40, 0],
  ["single|雞米花|0", "單點", "雞米花", "", 40, 0],
  ["single|薯條／雞塊|0", "單點", "薯條／雞塊", "", 40, 0],
  ["single|小肉豆|0", "單點", "小肉豆", "", 40, 0],
  ["single|檸檬雞柳|0", "單點", "檸檬雞柳", "", 45, 0],
  ["single|蘿蔔糕|0", "單點", "蘿蔔糕", "", 45, 0],
  ["single|煎餃|0", "單點", "煎餃", "", 45, 0],
  ["single|藍帶豬排|0", "單點", "藍帶豬排", "", 45, 0],
  ["single|椒鹽炸餃|0", "單點", "椒鹽炸餃", "", 45, 0],
  ["single|辛香脆薯|0", "單點", "辛香脆薯", "", 50, 0],
  ["single|卡啦雞腿排（原／辣）|0", "單點", "卡啦雞腿排（原／辣）", "", 55, 0],
  ["single|蘿蔔糕炒蛋|0", "單點", "蘿蔔糕炒蛋", "", 60, 0],
  ["single|塔香蘿蔔糕牽絲乳酪炒蛋|0", "單點", "塔香蘿蔔糕牽絲乳酪炒蛋", "", 85, 1],
  ["single|煎餃炒蛋|0", "單點", "煎餃炒蛋", "", 60, 1],
  ["single|薯餅塔|0", "單點", "薯餅塔", "", 65, 1],
  ["single|快樂小兒童|0", "單點", "快樂小兒童", "", 65, 0],
  ["single|胡麻燻雞皮蛋沙拉（輕食）|0", "單點", "胡麻燻雞皮蛋沙拉（輕食）", "", 80, 0],
  ["single|超級薯餅塔|0", "單點", "超級薯餅塔", "", 95, 0],
  ["single|卡啦卡啦塔|0", "單點", "卡啦卡啦塔", "", 125, 1],
  ["tpm|蘑菇鐵板麵|0", "鐵板麵", "蘑菇鐵板麵", "單點", 50, 0],
  ["tpm|蘑菇鐵板麵|1", "鐵板麵", "蘑菇鐵板麵", "加蛋", "", 0],
  ["tpm|蘑菇鐵板麵|2", "鐵板麵", "蘑菇鐵板麵", "加肉", "", 0],
  ["tpm|蘑菇鐵板麵|3", "鐵板麵", "蘑菇鐵板麵", "九層塔", "", 0],
  ["tpm|蘑菇鐵板麵|4", "鐵板麵", "蘑菇鐵板麵", "起士", "", 0],
  ["tpm|蘑菇鐵板麵|5", "鐵板麵", "蘑菇鐵板麵", "雙起士", "", 0],
  ["tpm|黑胡椒鐵板麵|0", "鐵板麵", "黑胡椒鐵板麵", "單點", 50, 0],
  ["tpm|黑胡椒鐵板麵|1", "鐵板麵", "黑胡椒鐵板麵", "加蛋", "", 0],
  ["tpm|黑胡椒鐵板麵|2", "鐵板麵", "黑胡椒鐵板麵", "加肉", "", 0],
  ["tpm|黑胡椒鐵板麵|3", "鐵板麵", "黑胡椒鐵板麵", "九層塔", "", 0],
  ["tpm|黑胡椒鐵板麵|4", "鐵板麵", "黑胡椒鐵板麵", "起士", "", 0],
  ["tpm|黑胡椒鐵板麵|5", "鐵板麵", "黑胡椒鐵板麵", "雙起士", "", 0],
  ["tpm|肉醬鐵板麵|0", "鐵板麵", "肉醬鐵板麵", "單點", "", 0],
  ["tpm|肉醬鐵板麵|1", "鐵板麵", "肉醬鐵板麵", "加蛋", "", 0],
  ["tpm|肉醬鐵板麵|2", "鐵板麵", "肉醬鐵板麵", "加肉", "", 0],
  ["tpm|肉醬鐵板麵|3", "鐵板麵", "肉醬鐵板麵", "九層塔", "", 0],
  ["tpm|肉醬鐵板麵|4", "鐵板麵", "肉醬鐵板麵", "起士", "", 0],
  ["tpm|肉醬鐵板麵|5", "鐵板麵", "肉醬鐵板麵", "雙起士", "", 0],
  ["teppan|塔香起司辣肉醬麵|0", "鐵板麵組合", "塔香起司辣肉醬麵", "", 80, 0],
  ["teppan|蘑菇鐵板麵肉蛋雙拼|0", "鐵板麵組合", "蘑菇鐵板麵肉蛋雙拼", "", 85, 0],
  ["teppan|黑胡椒鐵板麵肉蛋雙拼|0", "鐵板麵組合", "黑胡椒鐵板麵肉蛋雙拼", "", 85, 0],
  ["teppan|起司辣肉醬麵肉蛋雙拼|0", "鐵板麵組合", "起司辣肉醬麵肉蛋雙拼", "", 105, 1],
  ["teppan|鐵板麵豪華三拼（菇／黑）|0", "鐵板麵組合", "鐵板麵豪華三拼（菇／黑）", "", 110, 1],
  ["drink|紅茶|0", "喝點什麼", "紅茶", "中杯", 25, 0],
  ["drink|紅茶|1", "喝點什麼", "紅茶", "大杯", 30, 0],
  ["drink|奶茶|0", "喝點什麼", "奶茶", "中杯", 25, 0],
  ["drink|奶茶|1", "喝點什麼", "奶茶", "大杯", 30, 0],
  ["drink|無糖紅茶|0", "喝點什麼", "無糖紅茶", "中杯", 25, 0],
  ["drink|無糖紅茶|1", "喝點什麼", "無糖紅茶", "大杯", 30, 0],
  ["drink|無糖豆漿|0", "喝點什麼", "無糖豆漿", "中杯", 25, 0],
  ["drink|無糖豆漿|1", "喝點什麼", "無糖豆漿", "大杯", 30, 0],
  ["drink|豆漿紅茶|0", "喝點什麼", "豆漿紅茶", "中杯", 30, 0],
  ["drink|豆漿紅茶|1", "喝點什麼", "豆漿紅茶", "大杯", 35, 0],
  ["drink|啊！害啊！（紅茶混奶茶）|0", "喝點什麼", "啊！害啊！（紅茶混奶茶）", "中杯", 30, 1],
  ["drink|啊！害啊！（紅茶混奶茶）|1", "喝點什麼", "啊！害啊！（紅茶混奶茶）", "大杯", 35, 1],
  ["drink|義美鮮奶茶|0", "喝點什麼", "義美鮮奶茶", "中杯", 35, 0],
  ["drink|義美鮮奶茶|1", "喝點什麼", "義美鮮奶茶", "大杯", 40, 0],
  ["drink|雙倍義美鮮奶茶|0", "喝點什麼", "雙倍義美鮮奶茶", "中杯", 45, 1],
  ["drink|雙倍義美鮮奶茶|1", "喝點什麼", "雙倍義美鮮奶茶", "大杯", 50, 1],
  ["drink|研磨咖啡／黑咖啡|0", "喝點什麼", "研磨咖啡／黑咖啡", "中杯", 35, 0],
  ["drink|研磨咖啡／黑咖啡|1", "喝點什麼", "研磨咖啡／黑咖啡", "大杯", 40, 0],
  ["drink|咖啡拿鐵|0", "喝點什麼", "咖啡拿鐵", "中杯", 45, 1],
  ["drink|咖啡拿鐵|1", "喝點什麼", "咖啡拿鐵", "大杯", 50, 1],
  ["drink|鴛鴦奶茶|1", "喝點什麼", "鴛鴦奶茶", "大杯", 50, 1],
  ["drink|招牌暖暖濃湯（冬季限定）|0", "喝點什麼", "招牌暖暖濃湯（冬季限定）", "中杯", 60, 1],
  ["add|蛋餅加九層塔|0", "加料／加價", "蛋餅加九層塔", "", 10, 0],
  ["add|蛋餅加起司|0", "加料／加價", "蛋餅加起司", "", 10, 0],
  ["add|蛋餅加蔬菜|0", "加料／加價", "蛋餅加蔬菜", "", 10, 0],
  ["add|蛋餅加乳酪絲|0", "加料／加價", "蛋餅加乳酪絲", "", 30, 0],
  ["add|吐司加花生醬|0", "加料／加價", "吐司加花生醬", "", 5, 0],
  ["add|吐司加起司|0", "加料／加價", "吐司加起司", "", 10, 0],
  ["add|吐司加蔬菜|0", "加料／加價", "吐司加蔬菜", "", 10, 0],
  ["add|吐司加薯餅|0", "加料／加價", "吐司加薯餅", "", 25, 0],
  ["add|厚片換口味|0", "加料／加價", "厚片換口味", "", 5, 0]
];

/* ================= 試算表選單 ================= */
function onOpen() {
  SpreadsheetApp.getUi().createMenu('🍳 弘林菜單')
    .addItem('建立／整理價格表（會保留已填的價格）', 'setup')
    .addItem('打開菜單工具（顯示網址）', 'showUrl')
    .addItem('自我檢查（測試用）', 'selfTest')
    .addToUi();
}

// 自動記住「這個程式所在的試算表」，換新試算表也不用改程式碼
function book_() {
  if (saas_()) {
    if (!CTX.ssId) throw new Error('內部錯誤：沒有店家情境');
    return CTX._ss || (CTX._ss = SpreadsheetApp.openById(CTX.ssId));
  }
  const id = PropertiesService.getScriptProperties().getProperty('ssId');
  if (id) { try { return SpreadsheetApp.openById(id); } catch (e) {} }
  return SpreadsheetApp.getActiveSpreadsheet();
}

// 顯示網址：一律用你正式部署的網址（WEB_APP_URL），不用 Google 自動給的測試網址（那個常常打不開）
function webUrl_() { return WEB_APP_URL || ScriptApp.getService().getUrl() || ''; }

function showUrl() {
  const url = webUrl_();
  const ui = SpreadsheetApp.getUi();
  if (!url) { ui.alert('還沒部署網頁應用程式。請到 Apps Script 右上角「部署 → 新增部署作業」。'); return; }
  if (saas_()) {
    const lid = PropertiesService.getScriptProperties().getProperty('legacyShopId') || '';
    ui.alert('線上服務模式', '登入（店主／夥伴／管理）：\n' + url + '\n\n顧客服務頁（LINE 圖文選單用）：\n' + url + '?s=' + lid, ui.ButtonSet.OK);
    return;
  }
  const staff = url + '?staff=' + STAFF_KEY;
  const row = (t, u, big) => '<div style="margin:0 0 14px"><b style="font-size:' + (big ? 16 : 13) + 'px">' + t + '</b><br>' +
    '<a href="' + u + '" target="_blank" style="display:inline-block;margin:6px 0;padding:' + (big ? '10px 16px' : '4px 0') + ';' + (big ? 'background:#E8762A;color:#fff;border-radius:10px;text-decoration:none;font-weight:700' : '') + '">' + (big ? '打開菜單工具' : u) + '</a>' +
    (big ? '<br><input value="' + u + '" readonly onclick="this.select()" style="width:100%;font-size:12px;padding:6px">' : '') + '</div>';
  const html = HtmlService.createHtmlOutput('<div style="font-family:sans-serif;font-size:13px;line-height:1.5">' +
    row('夥伴菜單工具（改價格、輸出 PDF）', staff, true) +
    row('店家工具（交接、店休日曆、公告、桌號 QR、Wi-Fi 卡）', url + '?p=tools&staff=' + STAFF_KEY) +
    '<details><summary style="cursor:pointer;color:#555">顧客服務頁網址（LINE 圖文選單用）</summary><div style="margin-top:8px">' +
    row('顧客服務首頁', url) + row('大單預訂', url + '?p=pre') + row('敲敲老闆', url + '?p=knock') + row('創意許願', url + '?p=wish') + row('異常協助', url + '?p=help') + '</div></details>' +
    '</div>').setWidth(560).setHeight(380);
  ui.showModalDialog(html, '網址');
}

// 自我檢查：在試算表選單按一下，檢查價格表、菜單工具、顧客頁是否都能正常產生
function selfToken_() {
  const lid = PropertiesService.getScriptProperties().getProperty('legacyShopId');
  if (!lid) throw new Error('找不到原店家');
  const s = shopById_(lid);
  return tokenMake_({ s: lid, r: 'owner', u: 'owner', v: s.tv }, 1);
}
function selfTest() {
  if (saas_()) { const lid = PropertiesService.getScriptProperties().getProperty('legacyShopId'); if (lid) useShop_(lid); }
  const out = [];
  const ok = (name, fn) => { try { const r = fn(); out.push('✅ ' + name + (r ? '：' + r : '')); } catch (e) { out.push('❌ ' + name + '：' + (e && e.message || e)); } };
  ok('找到試算表', () => { const ss = book_(); if (!ss) throw new Error('找不到，請先執行「建立／整理價格表」'); return ss.getName ? ss.getName() : ''; });
  ok('讀取價格表', () => { const d = getData_(); if (d.error) throw new Error(d.error === 'noSheet' ? '沒有「價格表」分頁，請先執行「建立／整理價格表」' : d.error); return Object.keys(d.prices).length + ' 格，目前菜單版本 V' + d.ver; });
  const stKey = saas_() ? selfToken_() : STAFF_KEY, stQ = saas_() ? 't' : 'staff';
  ok('菜單工具頁面', () => { const h = doGet({ parameter: { [stQ]: stKey } }).getContent(); if (h.indexOf('STAFF_KEY') < 0) throw new Error('Page 檔案可能沒貼完整'); return '正常'; });
  ok('顧客服務頁面', () => { const h = doGet({ parameter: saas_() ? { s: (CTX.shopId || '') } : {} }).getContent(); if (h.indexOf('__hlEnd') < 0) throw new Error('Customer 檔案可能沒貼完整'); return '正常'; });
  ok('店家工具頁面', () => {
    if (typeof toolsPage_ !== 'function') throw new Error('還沒新增 ToolsServer 指令碼');
    const h = doGet({ parameter: { p: 'tools', [stQ]: stKey } }).getContent();
    if (h.indexOf('__hlEnd') < 0) throw new Error('Tools 檔案可能沒貼完整'); return '正常';
  });
  ok('吉祥物圖片', () => logoDataUri_() ? '有' : '沒找到（不影響使用，要顯示請把「弘林logo」圖片放到雲端硬碟）');
  ok('網址', () => webUrl_() || '尚未設定');
  const msg = out.join('\n');
  Logger.log(msg);
  try { SpreadsheetApp.getUi().alert('弘林菜單・自我檢查', msg + '\n\n夥伴菜單工具：\n' + webUrl_() + '?staff=' + STAFF_KEY, SpreadsheetApp.getUi().ButtonSet.OK); } catch (e) {}
  return msg;
}

/* ================= 建立／整理價格表 ================= */
const itemOf_ = k => String(k).split('|').slice(0, 2).join('|');   // 'sid|品項'
const bool_ = v => v === true || v === 'TRUE' || v === 'true' || v === '隱藏' || v === '★';
function deleted_() { try { return JSON.parse(props_().getProperty('deleted') || '[]'); } catch (e) { return []; } }

function setup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  PropertiesService.getScriptProperties().setProperty('ssId', ss.getId());
  if (saas_() && !CTX.ssId) { const lid = PropertiesService.getScriptProperties().getProperty('legacyShopId'); if (lid) useShop_(lid); }
  setupBook_(ss, ITEMS, { title: '弘林早午餐｜菜單價格表' });
  try { if (typeof ensureTickTrigger_ === 'function') ensureTickTrigger_(); } catch (e) {}   // 每小時提醒（未打卡、預期排班、交接、叫貨）
}

// items：內建品項清單（新店家給 []）；opt.title：價格表左上角的標題
function setupBook_(ss, items, opt) {
  opt = opt || {};
  const old = readAnyPrices_(ss);
  let sh = ss.getSheetByName(SHEET_NAME);
  const prevRows = sh ? readRows_(sh) : [];
  const meta = {}; prevRows.forEach(r => meta[r.k] = r);
  if (!sh) sh = ss.insertSheet(SHEET_NAME, 0);

  sh.getProtections(SpreadsheetApp.ProtectionType.SHEET).forEach(p => p.remove());
  sh.getProtections(SpreadsheetApp.ProtectionType.RANGE).forEach(p => p.remove());
  sh.clear();
  sh.clearConditionalFormatRules();
  sh.getRange(1, 1, sh.getMaxRows(), sh.getMaxColumns()).clearDataValidations();

  sh.getRange('A1').setValue(opt.title || '菜單價格表').setFontSize(15).setFontWeight('bold').setFontColor('#1B4F8A');
  sh.getRange('A2').setValue('只改黃色「價格」欄（只能填數字）。橘色＝跟上次印的菜單不一樣；紅色＝還沒有價格。「隱藏」打勾＝暫時不印在菜單上；「推薦」打勾＝菜單上標星星。');
  sh.getRange('A3').setValue('新增、刪除品項請用「菜單工具」。「上次印製」由系統自動更新。');
  sh.getRange('A2:A3').setFontColor('#555555');

  const head = ['代碼（勿改）', '分類', '品項', '規格', '價格', '上次印製', '隱藏', '推薦', '附餐說明', '標示'];
  sh.getRange(HEAD, 1, 1, NCOL).setValues([head]).setFontWeight('bold').setFontColor('#ffffff')
    .setBackground('#1B4F8A').setHorizontalAlignment('center');

  const del = deleted_();
  const builtinKeys = {}; items.forEach(it => builtinKeys[it[0]] = 1);
  const aliasOld = {}; Object.keys(KEY_ALIAS).forEach(k => aliasOld[KEY_ALIAS[k]] = 1);
  const skip = k => REMOVED_KEYS.indexOf(k) >= 0 || aliasOld[k] || del.indexOf(itemOf_(k)) >= 0;
  // 自己新增的品項（價格表裡有、內建清單沒有的）要保留，依分類放回原位置
  const custom = {};
  prevRows.forEach(r => { if (!builtinKeys[r.k] && !skip(r.k)) { const sid = r.k.split('|')[0]; (custom[sid] = custom[sid] || []).push(r); } });
  const rows = []; let lastSid = null;
  const flush = sid => { (custom[sid] || []).forEach(r => rows.push([r.k, r.cat, r.name, r.spec, r.p, r.l === '' ? r.p : r.l, r.hidden, r.star, r.side, r.tags])); delete custom[sid]; };
  items.forEach(([k, cat, name, spec, def, star]) => {
    const sid = k.split('|')[0];
    if (lastSid !== null && sid !== lastSid) flush(lastSid);
    lastSid = sid;
    if (skip(k)) return;
    const o = old[k] || (KEY_ALIAS[k] && old[KEY_ALIAS[k]]);
    const m = meta[k] || (KEY_ALIAS[k] && meta[KEY_ALIAS[k]]);
    const p = o && o.p !== '' ? o.p : def;
    const l = o && o.l !== '' ? o.l : p;
    rows.push([k, cat, name, spec, p, l, m ? m.hidden : false, m && m.star !== null ? m.star : !!star, m ? m.side : '', m ? m.tags : '']);
  });
  if (lastSid !== null) flush(lastSid);
  Object.keys(custom).forEach(flush);

  const n = Math.max(rows.length, 1);
  if (!rows.length) rows.push(['', '', '', '', '', '', false, false, '', '']);
  sh.getRange(HEAD + 1, 1, n, NCOL).setValues(rows).setFontSize(11);
  sh.getRange(HEAD + 1, 1, n, 1).setFontColor('#aaaaaa');
  sh.getRange(HEAD + 1, 5, n, 1).setBackground('#FFF2CC').setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange(HEAD + 1, 6, n, 1).setFontColor('#888888').setHorizontalAlignment('center');
  const boxes = sh.getRange(HEAD + 1, 7, n, 2);
  boxes.setDataValidation(SpreadsheetApp.newDataValidation().requireCheckbox().build());
  [170, 150, 210, 70, 80, 80, 60, 60, 160, 160].forEach((w, i) => sh.setColumnWidth(i + 1, w));
  sh.setFrozenRows(HEAD);

  const priceRange = sh.getRange(HEAD + 1, 5, n, 1);
  priceRange.setDataValidation(SpreadsheetApp.newDataValidation()
    .requireNumberBetween(0, 9999).setAllowInvalid(false).setHelpText('請只填數字（元）').build());
  const r0 = HEAD + 1;
  sh.setConditionalFormatRules([
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$G' + r0 + '=TRUE')
      .setBackground('#E5E7EB').setFontColor('#9CA3AF').setRanges([sh.getRange(HEAD + 1, 1, n, NCOL)]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$E' + r0 + '=""')
      .setBackground('#F8D7DA').setRanges([priceRange]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$E' + r0 + '<>$F' + r0)
      .setBackground('#FFB84D').setFontColor('#000000').setRanges([priceRange]).build(),
  ]);

  // 保護：只開放「價格、隱藏、推薦」欄，其他欄只有你（擁有者）能改
  const p = sh.protect().setDescription('只開放價格、隱藏、推薦欄');
  p.setUnprotectedRanges([priceRange, boxes]);
  const me = Session.getEffectiveUser();
  p.addEditor(me);
  p.removeEditors(p.getEditors().filter(u => u.getEmail() !== me.getEmail()));
  if (p.canDomainEdit()) p.setDomainEdit(false);

  logSheet_(ss); printSheet_(ss);
  ss.setActiveSheet(sh); ss.moveActiveSheet(1);
  try { ss.toast('價格表完成：共 ' + (items.length ? n : 0) + ' 格。', '菜單', 8); } catch (e) {}
}

// 讀價格表的每一列（相容舊的 6 欄格式）
function readRows_(sh) {
  const n = sh.getLastRow() - HEAD;
  if (n <= 0) return [];
  return sh.getRange(HEAD + 1, 1, n, NCOL).getValues().filter(r => String(r[0]).trim()).map(r => ({
    k: String(r[0]).trim(), cat: String(r[1]), name: String(r[2]), spec: String(r[3]),
    p: r[4] === '' ? '' : r[4], l: r[5] === '' ? '' : r[5],
    hidden: bool_(r[6]), star: r[7] === '' ? null : bool_(r[7]), side: String(r[8] || ''), tags: String(r[9] || ''),
  }));
}

// 從任何一個有「代碼」欄的分頁讀出已填的價格（例如之前匯入的範本）
function readAnyPrices_(ss) {
  const out = {};
  ss.getSheets().forEach(sh => {
    const name = sh.getName();
    if (name === LOG_NAME || name === PRINT_NAME) return;
    const v = sh.getDataRange().getValues();
    const hi = v.findIndex(r => r.some(c => String(c).indexOf('代碼') >= 0));
    if (hi < 0) return;
    const H = v[hi].map(String);
    const cK = H.findIndex(h => h.indexOf('代碼') >= 0);
    const cP = H.findIndex(h => h.indexOf('價格') >= 0 && h.indexOf('參考') < 0 && h.indexOf('上次') < 0);
    const cL = H.findIndex(h => h.indexOf('上次印製') >= 0);
    if (cK < 0 || cP < 0) return;
    for (let i = hi + 1; i < v.length; i++) {
      const k = String(v[i][cK]).trim();
      if (!k) continue;
      const p = str_(v[i][cP]), l = cL >= 0 ? str_(v[i][cL]) : '';
      const cur = out[k];
      if (!cur || (cur.p === '' && p !== '') || name === SHEET_NAME) out[k] = { p: p === '' ? '' : Number(p), l: l === '' ? '' : Number(l) };
    }
  });
  return out;
}

function logSheet_(ss) {
  let sh = ss.getSheetByName(LOG_NAME);
  if (!sh) {
    sh = ss.insertSheet(LOG_NAME);
    sh.appendRow(['時間', '誰', '品項', '原本', '改成', '從哪裡改']);
    sh.getRange(1, 1, 1, 6).setFontWeight('bold').setBackground('#1B4F8A').setFontColor('#ffffff');
    sh.setFrozenRows(1); sh.setColumnWidth(1, 150); sh.setColumnWidth(3, 280);
  }
  return sh;
}
function printSheet_(ss) {
  let sh = ss.getSheetByName(PRINT_NAME);
  if (!sh) {
    sh = ss.insertSheet(PRINT_NAME);
    sh.appendRow(['時間', '誰', '種類', '這次變動的價格', 'PDF 連結']);
    sh.getRange(1, 1, 1, 5).setFontWeight('bold').setBackground('#1B4F8A').setFontColor('#ffffff');
    sh.setFrozenRows(1); sh.setColumnWidth(1, 150); sh.setColumnWidth(4, 360); sh.setColumnWidth(5, 260);
  }
  return sh;
}

function str_(v) {
  if (v === '' || v === null || v === undefined) return '';
  const n = Number(v);
  return isNaN(n) ? String(v).trim() : String(Math.round(n));
}

// 直接在試算表改價格時，也記進「修改紀錄」
function onEdit(e) {
  try {
    if (saas_()) { const lid = PropertiesService.getScriptProperties().getProperty('legacyShopId'); if (!lid) return; useShop_(lid); }
    const sh = e.range.getSheet();
    if (sh.getName() !== SHEET_NAME || e.range.getColumn() > 5 || e.range.getLastColumn() < 5 || e.range.getLastRow() <= HEAD) return;
    const ss = sh.getParent();
    const who = (e.user && e.user.getEmail()) || '試算表';
    if (e.range.getNumRows() === 1 && e.range.getNumColumns() === 1) {
      const info = sh.getRange(e.range.getRow(), 2, 1, 3).getValues()[0].filter(String).join('・');
      logSheet_(ss).appendRow([new Date(), who, info, e.oldValue === undefined ? '' : e.oldValue, e.value === undefined ? '' : e.value, '試算表']);
    } else {
      logSheet_(ss).appendRow([new Date(), who, '（一次改了多格：第 ' + e.range.getRow() + '–' + e.range.getLastRow() + ' 列）', '', '', '試算表']);
    }
    const pr = props_();
    pr.setProperty('updatedAt', new Date().toISOString());
    pr.setProperty('updatedBy', who);
  } catch (err) {}
}

/* ================= 菜單工具網頁 ================= */
// 店家工具上傳的 Logo 資料（沒有 Tools.gs 或沒上傳過就是 null）
function uploadedLogo_() {
  try { return JSON.parse(props_().getProperty('t_logo') || 'null'); } catch (e) { return null; }
}
// Logo 色塊底色：手動指定 > 上傳時偵測到的底色 > 空白（＝照原本樣式）
function logoBg_() {
  const m = uploadedLogo_();
  if (!m) return '';
  if (m.bgManual) return m.bgManual;
  return m.bgMode !== 'transparent' && m.bg ? m.bg : '#FFFFFF';
}
// 讀雲端硬碟的 logo 圖片（放快取 6 小時）：優先用店家工具上傳的小圖，再來 LOGO_FILE_ID，最後用檔名搜尋
function logoDataUri_() {
  const cache = CacheService.getScriptCache();
  const hit = cache.get(ck_('logo')); if (hit !== null) return hit;
  let uri = '';
  try {
    let file = null;
    const up = uploadedLogo_();
    if (up && (up.webId || up.fileId)) { try { file = DriveApp.getFileById(up.webId || up.fileId); } catch (e) {} }
    if (!file && !saas_() && LOGO_FILE_ID) { try { file = DriveApp.getFileById(LOGO_FILE_ID); } catch (e) {} }
    if (!file && !saas_()) {
      const it = DriveApp.searchFiles('title contains "' + LOGO_NAME + '" and mimeType contains "image/" and trashed = false');
      if (it.hasNext()) file = it.next();
    }
    if (file) {
      let b = file.getBlob();
      if (b.getBytes().length > 70000) { try { b = file.getThumbnail(); } catch (e) { b = null; } }   // 圖太大就用雲端硬碟的縮圖
      if (b && b.getBytes().length <= 70000) uri = 'data:' + (b.getContentType() || 'image/png') + ';base64,' + Utilities.base64Encode(b.getBytes());
    }
  } catch (e) {}
  try { cache.put(ck_('logo'), uri, 21600); } catch (e) {}
  return uri;
}

// 注入到網頁 <script> 的資料：把 / 寫成 \/，避免出現連續兩個斜線被 Apps Script 當成註解砍掉
function js_(v) { return JSON.stringify(v).replace(/</g, '\\u003c').replace(/\//g, '\\/'); }

// 頁面共用的店家資訊（店名、聯絡方式…）給前端用
function brand_() {
  const c = shopCfg_();
  return { name: c.name, nameA: c.nameA, nameB: c.nameB, tagline: c.tagline, address: c.address, phone: c.phone, hours: c.hours, closedText: c.closedText,
    lineId: c.lineId, lineUrl: c.lineUrl, primary: c.primary, accent: c.accent, heroTag: c.heroTag, heroSub: c.heroSub, legacy: !!c.brandLegacy };
}
function page_(t, title) {
  return t.evaluate().setTitle(title)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
function loginPage_(mode, msg, extra) {
  const t = HtmlService.createTemplateFromFile('Login');
  t.boot = js_(Object.assign({ mode: mode, msg: msg || '', product: productName_(), plans: PLANS }, extra || {}));
  return page_(t, productName_() + '｜登入');
}
// 夥伴菜單工具頁（單店與線上服務共用）。key＝STAFF_KEY 或通行證
function menuPage_(key) {
  const t = HtmlService.createTemplateFromFile('Page');
  const cfg = brand_();
  t.logo = js_(logoDataUri_());
  t.logoBg = js_(logoBg_());
  t.staffKey = js_(key);
  t.toolsUrl = js_(typeof toolsPage_ === 'function' ? webUrl_() + '?p=tools&' + (saas_() ? 't=' : 'staff=') + key : '');
  t.homeUrl = js_(typeof homePage_ === 'function' ? webUrl_() + '?p=home&' + (saas_() ? 't=' : 'staff=') + key : '');
  t.ledgerUrl = js_(typeof ledgerPage_ === 'function' ? webUrl_() + '?p=ledger&' + (saas_() ? 't=' : 'staff=') + key : '');
  t.staffUrl = js_(typeof staffPage_ === 'function' && (!saas_() || CTX.role === 'owner') ? webUrl_() + '?p=staff&' + (saas_() ? 't=' : 'staff=') + key : '');
  t.brand = js_(cfg);
  t.sections = js_(typeof sectionsOf_ === 'function' ? sectionsOf_() : null);
  t.aiOn = js_(typeof aiOn_ === 'function' ? aiOn_() : false);
  t.acctUrl = js_(saas_() && CTX.role === 'owner' ? webUrl_() + '?p=account&t=' + key : '');
  t.setupUrl = js_(saas_() && CTX.role === 'owner' ? webUrl_() + '?p=setup&t=' + key : '');
  t.needSetup = js_(saas_() && CTX.role === 'owner' && !onboarded_());
  t.branches = js_(typeof branchList_ === 'function' && saas_() && CTX.role === 'owner' ? branchList_(CTX.shop).map(b => ({ id: b.id, name: b.name })) : []);
  t.brandUrl = js_(saas_() && CTX.role === 'owner' && !CTX.shop.brandId ? webUrl_() + '?p=brand&t=' + key : '');
  t.brandBack = js_(saas_() && CTX.uid === 'brand' ? webUrl_() + '?p=brand&t=' + tokenMake_({ s: CTX.shop.brandId, r: 'owner', u: 'owner', v: shopById_(CTX.shop.brandId).tv }, 1) : '');
  let boot = null;
  try { boot = getData_(); } catch (err) { boot = { error: 'server', detail: String(err && err.message || err) }; }
  t.boot = js_(boot);
  return page_(t, cfg.name + '｜菜單工具');
}
function brandPage_(key) {
  brandGuard_(key, false);
  const t = HtmlService.createTemplateFromFile('Brand');
  t.boot = js_({ token: key, menuUrl: webUrl_() + '?t=' + key });
  return page_(t, '分店管理');
}
function onboarded_() { return props_().getProperty('onboarded') === '1'; }
function setupPage_(key, done) {
  const t = HtmlService.createTemplateFromFile('Setup');
  const up = uploadedLogo_();
  t.boot = js_({ token: key, cfg: shopCfg_(), company: { name: CTX.shop.name, taxId: CTX.shop.taxId, editable: CTX.shop.taxId === '00000000' }, logo: logoDataUri_(), logoBg: logoBg_(), rule: T_LOGO_RULE, done: !!done,
    menuUrl: webUrl_() + '?t=' + key + '&later=1', skipUrl: webUrl_() + '?t=' + key + '&later=1' });
  return page_(t, '店家設定');
}
function accountPage_(key) {
  const t = HtmlService.createTemplateFromFile('Account');
  t.boot = js_({ token: key, role: CTX.role, menuUrl: webUrl_() + '?t=' + key, plans: PLANS, customerUrl: webUrl_() + '?s=' + CTX.shopId, setupUrl: webUrl_() + '?p=setup&t=' + key,
    brandUrl: !CTX.shop.brandId ? webUrl_() + '?p=brand&t=' + key : '', isBranch: !!CTX.shop.brandId });
  return page_(t, '帳號與夥伴');
}
function customerPage_(prm) {
  const t = HtmlService.createTemplateFromFile('Customer');
  const cfg = shopCfg_();
  t.logo = js_(logoDataUri_());
  t.logoBg = js_(logoBg_());
  let notices = [], closures = [];
  try { if (typeof tGetNotices === 'function') notices = tGetNotices(CTX.shopId); } catch (err) {}
  try { if (typeof tPublicClosures_ === 'function') closures = tPublicClosures_(); } catch (err) {}
  let docs = [];
  try { if (typeof stPublicDocs_ === 'function') docs = stPublicDocs_(); } catch (err) {}
  t.boot = js_({ page: prm.p || 'home', sid: CTX.shopId || '', brand: brand_(), links: { order: cfg.orderUrl, line: cfg.lineUrl, map: cfg.mapUrl, fb: cfg.fbUrl }, channels: cfg.channels, issues: ISSUE_TYPES, openDays: cfg.openDays, minDays: cfg.minDays, notices: notices, closures: closures, docs: docs });
  return page_(t, cfg.name + '｜顧客服務');
}

function doGet(e) {
  resetCtx_();
  const prm = (e && e.parameter) || {};
  if (saas_()) return doGetSaas_(prm);
  // 店家工具：?p=tools&staff=鑰匙（要放在菜單工具前面判斷）
  if (prm.p === 'tools' && prm.staff === STAFF_KEY && typeof toolsPage_ === 'function') return toolsPage_(e);
  if (prm.p === 'staff' && prm.staff === STAFF_KEY && typeof staffPage_ === 'function') return staffPage_(STAFF_KEY);
  if (prm.p === 'ledger' && prm.staff === STAFF_KEY && typeof ledgerPage_ === 'function') return ledgerPage_(STAFF_KEY);
  if (prm.p === 'home' && prm.staff === STAFF_KEY && typeof homePage_ === 'function') return homePage_(STAFF_KEY);
  if (prm.p === 'clock' && typeof clockPage_ === 'function') return clockPage_('', prm.jc);
  if (prm.p === 'apply' && typeof applyPage_ === 'function') return applyPage_('');
  if (prm.p === 'avail' && typeof availPage_ === 'function') return availPage_('', prm.jc);
  if (prm.p === 'join' && typeof joinPage_ === 'function') return joinPage_('', prm.jc);
  if (prm.staff === STAFF_KEY) return menuPage_(STAFF_KEY);
  return customerPage_(prm);
}

// 線上服務模式：?s=店家編號（顧客）、?t=通行證（夥伴）、?invite=邀請碼、?p=admin（管理後台）
function doGetSaas_(prm) {
  if (prm.p === 'admin') {
    const t = HtmlService.createTemplateFromFile('Admin');
    t.boot = js_({ product: productName_(), token: prm.a || '' });
    return page_(t, productName_() + '｜管理後台');
  }
  if (prm.ml) return loginPage_('magic', '', { ml: String(prm.ml).replace(/[^0-9a-f]/gi, '').slice(0, 64) });   /* 信裡的登入／驗證連結：頁面打開後在背景完成驗證 */
  if (prm.invite) return loginPage_('invite', '', { code: String(prm.invite) });
  if (prm.p === 'activate') return loginPage_('activate');
  const key = prm.t || prm.staff;
  if (key) {
    try {
      authGuard_(key, false);
      if (prm.p === 'tools') return toolsPage_({ parameter: { t: key, hiring: prm.hiring, tab: prm.tab } });
      if (prm.p === 'account') return accountPage_(key);
      if (prm.p === 'brand') return brandPage_(key);
      if (prm.p === 'staff') return staffPage_(key);
      if (prm.p === 'ledger') return ledgerPage_(key);
      if (prm.p === 'home') return homePage_(key);
      /* 店主第一次進來：先走設定精靈（店家資料、Logo、配色），之後才進菜單工具；夥伴不用 */
      if (prm.p === 'setup' && CTX.role === 'owner') return setupPage_(key, true);
      if (!prm.p && CTX.role === 'owner' && !prm.later && !onboarded_()) return setupPage_(key, false);
      return menuPage_(key);
    } catch (err) { return loginPage_('login', String(err && err.message || err), { go: 'menu' }); }
  }
  if (prm.s) {
    try { useShop_(prm.s); if (prm.p === 'clock') return clockPage_(prm.s, prm.jc); if (prm.p === 'apply') return applyPage_(prm.s); if (prm.p === 'avail') return availPage_(prm.s, prm.jc); if (prm.p === 'join') return joinPage_(prm.s, prm.jc); return customerPage_(prm); }
    catch (err) { return loginPage_('closed', String(err && err.message || err)); }
  }
  return loginPage_('login', '', { go: ['home', 'menu', 'tools', 'staff', 'ledger', 'account'].indexOf(prm.go) >= 0 ? prm.go : '' });
}

// JSON API：給「啟用工具」與官網呼叫。Content-Type 用 text/plain 避免瀏覽器預檢
function doPost(e) {
  resetCtx_();
  let out;
  try {
    const q = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const a = String(q.action || '');
    if (!saas_()) out = { ok: false, msg: '線上服務尚未啟用' };
    else if (a === 'login') out = authStart(q.taxId, q.password);
    else if (a === 'verify') out = authVerify(q.taxId, q.code, q.device);
    else if (a === 'register') out = regCreate(q);
    else if (a === 'regVerify') out = regVerify(q.taxId, q.code);
    else if (a === 'check') out = authCheck(q.token);
    else if (a === 'payNotify') out = payNotify(q.provider, q.params);
    else out = { ok: false, msg: '不支援的操作' };
  } catch (err) { out = { ok: false, msg: String(err && err.message || err) }; }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

// 前端呼叫（需要通行證／鑰匙；單店模式沿用舊行為：不檢查）
function getData(key) {
  if (saas_() || key) guardRead_(key);
  return getData_();
}
function getData_() {
  const ss = book_();
  if (!ss) return { error: 'noBook' };
  const sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) return { error: 'noSheet' };
  const rows = readRows_(sh).map(r => ({ k: r.k, cat: r.cat, name: r.name, spec: r.spec, p: str_(r.p), l: str_(r.l), hidden: r.hidden, star: r.star, side: r.side, tags: r.tags }));
  const prices = {}, last = {};
  rows.forEach(r => { prices[r.k] = r.p; last[r.k] = r.l; });
  const pr = props_();
  const lic = saas_() && CTX.lic ? { mode: CTX.lic.mode, label: CTX.lic.label, msg: CTX.lic.msg, watermark: !!CTX.lic.watermark, expires: CTX.lic.expires } : null;
  return {
    lic, tagDefs: TAG_DEFS, rows, prices, last,
    updatedAt: pr.getProperty('updatedAt') || '',
    updatedBy: pr.getProperty('updatedBy') || '',
    printedAt: pr.getProperty('printedAt') || '',
    ver: Number(pr.getProperty('ver') || 0),
    menuEmail: shopCfg_().menuEmail,
    demo: saas_() && typeof testAcct_ === 'function' && !!CTX.shop && testAcct_(CTX.shop.taxId),
  };
}

// changes = { 代碼: '價格' }
function guard_(key) { return authGuard_(key, true); }
function guardRead_(key) { return authGuard_(key, false); }

function setPrices(changes, key) {
  guard_(key);
  const ovs = [];   // 分店改價：記成個別價（品牌同步不會蓋掉）
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const ss = book_(), sh = ss.getSheetByName(SHEET_NAME);
    if (!sh) return { error: 'noSheet' };
    const n = sh.getLastRow() - HEAD;
    const keys = sh.getRange(HEAD + 1, 1, n, 1).getValues().map(r => String(r[0]).trim());
    const now = new Date(), logRows = [];
    Object.keys(changes || {}).forEach(k => {
      const i = keys.indexOf(k);
      if (i < 0) return;
      const v = String(changes[k]).replace(/[^0-9]/g, '').slice(0, 4);
      const row = HEAD + 1 + i;
      const cell = sh.getRange(row, 5);
      const old = str_(cell.getValue());
      if (old === v) return;
      cell.setValue(v === '' ? '' : Number(v));
      const info = sh.getRange(row, 2, 1, 3).getValues()[0].filter(String).join('・');
      logRows.push([now, '', info, old, v, '菜單工具']);
      const ic = sh.getRange(row, 2, 1, 3).getValues()[0];
      if (v !== '') ovs.push({ k: [ic[0], ic[1], ic[2]].join('|'), v: Number(v) });
    });
    if (logRows.length) {
      const lg = logSheet_(ss);
      lg.getRange(lg.getLastRow() + 1, 1, logRows.length, 6).setValues(logRows);
      const pr = props_();
      pr.setProperty('updatedAt', now.toISOString());
      pr.setProperty('updatedBy', '菜單工具');   // 修正：原本寫 who（沒有定義），會讓每次改價都報錯重試
    }
  } finally { lock.releaseLock(); }
  if (ovs.length && typeof branchOverrideNote_ === 'function') branchOverrideNote_(ovs);
  return getData_();
}

/* ---------- 品項管理：新增、隱藏、刪除（只有夥伴工具能用） ---------- */
function logItem_(ss, what, info) {
  logSheet_(ss).appendRow([new Date(), '', info, '', what, '菜單工具']);
  const pr = props_();
  pr.setProperty('updatedAt', new Date().toISOString());
}
function itemRowIdx_(sh, item) {   // 回傳這個品項在試算表的列號（由大到小）
  const n = sh.getLastRow() - HEAD; if (n <= 0) return [];
  const keys = sh.getRange(HEAD + 1, 1, n, 1).getValues();
  const out = []; keys.forEach((r, i) => { if (itemOf_(String(r[0]).trim()) === item) out.push(HEAD + 1 + i); });
  return out.reverse();
}

function setHidden(item, hidden, key) {
  guard_(key);
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const ss = book_(), sh = ss.getSheetByName(SHEET_NAME);
    const idx = itemRowIdx_(sh, item);
    if (!idx.length) throw new Error('找不到這個品項');
    idx.forEach(r => sh.getRange(r, 7).setValue(!!hidden));
    logItem_(ss, hidden ? '隱藏' : '取消隱藏', item.split('|')[1]);
  } finally { lock.releaseLock(); }
  return getData_();
}

// it = { sid, cat, name, side, star, cols: [{ spec, price }]（price 為 null 表示不供應） }
function addItem(it, key) {
  guard_(key);
  const name = String(it && it.name || '').replace(/[|<>]/g, '').trim().slice(0, 30);
  if (!name) throw new Error('請輸入品項名稱');
  const sid = String(it.sid || '').replace(/[^a-z]/g, '');
  const cols = (it.cols || []).map((c, i) => ({ i, spec: String(c.spec || ''), price: c.price === null ? null : String(c.price || '').replace(/[^0-9]/g, '').slice(0, 4) })).filter(c => c.price !== null);
  if (!sid || !cols.length) throw new Error('至少要有一個規格');
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const ss = book_(), sh = ss.getSheetByName(SHEET_NAME);
    const item = sid + '|' + name;
    if (itemRowIdx_(sh, item).length) throw new Error('這個分類已經有「' + name + '」了');
    const n = sh.getLastRow() - HEAD;
    const keys = n > 0 ? sh.getRange(HEAD + 1, 1, n, 1).getValues().map(r => String(r[0])) : [];
    let at = -1; keys.forEach((k, i) => { if (k.split('|')[0] === sid) at = i; });
    const rows = cols.map(c => [item + '|' + c.i, String(it.cat || ''), name, c.spec, c.price === '' ? '' : Number(c.price), '', false, !!it.star, String(it.side || '').slice(0, 30), tagsClean_(it.tags).join(',')]);
    let row;
    if (at >= 0) { row = HEAD + 1 + at + 1; sh.insertRowsAfter(row - 1, rows.length); }
    else row = sh.getLastRow() + 1;
    sh.getRange(row, 1, rows.length, NCOL).setValues(rows);
    const del = deleted_().filter(x => x !== item);
    props_().setProperty('deleted', JSON.stringify(del));
    logItem_(ss, '新增品項', it.cat + '・' + name);
  } finally { lock.releaseLock(); }
  return getData_();
}

// 設定品項的標示（過敏原、素食、辣）。item = 'sid|品項'，tags = ['egg','veg',…]
function setTags(item, tags, key) {
  guard_(key);
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const ss = book_(), sh = ss.getSheetByName(SHEET_NAME);
    const idx = itemRowIdx_(sh, item);
    if (!idx.length) throw new Error('找不到這個品項');
    const v = tagsClean_(tags).join(',');
    idx.forEach(r => sh.getRange(r, 10).setNumberFormat('@').setValue(v));
    logItem_(ss, '標示：' + (v || '（無）'), item.split('|')[1]);
  } finally { lock.releaseLock(); }
  return getData_();
}

function deleteItem(item, key) {
  guard_(key);
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const ss = book_(), sh = ss.getSheetByName(SHEET_NAME);
    const idx = itemRowIdx_(sh, item);
    if (!idx.length) throw new Error('找不到這個品項');
    idx.forEach(r => sh.deleteRow(r));
    if (ITEMS.some(x => itemOf_(x[0]) === item)) {   // 內建品項要記住，重新整理價格表時才不會又出現
      const del = deleted_(); if (del.indexOf(item) < 0) del.push(item);
      props_().setProperty('deleted', JSON.stringify(del));
    }
    logItem_(ss, '刪除品項', item.split('|')[1]);
  } finally { lock.releaseLock(); }
  return getData_();
}

// 取得版本號：正式菜單每產生一次就 +1（V1、V2…）；核對表不加號，只標示依哪一版產生
function reserveVersion(mode, key) {
  guard_(key);
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const pr = props_();
    let n = Number(pr.getProperty('ver') || 0);
    const d = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy/MM/dd HH:mm');
    if (mode === 'menu') { n += 1; pr.setProperty('ver', String(n)); return { no: n, label: '版本 V' + n + '｜' + d }; }
    return { no: n, label: '核對表（依 V' + n + '）｜' + d };
  } finally { lock.releaseLock(); }
}

// 存 PDF 到雲端硬碟；mode = 'menu'（正式菜單，會更新「上次印製」）或 'blank'（空白核對表）
function savePdf(b64, filename, mode, key, ver) {
  guard_(key);
  const ss = book_();
  const folder = subFolder_(FOLDER_NAME, '菜單PDF');
  const file = folder.createFile(Utilities.newBlob(Utilities.base64Decode(b64), 'application/pdf', filename));
  try { file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW); } catch (e) {}

  const changed = [];
  if (mode === 'menu') {
    const lock = LockService.getScriptLock();
    lock.waitLock(20000);
    try {
      const sh = ss.getSheetByName(SHEET_NAME);
      const n = sh.getLastRow() - HEAD;
      const v = sh.getRange(HEAD + 1, 1, n, 6).getValues();
      v.forEach(r => {
        if (String(r[0]).trim() && str_(r[4]) !== str_(r[5]))
          changed.push([r[1], r[2], r[3]].filter(String).join('・') + '：' + (str_(r[5]) || '空白') + ' → ' + (str_(r[4]) || '空白'));
      });
      sh.getRange(HEAD + 1, 6, n, 1).setValues(v.map(r => [r[4]]));
      props_().setProperty('printedAt', new Date().toISOString());
    } finally { lock.releaseLock(); }
  }
  printSheet_(ss).appendRow([new Date(), '', (mode === 'menu' ? '正式菜單 ' : '空白核對表 ') + (ver || ''),
    mode === 'menu' ? (changed.length ? changed.join('\n') : '（跟上次一樣）') : '—', file.getUrl()]);
  return { url: file.getUrl(), fileId: file.getId(), data: getData_() };
}

// 把剛產生的菜單 PDF 當附件寄出
function emailPdf(fileId, to, key) {
  guard_(key);
  to = String(to || '').trim();
  if (!/^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/.test(to)) throw new Error('Email 格式不對');
  const file = DriveApp.getFileById(fileId);
  if (file.getParents().next().getId() !== subFolder_(FOLDER_NAME, '菜單PDF').getId()) throw new Error('找不到這份菜單檔');
  if (typeof mailSend_ === 'function') {
    mailSend_(to, '【' + shopCfg_().name + '】菜單 ' + file.getName(), '附件是最新的菜單 PDF：' + file.getName() + '\n\n也可以用這個連結開啟：' + file.getUrl() + '\n\n（由菜單工具自動寄出）', null, { brand: 'shop', btn: '打開菜單 PDF', attachments: [file.getBlob()] });
    return { ok: true, to: to };
  }
  MailApp.sendEmail({
    to: to,
    subject: '【' + shopCfg_().name + '】菜單 ' + file.getName(),
    body: '附件是最新的菜單 PDF：' + file.getName() + '\n\n也可以用這個連結開啟：' + file.getUrl() + '\n\n（由菜單工具自動寄出）',
    attachments: [file.getBlob()],
    name: shopCfg_().name + ' 菜單工具',
  });
  return { ok: true, to: to };
}


/* ================= 顧客服務：異常協助、許願、敲敲老闆、預訂 ================= */

// 給顧客挑品項用：依分類整理，只列出有價格的品項（不含加料）
function getCatalog(sid) {
  if (saas_()) useShop_(sid);
  const d = getData_();
  if (d.error) return { error: d.error };
  const cats = [], byCat = {};
  d.rows.forEach(r => {
    if (r.hidden || r.cat.indexOf('加料') === 0 || r.p === '') return;
    if (!byCat[r.cat]) { byCat[r.cat] = { name: r.cat, items: [] }; cats.push(byCat[r.cat]); }
    byCat[r.cat].items.push({ k: r.k, name: r.name, spec: r.spec, price: Number(r.p), star: !!r.star });
  });
  return { cats };
}

// 顧客電子菜單（公開）：只含沒隱藏、有價格的品項，依價格表順序分類；一個品項的多個規格合成一筆
function getMenu(sid) {
  if (saas_()) useShop_(sid);
  const d = getData_();
  if (d.error) return { error: d.error };
  const cats = [], byCat = {}, byItem = {};
  const secs = typeof sectionsOf_ === 'function' ? (sectionsOf_() || []) : [];
  d.rows.forEach(r => {
    if (r.hidden || r.p === '') return;
    if (!byCat[r.cat]) { const sc = secs.filter(s => s.t === r.cat)[0]; byCat[r.cat] = { name: r.cat, note: sc && sc.note ? sc.note : '', items: [] }; cats.push(byCat[r.cat]); }
    const ik = r.cat + '|' + r.name;
    let it = byItem[ik];
    if (!it) { it = byItem[ik] = { name: r.name, side: r.side || '', star: !!r.star, tags: tagsClean_(r.tags), prices: [] }; byCat[r.cat].items.push(it); }
    it.prices.push({ spec: r.spec, price: Number(r.p) });
  });
  const c = shopCfg_();
  return { cats, tagDefs: TAG_DEFS, primary: c.primary, accent: c.accent };
}

function priceMap_() {
  const d = getData_(), m = {};
  d.rows.forEach(r => { if (!r.hidden && r.p !== '') m[r.k] = { label: r.name + (r.spec ? '（' + r.spec + '）' : ''), price: Number(r.p) }; });
  return m;
}

function custSheet_(type) {
  const cfg = CUSTOMER_SHEETS[type], ss = book_();
  let sh = ss.getSheetByName(cfg.name);
  if (!sh) {
    sh = ss.insertSheet(cfg.name);
    sh.appendRow(cfg.head);
    sh.getRange(1, 1, 1, cfg.head.length).setFontWeight('bold').setBackground('#1B4F8A').setFontColor('#ffffff');
    sh.setFrozenRows(1);
    const col = cfg.head.indexOf('狀態') + 1;
    const opts = type === 'pre' ? ['待確認', '已確認', '已完成', '取消'] : ['待處理', '處理中', '已完成'];
    sh.getRange(2, col, 999, 1).setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(opts, true).build());
    sh.setColumnWidths(1, cfg.head.length, 120);
  }
  return sh;
}

function nextId_(prefix) {
  const d = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyMMdd');
  const pr = props_(), key = 'seq_' + prefix + d;
  const n = Number(pr.getProperty(key) || 0) + 1;
  pr.setProperty(key, String(n));
  return prefix + d + '-' + ('00' + n).slice(-3);
}

function clean_(v, max) { return String(v == null ? '' : v).replace(/[<>]/g, '').trim().slice(0, max || 500); }

function lines_(list, withPrice) {
  const m = priceMap_(); let total = 0, count = 0; const out = [];
  (list || []).slice(0, 60).forEach(x => {
    const it = m[x.k]; const q = Math.max(1, Math.min(200, parseInt(x.q, 10) || 1));
    if (!it) return;
    count += q; total += it.price * q;
    out.push(it.label + ' × ' + q + (withPrice ? '（' + (it.price * q) + ' 元）' : ''));
  });
  return { text: out.join('\n'), total, count };
}

function notify_(subject, body, type) {
  try {
    if (type && typeof notifyOn_ === 'function' && !notifyOn_(type)) return;
    if (saas_()) subject = subject.replace('【弘林】', '【' + shopCfg_().name + '】');
    const to = shopCfg_().notifyEmail || (saas_() && CTX.shop ? CTX.shop.email : Session.getEffectiveUser().getEmail());
    if (to && typeof mailSend_ === 'function') mailSend_(to, subject, body + '\n\n打開試算表處理：\n' + book_().getUrl(), null, { btn: '打開試算表處理' });
    else if (to) MailApp.sendEmail(to, subject, body + '\n\n→ 打開試算表處理：' + book_().getUrl());
  } catch (e) {}
}

function antiSpam_(f) {
  if (saas_()) useShop_(f && f.sid);
  if (f.hp) throw new Error('送出失敗');                       // 機器人會填隱藏欄位
  if (Date.now() - Number(f.t0 || 0) < 3000) throw new Error('太快了，請再按一次送出');
}

function submitHelp(f) {
  antiSpam_(f);
  if (!clean_(f.contact)) throw new Error('請留下聯絡方式');
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const id = nextId_('H');
    let photos = [];
    if (f.photos && f.photos.length) {
      const folder = subFolder_('弘林_顧客回報照片', '顧客回報照片');
      photos = f.photos.slice(0, 3).map((b64, i) => folder.createFile(Utilities.newBlob(Utilities.base64Decode(b64), 'image/jpeg', id + '_' + (i + 1) + '.jpg')).getUrl());
    }
    const items = lines_(f.items, false).text;
    custSheet_('help').appendRow([id, new Date(), clean_(f.channel, 40), clean_(f.orderNo, 60), clean_(f.orderDate, 20),
      (f.issues || []).map(x => clean_(x, 40)).join('、'), items, clean_(f.detail, 1000), clean_(f.want, 40), clean_(f.contact, 100), photos.join('\n'), '待處理', '', '']);
    notify_('【弘林】新的異常回報 ' + id, '管道：' + f.channel + '\n訂單編號：' + f.orderNo + '\n異常：' + (f.issues || []).join('、') + '\n品項：\n' + items + '\n說明：' + f.detail + '\n聯絡：' + f.contact, 'help');
    return { id };
  } finally { lock.releaseLock(); }
}

function submitWish(f) {
  antiSpam_(f);
  if (!clean_(f.item)) throw new Error('請寫下想吃的品項');
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const id = nextId_('W');
    custSheet_('wish').appendRow([id, new Date(), clean_(f.item, 100), clean_(f.detail, 1000), clean_(f.contact, 100), '待處理', '']);
    notify_('【弘林】新的許願 ' + id, '想吃：' + f.item + '\n說明：' + f.detail, 'wish');
    return { id };
  } finally { lock.releaseLock(); }
}

function submitKnock(f) {
  antiSpam_(f);
  if (!clean_(f.msg)) throw new Error('請寫下想說的話');
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const id = nextId_('K');
    custSheet_('knock').appendRow([id, new Date(), clean_(f.to, 10), clean_(f.msg, 1000), f.reply ? '要' : '不用', clean_(f.contact, 100), '待處理', '']);
    notify_('【弘林】敲敲' + f.to + ' ' + id, f.msg + (f.reply ? '\n（需要回覆）聯絡：' + f.contact : ''), 'knock');
    return { id };
  } finally { lock.releaseLock(); }
}

function submitPreorder(f) {
  antiSpam_(f);
  if (!clean_(f.name) || !clean_(f.phone)) throw new Error('請填姓名和電話');
  const d = new Date(String(f.date) + 'T00:00:00+08:00');
  if (isNaN(d)) throw new Error('請選取餐日期');
  const today = new Date(Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd') + 'T00:00:00+08:00');
  const minD = shopCfg_().minDays;
  if ((d - today) / 86400000 < minD) throw new Error('預訂最晚要提前 ' + minD + ' 天');
  // 店休行事曆（Tools.gs）：特別店休、特別營業都算進去；沒有 Tools.gs 時照原本的每週公休
  if (typeof tClosedInfo_ === 'function') {
    const ci = tClosedInfo_(String(f.date));
    if (ci.closed) throw new Error('這天' + (ci.reason ? '（' + ci.reason + '）' : '') + '公休，請選其他日期');
  } else {
    const wd = Number(Utilities.formatDate(d, 'Asia/Taipei', 'u')) % 7;
    if (shopCfg_().openDays.indexOf(wd) < 0) throw new Error('這天公休，請選其他日期');
  }
  const L = lines_(f.items, true);
  if (!L.count) throw new Error('請至少選一個品項');
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const id = nextId_('R');
    custSheet_('pre').appendRow([id, new Date(), clean_(f.date, 12), clean_(f.time, 8), clean_(f.name, 40), clean_(f.phone, 30), L.text, L.count, L.total, clean_(f.note, 500), '待確認', '']);
    notify_('【弘林】新的預訂 ' + id + '（' + f.date + ' ' + f.time + '）', f.name + ' ' + f.phone + '\n' + L.text + '\n預估：' + L.total + ' 元\n備註：' + f.note, 'pre');
    return { id, total: L.total, count: L.count };
  } finally { lock.releaseLock(); }
}
