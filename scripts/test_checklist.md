# Supervisor 架構測試清單

生成時間: 2025-12-11
測試目標: 驗證 Supervisor 架構穩定性和功能完整性，確保可安全移除 start_server.py

---

## 測試分類

- 功能測試（8 項）
- 穩定性測試（3 項）
- 兼容性測試（3 項）
- 安全性測試（3 項）

**總計**: 17 項測試

---

## 功能測試（8 項）

### TEST-F-01: 開發環境啟動功能

**測試項目**: `./manage.sh start-dev` 啟動成功

**執行步驟**:
1. 確保環境乾淨（執行 `./manage.sh stop-dev`）
2. 執行 `./manage.sh start-dev`
3. 等待 5 秒
4. 檢查進程狀態

**驗證命令**:
```bash
./manage.sh status-dev
curl http://localhost:3082/health
curl http://localhost:5175/
```

**預期結果**:
- Supervisor 啟動成功
- Backend 進程狀態 RUNNING
- Frontend 進程狀態 RUNNING
- Backend health check 返回 200
- Frontend 頁面可訪問

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-F-02: 開發環境停止功能

**測試項目**: `./manage.sh stop-dev` 完全停止並釋放 Port

**執行步驟**:
1. 確保服務正在運行
2. 執行 `./manage.sh stop-dev`
3. 等待 3 秒
4. 檢查進程和端口狀態

**驗證命令**:
```bash
./manage.sh status-dev  # 應顯示未運行
./scripts/port_cleaner.sh --check-only
lsof -i :3082  # 應無輸出
lsof -i :5175  # 應無輸出
```

**預期結果**:
- Supervisor 進程完全停止
- 所有子進程已終止
- Port 3082 已釋放
- Port 5175 已釋放
- 無殘留進程

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-F-03: 開發環境重啟功能

**測試項目**: `./manage.sh restart-dev` 正確重啟服務

**執行步驟**:
1. 確保服務正在運行
2. 記錄當前進程 PID
3. 執行 `./manage.sh restart-dev`
4. 等待 5 秒
5. 檢查新進程 PID

**驗證命令**:
```bash
./manage.sh status-dev
pgrep -f supervisord  # PID 應改變
curl http://localhost:3082/health
curl http://localhost:5175/
```

**預期結果**:
- 服務成功重啟
- 新 PID 與舊 PID 不同
- Backend 和 Frontend 正常運行
- Health check 通過

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-F-04: 後端日誌分離

**測試項目**: `./manage.sh logs-backend` 僅顯示後端日誌

**執行步驟**:
1. 確保服務正在運行
2. 執行 `./manage.sh logs-backend`
3. 檢查輸出內容

**驗證命令**:
```bash
./manage.sh logs-backend | head -20
```

**預期結果**:
- 僅顯示 Backend 相關日誌
- 日誌包含 Uvicorn、FastAPI 相關信息
- 不包含 Vite、Vue 相關信息
- 日誌格式正確

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-F-05: 前端日誌分離

**測試項目**: `./manage.sh logs-frontend` 僅顯示前端日誌

**執行步驟**:
1. 確保服務正在運行
2. 執行 `./manage.sh logs-frontend`
3. 檢查輸出內容

**驗證命令**:
```bash
./manage.sh logs-frontend | head -20
```

**預期結果**:
- 僅顯示 Frontend 相關日誌
- 日誌包含 Vite、Vue 相關信息
- 不包含 Uvicorn、FastAPI 相關信息
- 日誌格式正確

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-F-06: 全部日誌聯合顯示

**測試項目**: `./manage.sh logs-dev` 顯示所有日誌

**執行步驟**:
1. 確保服務正在運行
2. 執行 `./manage.sh logs-dev`
3. 檢查輸出內容

**驗證命令**:
```bash
./manage.sh logs-dev | head -30
```

**預期結果**:
- 同時顯示 Backend 和 Frontend 日誌
- 日誌交織顯示（按時間順序）
- 包含 Uvicorn、FastAPI、Vite、Vue 相關信息
- 日誌格式正確

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-F-07: Port 檢測功能

**測試項目**: `./scripts/port_cleaner.sh --check-only` 檢測 Port

**執行步驟**:
1. 啟動開發環境
2. 執行 `./scripts/port_cleaner.sh --check-only`
3. 檢查輸出

**驗證命令**:
```bash
./scripts/port_cleaner.sh --check-only
```

**預期結果**:
- 正確檢測到占用的 Port（3082, 5175）
- 顯示進程 PID 和命令
- 不執行清理操作
- 退出碼為 1（有占用）

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-F-08: Port 強制清理功能

**測試項目**: `./scripts/port_cleaner.sh --force` 清理 Port

**執行步驟**:
1. 啟動開發環境
2. 執行 `./scripts/port_cleaner.sh --force`
3. 等待 2 秒
4. 檢查 Port 狀態

**驗證命令**:
```bash
./scripts/port_cleaner.sh --force
lsof -i :3082  # 應無輸出
lsof -i :5175  # 應無輸出
./scripts/port_cleaner.sh --check-only  # 應顯示無占用
```

**預期結果**:
- 成功終止占用進程
- Port 3082 已釋放
- Port 5175 已釋放
- 清理後檢測顯示無占用
- 退出碼為 0

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

## 穩定性測試（3 項）

### TEST-S-01: 崩潰自動重啟測試

**測試項目**: 後端進程崩潰時 Supervisor 自動重啟

**執行步驟**:
1. 啟動開發環境
2. 查找後端進程 PID：`pgrep -f "uvicorn.*3082"`
3. 手動終止後端進程：`kill -9 <PID>`
4. 等待 5 秒
5. 檢查進程狀態

**驗證命令**:
```bash
./manage.sh start-dev
OLD_PID=$(pgrep -f "uvicorn.*3082")
echo "Old PID: $OLD_PID"
kill -9 $OLD_PID
sleep 5
NEW_PID=$(pgrep -f "uvicorn.*3082")
echo "New PID: $NEW_PID"
./manage.sh status-dev
curl http://localhost:3082/health
```

**預期結果**:
- 後端進程被終止後自動重啟
- 新 PID 與舊 PID 不同
- 重啟後服務正常運行
- Health check 通過
- Supervisor 狀態顯示 RUNNING

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-S-02: 長時間運行穩定性測試

**測試項目**: 服務連續運行 30 分鐘無異常

**執行步驟**:
1. 啟動開發環境
2. 記錄啟動時間
3. 等待 30 分鐘
4. 定期檢查服務狀態（每 5 分鐘）
5. 檢查日誌是否有錯誤

**驗證命令**:
```bash
./manage.sh start-dev
# 30 分鐘後
./manage.sh status-dev
./manage.sh logs-dev | grep -i error
curl http://localhost:3082/health
curl http://localhost:5175/
```

**預期結果**:
- 服務連續運行 30 分鐘
- 無進程崩潰或重啟（非預期）
- 無嚴重錯誤日誌
- Health check 持續通過
- 內存和 CPU 使用正常

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-S-03: 並發請求壓力測試

**測試項目**: 後端可處理並發請求

**執行步驟**:
1. 啟動開發環境
2. 使用 curl 發送 50 個並發請求
3. 檢查響應狀態
4. 檢查日誌錯誤

**驗證命令**:
```bash
./manage.sh start-dev
# 並發 50 個請求
for i in {1..50}; do
  curl -s http://localhost:3082/health &
done
wait
./manage.sh status-dev
./manage.sh logs-backend | tail -50
```

**預期結果**:
- 所有請求成功返回 200
- 後端進程保持穩定
- 無崩潰或錯誤日誌
- 響應時間合理（< 2 秒）

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

## 兼容性測試（3 項）

### TEST-C-01: WSL2 環境驗證

**測試項目**: 驗證在 WSL2 環境下正常運行

**執行步驟**:
1. 檢查當前環境
2. 啟動服務
3. 驗證所有功能

**驗證命令**:
```bash
uname -a | grep -i wsl
./manage.sh start-dev
./manage.sh status-dev
./manage.sh logs-dev | head -10
```

**預期結果**:
- 確認運行在 WSL2 環境
- 所有服務正常啟動
- 日誌輸出正常
- 無 WSL 相關錯誤

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-C-02: Port 占用檢測準確性

**測試項目**: Port 檢測工具準確識別占用

**執行步驟**:
1. 清理所有 Port
2. 手動啟動後端（占用 3082）
3. 運行檢測工具
4. 驗證檢測結果

**驗證命令**:
```bash
./scripts/port_cleaner.sh --force
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 3082 &
sleep 3
./scripts/port_cleaner.sh --check-only
kill %1
```

**預期結果**:
- 準確檢測到 Port 3082 被占用
- 顯示正確的進程信息
- 其他 Port 顯示未占用
- 檢測結果與 lsof 一致

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-C-03: 環境變量加載正確性

**測試項目**: .env 文件正確加載到後端

**執行步驟**:
1. 檢查 .env 文件存在
2. 啟動後端
3. 驗證環境變量

**驗證命令**:
```bash
test -f .env && echo "PASS: .env exists" || echo "FAIL: .env missing"
./manage.sh start-dev
curl http://localhost:3082/health
./manage.sh logs-backend | grep -i "environment\|config"
```

**預期結果**:
- .env 文件存在
- 後端成功加載環境變量
- 日誌顯示配置正確
- 無環境變量相關錯誤

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

## 安全性測試（3 項）

### TEST-X-01: 停止後 Port 完全釋放驗證

**測試項目**: 驗證停止後所有 Port 完全釋放

**執行步驟**:
1. 啟動所有服務（開發 + 生產）
2. 停止所有服務
3. 檢查所有 Port 狀態

**驗證命令**:
```bash
./manage.sh start-all
sleep 5
./manage.sh stop-all
sleep 3
lsof -i :3080  # 應無輸出
lsof -i :3082  # 應無輸出
lsof -i :5173  # 應無輸出
lsof -i :5175  # 應無輸出
./scripts/port_cleaner.sh --check-only  # 應顯示所有 Port 未占用
```

**預期結果**:
- Port 3080（生產後端）已釋放
- Port 3082（開發後端）已釋放
- Port 5173（生產前端）已釋放
- Port 5175（開發前端）已釋放
- Port 檢測工具確認無占用

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-X-02: 日誌文件權限和大小檢查

**測試項目**: 日誌文件權限正確且大小合理

**執行步驟**:
1. 啟動服務運行一段時間
2. 檢查日誌文件屬性
3. 驗證權限和大小

**驗證命令**:
```bash
./manage.sh start-dev
sleep 10
ls -lh logs/*.log
stat logs/backend-dev.log
stat logs/frontend-dev.log
```

**預期結果**:
- 日誌文件權限為 644 或更寬松（可讀）
- 日誌文件存在且可寫入
- 日誌大小合理（不過大）
- 日誌文件所有者正確

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

### TEST-X-03: 進程清理完整性驗證

**測試項目**: 停止後無殘留進程

**執行步驟**:
1. 啟動服務
2. 記錄所有相關進程
3. 停止服務
4. 檢查進程清理情況

**驗證命令**:
```bash
./manage.sh start-dev
pgrep -f supervisord
pgrep -f uvicorn
pgrep -f vite
./manage.sh stop-dev
sleep 3
pgrep -f supervisord  # 應無輸出
pgrep -f uvicorn      # 應無輸出
pgrep -f vite         # 應無輸出
```

**預期結果**:
- 停止前有 supervisord、uvicorn、vite 進程
- 停止後所有相關進程已終止
- 無殘留子進程
- 進程樹完全清理

**實際結果**: [ ]

**狀態**: [ ] PASS  [ ] FAIL

---

## 測試結果統計

- 功能測試: [ ] / 8 通過
- 穩定性測試: [ ] / 3 通過
- 兼容性測試: [ ] / 3 通過
- 安全性測試: [ ] / 3 通過

**總計**: [ ] / 17 通過

**通過率**: [ ]%

**驗收標準**: 100% 通過（17/17）

---

## 測試環境信息

- 操作系統: Linux (WSL2)
- Supervisor 版本: 4.2.1
- Python 版本: 3.x
- Node.js 版本: 18.x+
- 測試日期: [ ]
- 測試執行人: Claude Code

---

## 備註

1. 所有測試應在乾淨環境下執行
2. 每次測試前執行 `./manage.sh stop-dev` 確保環境清潔
3. 記錄所有失敗案例的詳細日誌
4. 對失敗項目進行修復後重測
5. 長時間穩定性測試可在背景執行

---

**測試清單狀態**: 已完成 ✅
**下一步**: 執行階段 2（測試執行與結果驗證）
