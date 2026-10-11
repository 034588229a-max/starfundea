"""商家指南說明書（HTML 單檔＋PDF）。內容寫在下面的 CHAPTERS，畫面截圖來自 guide/shots/（先執行 make_guide_shots.py）。
輸出：guide/SFD系統使用指南.html、guide/SFD系統使用指南.pdf，並複製到 publish/guide/（給網站使用）。
改產品名稱：改 PRODUCT；改內容：改 CHAPTERS 後重新執行。"""
import asyncio, base64, html, os, shutil
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, 'guide', 'shots'); OUT = os.path.join(ROOT, 'guide')
PRODUCT = '星樂創意 StarFunDea'
VERSION = 'v1.1　2026.10'

def svg(name):
    p = os.path.join(ROOT, 'brand', 'official', name)
    return 'data:image/svg+xml;base64,' + base64.b64encode(open(p, 'rb').read()).decode()

def img(name):
    p = os.path.join(SHOTS, name + '.png')
    return 'data:image/png;base64,' + base64.b64encode(open(p, 'rb').read()).decode() if os.path.isfile(p) else ''

# 每個項目：(標題, 一句話說明, [步驟…], 小提醒或 None, 截圖名稱或 None)
CHAPTERS = [
 ('開始使用', 'START', [
  ('登入', '第一次用，先登入你的店。', ['第一次用：打開「帳號已開通」信裡的連結（或在登入頁按「首次開通／忘記密碼」），輸入統一編號、收信箱的驗證碼，設定你自己的密碼，設好就直接登入。客服看不到這組密碼。', '之後登入：打開網址（或手機桌面的 App 圖示），輸入統一編號和密碼，按「寄送驗證碼」。', '到註冊時的信箱收 6 位數驗證碼（沒收到請看垃圾信件匣），輸入後登入。', '登入後這支手機會記住你，下次直接進入。', '夥伴（店內幫手）不用密碼：請店主在「帳號與訂閱」產生邀請連結，用手機打開並綁定即可。'], '驗證碼 5 分鐘內有效；連續輸錯 5 次會鎖 15 分鐘。', '01-login'),
  ('主畫面', '登入後先看到主畫面，所有功能都是大按鈕。', ['功能分成六類：菜單、行銷、店務、財務、人員、設定與帳號。', '按鈕右上角的小徽章是「現在要處理的事」，例如「1 件待處理」（待核准的請假、徵才登記）、「今日支出 4,380」。', '夥伴只看得到菜單、行銷、店務、財務和打卡；人員、設定、帳號只有店主看得到。', '每個功能頁左上角都有「主畫面」可以回來。'], None, '02-home'),
  ('安裝成手機 App', '把常用功能放在手機桌面，一點就開、全螢幕。', ['iPhone：用 Safari 打開網址 → 點下方「分享」→「加入主畫面」。', 'Android：用 Chrome 打開網址 → 右上角「⋮」→「安裝應用程式」。', '員工打卡、店主管理、顧客菜單可以各裝一個圖示；功能更新時不用重裝。'], '如果打不開，請改用瀏覽器的「無痕分頁」；同時登入多個 Google 帳號有時會造成打不開。', None),
  ('店家設定精靈', '第一次登入先花 3 分鐘設好店家資料，之後所有海報、名片、菜單都會自動帶入。', ['第 1 步：填店名、標語、地址（縣市下拉，只要填路和號）、電話（室內或行動分開填）、LINE ID（會自動產生官方網址）、營業時間。', '第 2 步：上傳 Logo（系統會檢查解析度，並偵測底色）。', '第 3 步：選配色（20 組範本，或自己選主色與強調色），右邊即時預覽。', '想改，隨時回「設定精靈」。'], None, '28-setup'),
 ]),
 ('菜單', 'MENU', [
  ('改價格', '在手機上直接改，不用再改 Excel。', ['主畫面按「菜單改價」。', '點價格欄直接輸入新價格，系統約 1 秒自動存到你的 Google 試算表，不用按儲存。', '用上方搜尋框或分類標籤快速找到品項。', '下方會顯示「跟上次印的菜單不同 N 格」，改了哪些一目了然。'], '其他夥伴的手機約 15 秒自動同步，不會互相蓋掉。', '03-menu'),
  ('新增、隱藏與標示品項', '品項多的時候，管理起來要輕鬆。', ['每個分類最下面按「＋ 新增品項」，填名稱和價格。', '品項右邊的「⋯」可以：標「推薦」（菜單上會有星號）、隱藏（不印也不顯示給顧客）、加附餐說明。', '同一個選單可以設過敏原與素食標示：蛋、奶、花生、堅果、麩質、大豆、甲殼、魚、芝麻、素、純素、辣，共 12 種，印在菜單上，也讓顧客篩選。', '右上角「分類」可以改分類名稱、增減分類、設定價格欄（例如「中杯,大杯」），也有早餐店、飲料店、小吃店的範本。'], None, None),
  ('調價助手', '食材漲價時，一次調整整批價格。', ['按「調價助手」。', '選要調的分類（或全部）、選「加減金額」或「加減百分比」、填數字，選取整到 5 或 10 元。', '畫面會逐項列出「舊價 → 新價」，可以取消不想動的品項。', '確認後按套用；錯了可以一鍵復原。輸出新菜單時，變動的價格會用橘色底標出來。'], '調完價記得把新菜單輸出，或重新貼到門口；每次改價都會自動留下紀錄（誰、何時、舊價、新價）。', None),
  ('菜單範本批量設定', '品項很多、或想用 Excel 整理時，用範本一次建好。', ['按「菜單範本」→「下載範本」，用 Excel 或 Google 試算表填：分類、品項、價格、標示。', '也可以「匯出現有菜單」，改好價格再上傳。', '上傳後系統會先檢查並列出有問題的列（例如價格不是數字），你確認再寫入。'], '上傳不會刪掉你現有的品項，只會新增或更新價格。', None),
  ('輸出 A3 菜單', '按一個鍵，得到排好版的 A3 菜單 PDF。', ['改好價格後按「預覽」，可以直接點菜單上的價格再修改。', '按「輸出 PDF」。系統自動把品項平均分成四欄、拉齊留白。', '品項太多時先自動縮小列高；還放不下，會把整個分類排到背面（也可以勾「只印單面」）。', '每次輸出版本號自動加一，並記下相較上一版變動了哪些項目。'], None, None),
  ('顧客電子菜單', '客人掃 QR Code 就能看最新價格。', ['顧客網址在「帳號與訂閱」可以複製（格式是 …?s=店家代碼&p=menu）。', '到「行銷」的桌號 QR 做成桌上的 QR 海報。', '顧客可以篩選素食、純素、不辣，並避開指定過敏原；價格永遠是最新的，不用重印 QR。'], '標示僅供參考；有嚴重過敏的客人，請提醒他向店家確認。', '26-customer-menu'),
 ]),
 ('行銷', 'MARKETING', [
  ('公告海報', '臨時公休、活動、節慶，三分鐘做好一張海報，印得出也貼得上社群。', ['主畫面「行銷」→「公告海報」。', '選類別：臨時公休、休假、營業時間調整、活動優惠、節慶祝福、新品上市、徵才、一般公告。', '選輸出比例：A4（印出來貼門口）、1:1（FB、LINE 貼文）、9:16（限時動態）。店家 Logo 會自動帶入。', '套用範本後改文字；內容多會自動縮字，保證一頁。14 個節日會自動帶出下一次日期。', '按「預覽」確認，再按「儲存並產生 PDF」，或按「下載圖片（PNG）」直接傳到 LINE、FB。', '勾「顧客頁顯示」，顧客打開店家頁面就會看到這則公告。'], '公告可以重複編輯；已經產生過的海報會留在「已儲存的公告」。', '06-tools-notice'),
  ('桌號 QR', '桌上、候位、外帶，一次印好。', ['按「桌號 QR」，貼上多桌網址（一行一桌），系統自動編號並防止重複。', '選類型：桌號點餐、候位點餐、外帶自取；選紙張：A5 雙拼、A4、A6 四拼。', '每張都有核對碼，印出來後可以掃一遍確認網址正確。', '按「儲存並產生 PDF」。'], None, '07-tools-table'),
  ('Wi-Fi 卡', '客人掃一下就連上網，不用再問密碼。', ['按「Wi-Fi 卡」，填網路名稱、密碼、加密方式（一般選 WPA）。', '可以選要不要在卡片上印出密碼；有隱藏網路也能設定。', '紙張選 A6 四拼（一張 A4 切四張）、A5 雙拼或 A4。', '預覽沒問題就產生 PDF。'], '手機相機掃到會直接跳出「加入網路」。', '08-tools-wifi'),
  ('名片', '90×54 mm，正面放資訊與 LINE QR，背面是置中的 Logo。', ['按「名片」，選版型（4 種）和配色（預設跟店家配色，也有 8 組範本）。', '填店名、姓名、職稱、電話、營業時間、付款方式（例如現金、LINE Pay、全支付）、地址、LINE。', '正面的 QR Code 預設連到你的 LINE 官方帳號，客人掃了就加好友；也可以改連電子菜單、敲敲老闆、地圖或自訂網址。', '背面固定是置中的 Logo，不放其他字。', '輸出兩種：「印刷廠用」（含 3 mm 出血）；「A4 十張」（附裁切記號，自己印）。右邊可選「雙面」（正面＋Logo 背面，預設）或「只印正面」。'], '列印請選「實際大小」，不要選「縮放符合頁面」。', '09-tools-card'),
  ('徵才海報與面試登記', '想徵人，海報上的 QR Code 直接讓人登記面試。', ['主畫面「行銷」→「徵才海報」，會直接開啟徵才範本，QR Code 已經連到面試登記頁。', '應徵者掃碼後填姓名、聯絡方式、想應徵的職位和方便的時段。', '你到「人員與班表」→「徵才」看登記名單，選好日期時間按「約面試並通知」，系統會寄確認信給應徵者；錄取的人可以一鍵轉成員工。', '新登記會寄信到店家通知信箱。'], None, '24-apply'),
  ('LINE 圖文選單', '客人加 LINE 好友後，從選單看菜單、營業時間、收款方式。', ['主畫面「行銷」→「名片」旁的「LINE 選單」分頁。', '選 2、4 或 6 格，選大圖（2500×1686，建議）或小圖。', '每一格改標題、小字、圖示，並選「點下去」要去哪：電子菜單、顧客首頁、大單預訂、敲敲老闆、撥電話、自訂網址。', '按「預覽」確認，按「下載圖檔（PNG）」。再照畫面下方的步驟，到 LINE 官方帳號後台上傳，並貼上各格連結（畫面有清單可複製）。'], '收款方式只是「顯示」，系統不代收款；大單需先付訂金，客人掃碼洽詢，由你自己收。', '31-tools-rich'),
 ]),
 ('店務', 'OPERATIONS', [
  ('店休日曆', '什麼時候休息、什麼時候特別營業，一次設好。', ['按「店休日曆」，先設每週固定公休日。', '再加「特別店休」（例如設備保養、連假）或「特別營業」，填起訖日與原因。', '勾「顯示在顧客頁」，顧客首頁會提醒；預訂也會自動擋下店休日。', '可以一鍵把店休做成公告，或輸出 A4 的營業日曆海報。'], None, '05-tools-cal'),
  ('交接紀錄', '各班交代清楚，隔天上班的人不會漏掉。', ['按「交接紀錄」，看今日摘要（今明營業狀態、預訂、待處理）。', '「寫交接」：選班別、填名字、選緊急程度（急、一般、緩）、可指定交給某位夥伴（不選就是當天有班的人）、寫內容。', '需要後續處理的勾「待處理」；急的會排在最上面。', '隔天早上 9 點後，系統自動寄信提醒你和相關的夥伴；夥伴也能在自己的員工入口按「處理完成」，你這邊同步看得到。'], '沒處理完的交接，每天最多提醒一次。', '04-tools-hand'),
 ]),
 ('財務：店務收支', 'FINANCE', [
  ('設定固定廠商', '常叫貨的廠商先設好，之後記帳只要點一下。', ['主畫面「財務」→「店務收支」→「廠商」分頁（店主才有）。', '填廠商名稱、預設分類、預設付款方式（現金、轉帳、信用卡、月結）、最多 4 個常用金額。', '勾「設為常用廠商」，會排在記帳畫面最前面。', '選「叫貨日」（週幾）、叫貨時間、負責叫貨的人；叫貨日當天系統會寄信提醒你和負責的夥伴。', '按「儲存廠商」。不再合作的廠商按「停用」，歷史紀錄會保留。'], '固定廠商最多 30 家。', '14-ledger-vendors'),
  ('快速記帳', '像點餐機一樣：點廠商、按數字、記下。', ['在「記帳」分頁點一家廠商，會開全螢幕的記帳面板。', '用數字鍵盤輸入含稅總金額，或直接點常用金額（含「上次金額」）。', '選付款方式與日期（今天或昨天）。', '憑證選「統一發票」：填發票號碼（2 個英文字母加 8 位數字，例如 AB12345678），系統自動算出應稅金額（含稅 ÷ 1.05）與稅額，可以手動改，免稅就勾「免稅」。', '有收據或發票，按「收據照片」拍照上傳，檔案存進你自己的雲端。夥伴替店裡採購也一樣可以登記、上傳。', '填購買品項、選採購人員，按「記下」。剛記完 10 秒內有「撤銷」可以反悔。'], '同一個發票號碼重複記，系統會提醒；確認不是重複再選「仍要記帳」。收據、無憑證的支出不計入進項稅額。', '12-ledger-sheet'),
  ('叫貨提醒與憑證正本', '不漏叫貨、不漏收憑證。', ['記帳首頁最上面的「今天要叫貨」會列出今天要叫的廠商，叫完按「已叫貨」；負責的夥伴也能在員工入口按。', '叫貨日沒叫完，隔天系統會再提醒一次，你看得到哪一家還沒叫。', '統一發票和收據會標「憑證正本：未收到」；收到後到「報表」按「已收到正本」，「憑證正本還沒收到」清單就會少一筆。', '「看收據」可以打開當時上傳的照片（只有店主打得開）。'], None, '13-ledger-report'),
  ('其他支出與收入', '水電、租金、雜支，還有每天的營業額。', ['首頁下方的橘色「其他支出」：選分類（人事、租金、水電瓦斯、設備維修、行銷廣告、雜支、其他…），輸入金額。', '綠色「收入」：記現場營業額、外送平台、線上訂單等，付款方式沒有「月結」。', '「今日」分頁列出今天所有明細與收入、支出、淨額；記錯可以刪除（夥伴只能撤銷自己 10 分鐘內記的）。'], None, '11-ledger'),
  ('月結與結清', '月結的廠商，記得哪些還沒付。', ['付款方式選「月結」記帳，這筆會標成「未付」。', '到「報表」分頁的「月結待付款」，會列出每家廠商未付的金額。', '付清之後按那家廠商的「全部結清」（要按兩次確認）。'], None, None),
  ('月報表', '月底對帳、給會計，都在這裡。', ['「報表」分頁（店主才有）可以切換月份。', '大數字：收入、支出、淨額、月結待付。', '往下看：支出分類、廠商支出排行、採購人員、統一發票（張數、含稅合計、應稅金額、進項稅額）、本月明細。', '按「下載 CSV」或「複製 CSV」，貼到 Excel 或 Google 試算表交給會計。'], '這裡是記帳與整理工具，不是報稅系統；稅務申報請交給會計師。', '13-ledger-report'),
 ]),
 ('人員與班表', 'STAFF', [
  ('建立員工資料', '老闆只要輸入 Email，其餘員工自己完成。', ['主畫面「人員」→「人員與班表」，第一個分頁是「① 員工」。', '輸入員工姓名、信箱、到職日（特休天數依此計算），按「產生連結」；有填信箱會直接寄邀請信。連結 7 天內有效、只能用一次。', '員工打開後填姓名、手機、地址、緊急聯絡人，拍照上傳身分證正反面與存摺封面（只存進你的雲端，只有你看得到），並設定自己的打卡 PIN。', '填完系統自動寄「登陸完成」信給員工，附他專屬的員工入口網址，並建議加到手機主畫面。', '方式二：「通用連結」一條給所有新員工，填完會出現在「等你處理」，你按核准才能打卡。'], '員工的 PIN 只有員工自己知道，忘記請店主在「編輯」重設。員工入口連結不要轉給別人，遺失可以在員工清單重新寄一次。', '15-staff-emp'),
  ('排班', '一週一張表，看得清楚。', ['進入「② 班表」，點格子（員工 × 日期）。', '點班別範本（早班、晚班、全天）一鍵加入，或自訂時間；一個格子可以有多個班。', '按「複製上週班表」可以延續；改完按「儲存班表」。', '已核准的請假會用紅底顯示；正在上班的人有綠框；最右邊是本週合計工時。', '「班別範本」區可以改班別名稱、時間與遲到寬限（預設 5 分鐘）。'], '班表有改動但沒儲存時，換週會被擋下來提醒你。', '16-staff-plan'),
  ('員工打卡', '員工用自己的專屬入口，只看得到自己。', ['員工收到「登陸完成」信，點入口網址，直接是他自己的畫面（也可以在「員工」分頁重新寄給他）。', '入口只顯示今天有沒有打卡，不分上班下班，也不會列出其他同事。按大大的「打卡」，時間由系統記錄。', '超過上班時間才打卡，要選補打卡的原因（交通延誤、忘記打卡、臨時支援，或選「其他」自己寫）；原因會標示給店主。', '上班後一段時間（預設 15 分鐘）還沒打卡，系統會寄信提醒員工，也列給你。', '備用方式：打卡網址輸入員工編號和 PIN 登入。'], '打卡不驗證地點；要防代打，請把入口連結與 PIN 當成私人物品。補打卡原因與提醒時間可以在「班別範本」區調整。', '22-clock-home'),
  ('打卡紀錄與補登', '看誰幾點到、工時多少、誰忘了打。', ['「打卡紀錄」分頁選日期範圍與員工，按「查詢」。', '每筆會標示遲到幾分鐘、早退、未下班；上方是每位員工的總工時與出勤天數。', '員工忘記打卡：在下方「補登打卡」填員工、日期、上下班時間，儲存後會標「店家補登」。', '按「下載 CSV」給會計或自己算薪水。'], '員工忘了下班，隔天打上班卡時系統會提醒他，並在你這邊標「忘了下班」。', '17-staff-punch'),
  ('請假與特休', '特休天數依到職日自動算好。', ['員工在入口的「請假」分頁選類別（事假、病假、特休、公假、其他）、日期、事由，送出。', '特休依勞動基準法第 38 條，由到職日自動算出年度天數與剩餘；超過剩餘天數會被擋下。', '你會收到信；到「請假」分頁填回覆後按「核准」或「駁回」。', '核准後系統寄信通知員工並告知剩餘特休；假會自動出現在班表上。'], '特休天數上線前請會計確認公司是否另有較優的制度。', '18-staff-leave'),
  ('預期排班', '自動提醒夥伴填方便上班的日子，你協調後一鍵寄出。', ['在「班表」分頁的「預期排班」卡，打開「自動提醒」，選每月幾號（排下個月）或每兩週。', '時間到，系統自動寄一條專屬網址給每位夥伴；夥伴只選自己方便的日子（只有他和你看得到）。', '回覆人數與誰還沒填都看得到，按「提醒還沒填的人」補寄；填好的日子會在班表格子用淡綠色標示。', '你照預期排好班並儲存後，用「班表輸出與寄送」：下載 PDF（列印）或 1:1 圖檔（傳 LINE），或按「Email 寄給員工」，每人收到自己的班，可附完整班表。'], '沒有電子郵件的員工會被略過，並列在回報裡，請改用電話或 LINE 通知。', '30-staff-avail'),
  ('寄班表與緊急聯絡', '班表出來了，一鍵通知大家。', ['班表頁上方「寄本週班表」或「寄當月班表」，會寄給有填信箱而且有班的員工；沒寄的人會列出原因。', '想附 PDF 或 1:1 圖檔，用上一項的「班表輸出與寄送」。', '「今天沒排班，可以緊急聯絡」會列出今天沒有班（含請假）的在職員工，直接按「撥電話」或「寄信」。'], '寄信受每天的信件額度限制，人數很多時請分次寄。', None),
  ('文件下載區', '工作守則、教育訓練、常用文件，放這裡，員工隨時看。', ['「文件下載區」分頁選檔案（PDF、圖片、Word、Excel、PowerPoint、文字檔，每份 10MB 以內）。', '填標題、選分類：工作守則（開店關店流程）、教育訓練（新人必看）、常用文件，或規章制度、表單等。', '選「誰看得到」：「員工」只有員工入口看得到；「公開」顧客首頁的「資訊下載」也會顯示。', '重要的按「設為必讀」；員工看完按「我看完了」，每份文件旁會顯示有幾位員工看完，員工自己也看得到進度。'], '文件用「知道連結的人可看」方式分享，請不要放機密資料。', '20-staff-docs'),
  ('徵才登記', '看誰登記面試，錄取就轉成員工。', ['「徵才」分頁可以設定職缺名稱、開關招募，並複製面試登記網址。', '「登記名單」可以改狀態、寫備註、直接撥電話；選日期時間按「約面試並通知」會寄確認信給應徵者。', '按「轉成員工」會把姓名和聯絡方式帶入，並給你一組 PIN 告訴他。'], None, '19-staff-hire'),
 ]),
 ('設定與帳號', 'SETTINGS', [
  ('Logo 與店家資料', '店名、標語、配色、Logo，海報與名片都會用到。', ['主畫面「設定與帳號」→「Logo 與店家資料」。', '「Logo」：上傳圖片，系統檢查解析度（太小會退件），並自動偵測底色。', '「店家資料」：店名、標語、營業時間、海報底部的標籤，以及主色和強調色（有 20 組配色範本，點一下套用）。'], 'Logo 建議長邊 1500 px 以上、背景去背的 PNG，印出來最清楚。', '10-tools-logo'),
  ('帳號、夥伴與訂閱', '誰能用、用到什麼時候。', ['「帳號與訂閱」可以複製顧客網址、看訂閱狀態與到期日。', '「店內夥伴」：輸入名稱，按「產生邀請連結」傳給對方；對方開啟後綁定那支手機。可以隨時「停用」。', '「安全」：更改密碼；「登出所有手機」可以一鍵讓所有裝置重新登入。忘記密碼請到登入頁按「首次開通／忘記密碼」自己重設。', '訂閱到期後：7 天寬限期照常使用，之後 90 天只能查看不能修改，再之後停用。'], '夥伴帳號最多 30 個。', '27-account'),
  ('系統寄出的信', '重要的事都會寄信通知，一看就知道是誰寄的、要做什麼。', ['**星樂創意寄給你的信**：深藍頁首加星樂創意 Logo，例如登入驗證碼、帳號開通、收款確認、到期提醒。', '**寄給員工、應徵者的信**：頁首是你的店名和店家主色，寄件人顯示「店名（SFD 代寄）」，例如員工入口、班表、請假結果、面試確認。', '每封信只有一個主要按鈕，按下去就到要做的地方；驗證碼、金額、日期這些重點會放大顯示。', '店務通知（顧客預訂、請假申請、面試登記、未打卡、交接、叫貨）會寄到「帳號」頁填的「通知信箱」；沒有填就寄到登入信箱。哪些要收，可以自己選（下一節）。'], '收不到信先看垃圾信件匣，並把寄件地址加入聯絡人。驗證碼 5 分鐘內有效。我們不會在信裡跟你要密碼。', '32-mail'),
  ('選擇要收哪些通知信', '不需要的提醒就關掉，那一類就不會寄信。', ['到「帳號」→「店家資料」，找到「通知信箱」下面的「要收到哪些通知信」。', '**有人送出時馬上寄給我**：顧客預訂、異常回報、敲敲老闆、許願、員工請假申請、員工填好資料、面試登記。', '**系統定時自動寄**：未打卡名單、預期排班已提醒、交接提醒、叫貨提醒。未打卡、交接、叫貨可以分開選「寄給我」和「寄給員工」。', '取消勾選後按「儲存店家資料」就生效；想再收到，勾回來再儲存即可。', '關掉通知不影響資料：顧客的預訂、員工的請假一樣會記錄，到系統裡都看得到。'], '預期排班提醒的日期、未打卡要等幾分鐘，在「人員與班表」→「② 班表」下方調整。登入驗證碼、開通、收款、到期提醒這類帳號安全與訂閱的信一定會寄，不能關。', '33-notify'),
  ('分店管理（有多家店時）', '總店統一管理，分店各自營業。', ['主畫面「設定與帳號」→「分店管理」：上傳分店清單 CSV，一次建立全部分店；各分店有自己的資料與顧客網址。', '「品牌同步」：總店改了外觀、Logo、分類、菜單，按「預覽差異」確認後同步到分店（每家分店可以選要不要跟隨）。', '每家分店可以設價格規則（跟總店同價、加減％或加減元），分店自己改的價格會被保留。', '「跨店調價」與「跨店公告」可以一次處理所有分店。'], None, None),
 ]),
 ('常見問題', 'FAQ', [
  ('遇到問題先看這裡', '大部分狀況都可以自己解決。', ['**網址打不開，出現「無法開啟這個檔案」**：改用瀏覽器的「無痕分頁」打開；確認整串網址有複製完整。', '**收不到驗證碼**：先看垃圾信件匣；等 1～2 分鐘再按一次。連續錯太多次要等 15 分鐘。', '**價格改了，別支手機沒變**：夥伴手機約 15 秒同步；也可以重新整理頁面。', '**員工忘記 PIN**：店主到「人員與班表」→「員工」→「編輯」，輸入新的 PIN 儲存，員工用新 PIN 登入；員工入口連結重新寄給他即可。', '**員工說沒收到信**：先請他看垃圾信件匣；沒有填信箱的員工不會收到任何信，請改用電話或 LINE。', '**不小心記錯帳**：剛記的 10 秒內按「撤銷」；之後店主到「今日」或「報表」分頁刪除。', '**我的資料存在哪裡？**：存在你自己的 Google 試算表和雲端硬碟（包含員工證件與收據照片），你隨時可以打開來看。', '**訂閱到期了**：到期後 7 天內照常使用，請盡快續訂；超過後只能看不能改。', '**想請我們協助**：把畫面截圖和你做了什麼告訴我們，越清楚越快解決。'], None, None),
 ]),
]

def esc(s): return html.escape(s)
def fmt(s): return esc(s).replace('**', '\0').split('\0') if False else ''.join(('<b>' + esc(p) + '</b>') if i % 2 else esc(p) for i, p in enumerate(s.split('**')))

def build():
    toc, body = [], []
    n = 0
    for ci, (ctitle, ckey, items) in enumerate(CHAPTERS):
        toc.append(f'<div class="tc"><b>第 {ci + 1} 章</b>　{esc(ctitle)}</div>')
        body.append(f'<section class="chap"><div class="ck">{ckey}</div><h1><span>第 {ci + 1} 章</span>{esc(ctitle)}</h1><div class="items-n">{len(items)} 個主題</div></section>')
        for it in items:
            n += 1
            title, one, steps, tip, shot = it
            toc.append(f'<div class="ti">{ci + 1}.{items.index(it) + 1}　{esc(title)}</div>')
            data = img(shot) if shot else ''
            steps_html = ''.join(f'<li>{fmt(s)}</li>' for s in steps)
            tip_html = f'<div class="tip"><b>小提醒</b>{esc(tip)}</div>' if tip else ''
            shot_html = f'<div class="ph"><div class="phi"><img src="{data}" alt=""></div></div>' if data else ''
            body.append(f'<section class="topic{" has-shot" if data else ""}"><div class="tx"><div class="no">{ci + 1}.{items.index(it) + 1}</div><h2>{esc(title)}</h2><p class="one">{esc(one)}</p><ol>{steps_html}</ol>{tip_html}</div>{shot_html}</section>')
    cover = (f'<section class="cover"><div class="path" aria-hidden="true"></div><div class="top"><img class="lg" src="{svg("logo-horizontal-dark.svg")}" alt="StarFunDea 星樂創意"><span class="vv">{esc(VERSION)}</span></div>'
             f'<div class="mid"><div class="kk">MERCHANT GUIDE</div><h1>SFD系統使用指南</h1><div class="sub">商家版</div><div class="rule"></div>'
             f'<p class="tg">把點子，走成<b>亮點</b>。</p></div>'
             f'<div class="bot"><div class="note">給店主、店長與夥伴的操作說明。<br>每個功能都有「怎麼做」的步驟和手機畫面。</div><div class="co">星樂創意 StarFunDea　·　From idea to spark.</div></div></section>')
    toc_html = '<section class="toc"><h1>目錄</h1><div class="tl">' + ''.join(toc) + '</div></section>'
    css = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=Barlow+Condensed:wght@600;700&display=swap');
:root{--pri:#0E1623;--acc:#F29A00;--ink:#0E1623;--mute:#556176;--bg:#EEF0F4;--line:#DFE3EA}
*{box-sizing:border-box}@page{size:A4;margin:0}
body{margin:0;font-family:'Noto Sans TC','Microsoft JhengHei',sans-serif;color:var(--ink);line-height:1.65;-webkit-print-color-adjust:exact;print-color-adjust:exact;background:#fff}
section{page-break-inside:avoid}
.cover{height:297mm;width:210mm;background:radial-gradient(160mm 120mm at 95% 8%,#1d2c47 0,transparent 70%),#0E1623;color:#fff;padding:24mm 22mm 20mm;display:flex;flex-direction:column;justify-content:space-between;page-break-after:always;position:relative;overflow:hidden}
.cover>*{position:relative;z-index:1}.cover .path{position:absolute;inset:0;z-index:0;background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 210 297'><circle cx='118' cy='228' r='5' fill='none' stroke='%238FA0B8' stroke-width='1.6'/><g fill='%23FFB534'><circle cx='128' cy='216' r='1.3'/><circle cx='137' cy='204' r='1.5'/><circle cx='145' cy='191' r='1.7'/><circle cx='152' cy='177' r='1.9'/><circle cx='158' cy='162' r='2.1'/><circle cx='163' cy='146' r='2.3'/></g><path d='M176 70l6 16.5 16.5 6-16.5 6-6 16.5-6-16.5-16.5-6 16.5-6z' fill='%23FFB534'/></svg>") center/100% 100% no-repeat}
.cover .top{display:flex;justify-content:space-between;align-items:center}.cover .lg{height:11mm;width:auto}.cover .vv{font-family:'Barlow Condensed';letter-spacing:.2em;color:#8FA0B8;font-size:11pt;font-weight:600}
.cover .kk{font-family:'Barlow Condensed';letter-spacing:.34em;font-weight:700;color:#FFB534;font-size:14pt}.cover h1{font-size:44pt;margin:8mm 0 2mm;line-height:1.12;font-weight:900;letter-spacing:.03em}.cover .sub{font-size:22pt;font-weight:700;letter-spacing:.32em;color:#8FA0B8}
.cover .rule{width:22mm;height:1.6mm;background:#FFB534;margin:10mm 0 8mm}.cover .tg{font-size:15pt;font-weight:500;letter-spacing:.14em;margin:0;color:#dbe4f2}.cover .tg b{color:#FFB534;font-weight:900}
.cover .note{border-top:1.5px solid #2a3a55;padding-top:6mm;font-size:12pt;color:#b8c4d6;max-width:120mm}.cover .co{margin-top:6mm;font-family:'Barlow Condensed';letter-spacing:.2em;color:#8FA0B8;font-size:10.5pt}.toc{width:210mm;min-height:297mm;padding:24mm 22mm;page-break-after:always}.toc h1{font-size:26pt;margin:0 0 8mm}.tl{columns:2;column-gap:16mm}.tc{margin-top:6mm;font-weight:900;color:var(--pri);break-after:avoid;font-size:12pt}.ti{padding:1.2mm 0 1.2mm 4mm;border-bottom:1px solid var(--line);font-size:10.5pt}
.chap{width:210mm;height:297mm;padding:0 22mm;display:flex;flex-direction:column;justify-content:center;background:var(--bg);page-break-before:always;page-break-after:always}
.chap .ck{font-family:'Barlow Condensed';font-weight:700;letter-spacing:.3em;color:var(--acc);font-size:16pt}.chap h1{font-size:40pt;margin:4mm 0;font-weight:900;line-height:1.2}.chap h1 span{display:block;font-size:14pt;color:var(--mute);letter-spacing:.2em;margin-bottom:2mm}.chap .items-n{color:var(--mute)}
.topic{width:210mm;min-height:297mm;padding:20mm 20mm 16mm;display:flex;gap:10mm;align-items:flex-start;page-break-before:always;page-break-after:always}
.topic .tx{flex:1;min-width:0}.no{font-family:'Barlow Condensed';font-weight:700;color:var(--acc);font-size:15pt;letter-spacing:.1em}.topic h2{font-size:24pt;margin:1mm 0 2mm;font-weight:900;line-height:1.25}.one{font-size:12pt;color:var(--mute);margin:0 0 5mm}
ol{padding-left:6mm;margin:0}li{margin:0 0 2.6mm;font-size:11pt}li b{color:var(--pri)}li::marker{color:var(--acc);font-weight:900}
.tip{margin-top:6mm;background:#FFF6E3;border-left:3px solid var(--acc);padding:3mm 4mm;font-size:10.5pt;border-radius:0 6px 6px 0}.tip b{display:block;color:var(--acc);font-size:9.5pt;letter-spacing:.14em;margin-bottom:1mm}
.ph{flex:0 0 66mm}.phi{width:66mm;max-height:228mm;overflow:hidden;border-radius:7mm;border:2.2mm solid #0E1623;background:#0E1623;box-shadow:0 3mm 8mm rgba(14,22,35,.3)}.phi img{display:block;width:100%;height:auto;border-radius:4.5mm}
.topic:not(.has-shot) .tx{max-width:150mm}
"""
    return f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>{esc(PRODUCT)}　商家使用指南</title><style>{css}</style></head><body>{cover}{toc_html}{"".join(body)}</body></html>', n

async def main():
    doc, n = build()
    hp = os.path.join(OUT, 'SFD系統使用指南.html'); open(hp, 'w', encoding='utf-8').write(doc)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        await pg.set_content(doc, wait_until='networkidle'); await pg.evaluate('document.fonts.ready'); await pg.wait_for_timeout(800)
        pdf = os.path.join(OUT, 'SFD系統使用指南.pdf')
        await pg.pdf(path=pdf, format='A4', print_background=True, margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'})
        await b.close()
    pub = os.path.join(ROOT, 'publish', 'guide'); os.makedirs(pub, exist_ok=True)
    shutil.copy(hp, os.path.join(pub, 'index.html')); shutil.copy(pdf, os.path.join(pub, 'SFD系統使用指南.pdf'))
    import pymupdf
    d = pymupdf.open(pdf)
    print(f'完成：{n} 個主題，PDF {len(d)} 頁 → guide/SFD系統使用指南.pdf、publish/guide/')
    for i in (0, 2, 4, 5):
        if i < len(d): d[i].get_pixmap(dpi=60).save(os.path.join(OUT, f'_preview{i}.png'))

asyncio.run(main())
